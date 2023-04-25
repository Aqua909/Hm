from __future__ import annotations

import asyncio
import traceback as tb
from typing import TYPE_CHECKING, Dict

import discord

from src.core.objects import Manga, ChapterUpdate
from src.core.ratelimiter import RateLimiter
from src.core.scanners import SCANLATORS, ABCScan
from src.utils import group_items_by

if TYPE_CHECKING:
    from src.core import MangaClient

from discord.ext import commands, tasks


class UpdateCheckCog(commands.Cog):
    def __init__(self, bot: MangaClient) -> None:
        self.bot: MangaClient = bot
        self.SCANLATORS: Dict[str, ABCScan] = SCANLATORS
        self.rate_limiter: RateLimiter = RateLimiter()

    async def cog_load(self):
        self.bot.logger.info("Loaded Updates Cog...")

        self.check_updates_task.add_exception_type(Exception)
        self.check_updates_task.start()

    async def check_updates_by_scanlator(self, mangas: list[Manga]):
        if mangas and mangas[0].scanlator not in self.SCANLATORS:
            self.bot.logger.error(f"Unknown scanlator {mangas[0].scanlator}")
            return

        self.bot.logger.info(f"Checking for updates for {mangas[0].scanlator}...")
        scanner = self.SCANLATORS.get(mangas[0].scanlator)

        disabled_scanlators = await self.bot.db.get_disabled_scanlators()
        if scanner.name in disabled_scanlators:
            self.bot.logger.info(f"Scanlator {scanner.name} is disabled... Ignoring update check!")
            return

        for manga in mangas:
            await self.rate_limiter.delay_if_necessary(manga)

            try:
                update_check_result: ChapterUpdate = await scanner.check_updates(
                    self.bot, manga
                )
            except Exception as e:
                self.bot.logger.warning(
                    f"Error while checking for updates for {manga.human_name} ({manga.id})",
                    exc_info=e,
                )
                traceback = "".join(
                    tb.format_exception(type(e), e, e.__traceback__)
                )
                await self.bot.log_to_discord(f"Error when checking updates: {traceback}")
                continue

            if not update_check_result.new_chapters and manga.cover_url == update_check_result.new_cover_url:
                continue

            guild_ids = await self.bot.db.get_manga_guild_ids(manga.id)
            guild_configs = await self.bot.db.get_many_guild_config(guild_ids)

            if update_check_result.new_chapters:
                for i, chapter in enumerate(update_check_result.new_chapters):
                    self.bot.logger.info(
                        f"({manga.scanlator}) {manga.human_name} ====> Chapter "
                        f"{chapter.name} released!"
                    )
                    extra_kwargs = update_check_result.extra_kwargs[i] if len(
                        update_check_result.extra_kwargs
                    ) > i else {}

                    for guild_config in guild_configs:
                        try:
                            role_ping = "" if not guild_config.role else f"{guild_config.role.mention} "
                            await guild_config.webhook.send(
                                (
                                    f"{role_ping}**{manga.human_name}** **{chapter.name}**"
                                    f" has been released!\n{chapter.url}"
                                ),
                                allowed_mentions=discord.AllowedMentions(roles=True),
                                **extra_kwargs
                            )
                        except discord.HTTPException as e:
                            self.bot.logger.error(
                                f"Failed to send update for {manga.human_name}| {chapter.name}", exc_info=e
                            )

                manga.update(
                    update_check_result.new_chapters[-1] if update_check_result.new_chapters else None,
                    update_check_result.series_completed,
                    update_check_result.new_cover_url
                )
                await self.bot.db.update_series(manga)

            else:
                self.bot.logger.info(
                    f"({manga.scanlator}) {manga.human_name} ====> COVER UPDATE"
                )

        self.bot.logger.info(f"Finished checking for updates for {mangas[0].scanlator}...")

    @tasks.loop(hours=1.0)
    async def check_updates_task(self):
        self.bot.logger.info("Checking for updates...")
        try:
            series_to_delete: list[Manga] = await self.bot.db.get_series_to_delete()
            if series_to_delete:
                self.bot.logger.warning(
                    "Deleting the following series: ================="
                    + "\n".join(
                        f'({x.scanlator}) ' + x.human_name for x in series_to_delete
                    )
                )
                await self.bot.db.bulk_delete_series([m.id for m in series_to_delete])

            series_to_update: list[Manga] = await self.bot.db.get_series_to_update()

            if not series_to_update:
                return

            series_to_update: list[list[Manga]] = group_items_by(series_to_update, ["scanlator"])

            _tasks = [
                self.bot.loop.create_task(self.check_updates_by_scanlator(mangas))
                for mangas in series_to_update
            ]
            await asyncio.gather(*_tasks)
        except Exception as e:
            self.bot.logger.error("Error while checking for updates", exc_info=e)
            traceback = "".join(tb.format_exception(type(e), e, e.__traceback__))
            await self.bot.log_to_discord(f"Error when checking updates: {traceback}")
        finally:

            self.bot.logger.info("Update check finished =================")

    @check_updates_task.before_loop
    async def before_check_updates_task(self):
        await self.bot.wait_until_ready()


async def setup(bot: MangaClient) -> None:
    if bot.debug and bot.test_guild_id:
        await bot.add_cog(UpdateCheckCog(bot), guild=discord.Object(id=bot.test_guild_id))
    else:
        await bot.add_cog(UpdateCheckCog(bot))