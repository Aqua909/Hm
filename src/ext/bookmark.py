from __future__ import annotations
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from src.core import MangaClient

from src.core.scanners import SCANLATORS
from src.core.objects import ABCScan

import discord

from discord.ext import commands
from src.utils import get_manga_scanlator_class, create_bookmark_embed
from discord import app_commands
from src.core.errors import MangaNotFound, BookmarkNotFound, ChapterNotFound
from src.ui import BookmarkView


class BookmarkCog(commands.Cog):
    def __init__(self, bot: MangaClient):
        self.bot: MangaClient = bot

    async def bookmark_autocomplete(
            self, interaction: discord.Interaction, argument: str
    ) -> list[discord.app_commands.Choice]:
        bookmarks = await self.bot.db.get_user_bookmarks_autocomplete(interaction.user.id, argument)
        if not bookmarks:
            return []

        return [
            discord.app_commands.Choice(
                name=x[1],
                value=x[0]
            ) for x in bookmarks
               ][:25]

    async def chapter_autocomplete(
            self, interaction: discord.Interaction, argument: str
    ) -> list[discord.app_commands.Choice]:
        series_id = interaction.namespace["manga"]
        if series_id is None:
            return []
        chapters = await self.bot.db.get_bookmark_chapters(interaction.user.id, series_id, argument)
        if not chapters:
            return []

        return [
            discord.app_commands.Choice(
                name=chp.chapter_string,
                value=chp.url
            ) for chp in chapters
        ][:25]

    bookmark_group = app_commands.Group(name="bookmark", description="Bookmark a manga")

    @bookmark_group.command(name="new", description="Bookmark a new manga")
    @app_commands.describe(manga_url="The url of the manga you want to bookmark")
    async def bookmark_new(self, interaction: discord.Interaction, manga_url: str):
        await interaction.response.defer(ephemeral=True, thinking=True)

        scanner: ABCScan = get_manga_scanlator_class(SCANLATORS, manga_url)
        if not scanner:
            em = discord.Embed(title="Invalid URL", color=discord.Color.red())
            em.description = (
                "The URL you provided does not follow any of the known url formats.\n"
                "See `/supported_websites` for a list of supported websites and their url formats."
            )
            em.set_footer(text="Manga Updates", icon_url=self.bot.user.avatar.url)
            return await interaction.followup.send(embed=em, ephemeral=True)

        manga_id = scanner.get_manga_id(manga_url)
        bookmark = await scanner.make_bookmark_object(
            self.bot, manga_id, manga_url, interaction.user.id, interaction.guild.id
        )
        if not bookmark:
            raise MangaNotFound(manga_url)

        bookmark.last_read_chapter = bookmark.available_chapters[0]

        await self.bot.db.upsert_bookmark(bookmark)
        em = create_bookmark_embed(self.bot, bookmark, scanner.icon_url)
        await interaction.followup.send(
            f"Successfully bookmarked {bookmark.manga.human_name}", embed=em, ephemeral=True
        )
        return

    @bookmark_group.command(name="view", description="View your bookmark(s)")
    @app_commands.rename(series_id="manga")
    @app_commands.describe(series_id="The name of the bookmarked manga you want to view")
    @app_commands.autocomplete(series_id=bookmark_autocomplete)
    async def bookmark_view(self, interaction: discord.Interaction, series_id: Optional[str] = None):
        await interaction.response.defer(ephemeral=True, thinking=True)
        if not series_id:
            bookmarks = await self.bot.db.get_user_bookmarks(interaction.user.id)
            if not bookmarks:
                return await interaction.followup.send("You have no bookmarks", ephemeral=True)

            view = BookmarkView(self.bot, interaction, bookmarks)
            view.bookmarks_to_text_embeds()

            view.message = await interaction.followup.send(embed=view.items[0], view=view, ephemeral=True)
            return

        else:
            bookmark = await self.bot.db.get_user_bookmark(interaction.user.id, series_id)
            scanner = SCANLATORS[bookmark.manga.scanlator]
            em = create_bookmark_embed(self.bot, bookmark, scanner.icon_url)
            return await interaction.followup.send(embed=em, ephemeral=True)

    @bookmark_group.command(name="update", description="Update a bookmark")
    @app_commands.rename(series_id="manga")
    @app_commands.rename(chapter_url="chapter")
    @app_commands.describe(series_id="The name of the bookmarked manga you want to update")
    @app_commands.describe(chapter_url="The chapter you want to update the bookmark to")
    @app_commands.autocomplete(series_id=bookmark_autocomplete)
    @app_commands.autocomplete(chapter_url=chapter_autocomplete)
    async def bookmark_update(self, interaction: discord.Interaction, series_id: str, chapter_url: str):
        await interaction.response.defer(ephemeral=True, thinking=True)
        chapters = await self.bot.db.get_bookmark_chapters(interaction.user.id, series_id)
        if not chapters:
            raise BookmarkNotFound()

        chapter = next((x for x in chapters if x.url == chapter_url), None)
        if not chapter:
            raise ChapterNotFound(chapter_url)
        await self.bot.db.update_last_read_chapter(interaction.user.id, series_id, chapter)
        await interaction.followup.send(f"Successfully updated bookmark to {chapter.chapter_string}", ephemeral=True)
        return

    @bookmark_group.command(name="delete", description="Delete a bookmark")
    @app_commands.rename(series_id="manga")
    @app_commands.describe(series_id="The name of the bookmarked manga you want to delete")
    @app_commands.autocomplete(series_id=bookmark_autocomplete)
    async def bookmark_delete(self, interaction: discord.Interaction, series_id: str):
        await interaction.response.defer(ephemeral=True, thinking=True)
        deleted: bool = await self.bot.db.delete_bookmark(interaction.user.id, series_id)
        if not deleted:
            raise BookmarkNotFound()
        return await interaction.followup.send("Successfully deleted bookmark", ephemeral=True)


async def setup(bot: MangaClient) -> None:
    if bot._debug_mode and bot.test_guild_id:
        await bot.add_cog(BookmarkCog(bot), guild=discord.Object(id=bot.test_guild_id))
    else:
        await bot.add_cog(BookmarkCog(bot))