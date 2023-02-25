from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .bot import MangaClient

import hashlib
import re

import aiohttp
from bs4 import BeautifulSoup

from src.static import RegExpressions

from .errors import MangaNotFoundError


class ABCScan:
    MIN_TIME_BETWEEN_REQUESTS = 1.0  # In seconds
    base_url: str = None
    fmt_url: str = None
    name: str = "Unknown"

    @classmethod
    async def check_updates(
        cls,
        bot: MangaClient,
        human_name: str,
        url_manga_name: str,
        manga_id: str,
        last_chapter: int,
    ) -> tuple[str, float, bool]:
        """
        Summary:

        Checks whether a new release has appeared on the scanlator's website.
        Checks whether the series is completed or not.

        Parameters:

        session: aiohttp.ClientSession - The session to use for the request.
        manga: str - The name of the manga.
        manga_id: str - The ID of the manga.
        last_chapter: int - The last chapter released last time.

        Returns:

        str/None - The `url` of the new chapter if a new release appeared, otherwise `None`.
        float/None - The `chapter` number of the new chapter if a new release appeared, otherwise `None`.
        bool - `True` if the series is completed, otherwise `False`.
        """
        raise NotImplementedError

    @staticmethod
    def _bs_is_series_completed(soup: BeautifulSoup) -> bool:
        """
        Summary:

        Checks whether a series is completed or not.

        Parameters:

        soup: BeautifulSoup - The soup object to check the series status.

        Returns:

        bool - `True` if the series is completed, otherwise `False`.
        """
        raise NotImplementedError

    @classmethod
    async def is_series_completed(
        cls, session: aiohttp.ClientSession, manga_id: str, url_manga_name: str
    ) -> bool:
        """
        Summary:

        Checks whether a series is completed or not.

        Parameters:

        session: aiohttp.ClientSession - The session to use for the request.
        manga_id: str - The ID of the manga.
        url_manga_name: str - The name of the manga in the scanlator's website.

        Returns:

        bool - `True` if the series is completed, otherwise `False`.

        Raises:

        MangaNotFoundError - If the manga is not found in the scanlator's website.
        """
        raise NotImplementedError

    @classmethod
    async def get_human_name(
        cls, session: aiohttp.ClientSession, manga_id: str, url_manga_name: str
    ) -> str:
        """
        Summary:

        Gets the human-readable name of the manga.

        Parameters:

        session: aiohttp.ClientSession - The session to use for the request.
        manga_id: str - The ID of the manga.
        url_manga_name: str - The name of the manga in the scanlator's website.

        Returns:

        str - The human-readable name of the manga.

        Raises:

        MangaNotFoundError - If the manga is not found in the scanlator's website.
        """
        raise NotImplementedError

    @classmethod
    def get_manga_id(cls, manga_url: str) -> str:
        """
        Summary:

        Gets the ID of the manga.

        Parameters:

        manga: str - The URL of the manga.

        Returns:

        str - The ID of the manga.
        """
        return hashlib.sha256(manga_url.encode()).hexdigest()

    @classmethod
    async def get_curr_chapter_num(
        cls,
        session: aiohttp.ClientSession,
        manga_id: str,
        url_manga_name: str,
    ) -> float | None:
        """
        Summary:

        Gets the number of chapters released so far for the manga.

        Parameters:

        session: aiohttp.ClientSession - The session to use for the request.
        url_manga_name: str - The name of the manga in the scanlator's website.
        manga_id: str - The ID of the manga.

        Returns:

        float/None - The number of chapters released so far for the manga.
        """
        raise NotImplementedError

    @classmethod
    def get_rx_url_name(cls, url: str) -> str | None:
        """
        Summary:

        Gets the name of the manga from the URL.

        Parameters:

        url: str - The URL of the manga.

        Returns:

        str - The name of the manga from the URL.
            Note: This can be the ID of the manga depending on the scanlator (i.e. Mangadex).
        None - If the URL is not valid.
        """
        raise NotImplementedError


class TritiniaScans(ABCScan):
    base_url = "https://tritinia.org/manga/"
    fmt_url = base_url + "{manga}/ajax/chapters/"
    name = "tritinia"

    @classmethod
    async def check_updates(
        cls,
        bot: MangaClient,
        human_name: str,
        url_manga_name: str,
        manga_id: str,
        last_chapter: int,
    ) -> tuple[str, float, bool] | None:
        url_manga_name = RegExpressions.tritinia_url.search(url_manga_name).group(3)

        async with bot._session.post(cls.fmt_url.format(manga=url_manga_name)) as resp:
            if resp.status != 200:
                print("Tritinia: Failed to get manga page", resp.status)
                return None
            text = await resp.text()

            soup = BeautifulSoup(text, "html.parser")
            last_chapter_container = soup.find("li", {"class": "wp-manga-chapter"})
            last_chapter_tag = last_chapter_container.find("a")

            new_url = last_chapter_tag["href"]
            new_chapter = float(
                RegExpressions.chapter_num_from_url.search(new_url).group(1)
            )

            completed = await cls.is_series_completed(bot, manga_id, url_manga_name)
            if new_chapter > last_chapter:
                return new_url, new_chapter, completed

    @classmethod
    async def get_curr_chapter_num(
        cls, bot: MangaClient, manga_id: str, url_manga_name: str
    ) -> float | None:
        async with bot._session.post(cls.fmt_url.format(manga=url_manga_name)) as resp:
            if resp.status != 200:
                return None
            text = await resp.text()

            soup = BeautifulSoup(text, "html.parser")
            last_chapter_container = soup.find("li", {"class": "wp-manga-chapter"})
            last_chapter_tag = last_chapter_container.find("a")

            new_url = last_chapter_tag["href"]
            latest_chapter = float(
                RegExpressions.chapter_num_from_url.search(new_url).group(1)
            )
            return latest_chapter

    @staticmethod
    def _bs_is_series_completed(soup: BeautifulSoup) -> bool:
        """Returns whether the series is completed or not."""
        status_container = soup.find("div", {"class": "post-status"})
        status_div = status_container.find_all("div", {"class": "post-content_item"})[1]
        status = status_div.find("div", {"class": "summary-content"})
        status = status.text.strip()

        return status != "OnGoing"

    @classmethod
    async def is_series_completed(
        cls, bot: MangaClient, manga_id: str, url_manga_name: str
    ) -> bool:
        async with bot._session.get(cls.base_url + url_manga_name) as resp:
            if resp.status != 200:
                raise MangaNotFoundError(manga_url=cls.base_url + url_manga_name)

            soup = BeautifulSoup(await resp.text(), "html.parser")
            return cls._bs_is_series_completed(soup)

    @classmethod
    async def get_human_name(
        cls, bot: MangaClient, manga_id: str, url_manga_name: str
    ) -> str | None:
        async with bot._session.get(cls.base_url + url_manga_name) as resp:
            if resp.status != 200:
                return None

            soup = BeautifulSoup(await resp.text(), "html.parser")
            title_div = soup.find("div", {"class": "post-title"})
            title = title_div.find("h1")
            span_found = title.find("span")
            if span_found:
                span_found.decompose()
            return title.text.strip()

    @classmethod
    def get_manga_id(cls, manga_url: str) -> str:
        hash_object = hashlib.sha1(manga_url.encode())
        return hash_object.hexdigest()

    @classmethod
    def get_rx_url_name(cls, url: str) -> str | None:
        if RegExpressions.tritinia_url.match(url):
            return RegExpressions.tritinia_url.search(url).group(3)


class Manganato(ABCScan):
    base_url = "https://chapmanganato.com/manga-"
    fmt_url = base_url + "{manga_id}"
    name = "manganato"

    @classmethod
    async def check_updates(
        cls,
        bot: MangaClient,
        human_name: str,
        url_manga_name: str,
        manga_id: str,
        last_chapter: int,
    ) -> tuple[str, float, bool] | None:
        async with bot._session.get(cls.fmt_url.format(manga_id=manga_id)) as resp:
            if resp.status != 200:
                print("Manganato: Failed to get manga page", resp.status)
                return None

            soup = BeautifulSoup(await resp.text(), "html.parser")

            chapter_list_container = soup.find(
                "div", {"class": "panel-story-chapter-list"}
            )
            last_chapter_link = chapter_list_container.find("a")
            last_chapter_url = last_chapter_link["href"]
            last_web_chapter = float(
                RegExpressions.chapter_num_from_url.search(last_chapter_url).group(1)
            )

            if float(last_chapter) == last_web_chapter:
                return None
            return last_chapter_url, last_web_chapter, cls._bs_is_series_completed(soup)

    @staticmethod
    def _bs_is_series_completed(soup: BeautifulSoup) -> bool:
        """Returns whether the series is completed or not."""
        status_container = soup.find("table", {"class": "variations-tableInfo"})
        status_labels = status_container.find_all(
            "td", {"class": "table-label"}, limit=5
        )
        status_values = status_container.find_all(
            "td", {"class": "table-value"}, limit=5
        )
        status = [
            (lbl.text.strip(), val.text.strip())
            for lbl, val in zip(status_labels, status_values)
            if lbl.text.strip() == "Status :"
        ][0][1]
        return status == "Completed"

    @classmethod
    async def is_series_completed(
        cls, bot: MangaClient, manga_id: str, url_manga_name: str
    ) -> bool:
        async with bot._session.get(cls.fmt_url.format(manga_id=manga_id)) as resp:
            if resp.status != 200:
                raise MangaNotFoundError(cls.fmt_url.format(manga_id=manga_id))

            text = await resp.text()

            if "404 - PAGE NOT FOUND" in text:
                raise MangaNotFoundError(cls.fmt_url.format(manga_id=manga_id))

            soup = BeautifulSoup(await resp.text(), "html.parser")
            return cls._bs_is_series_completed(soup)

    @classmethod
    async def get_human_name(
        cls, bot: MangaClient, manga_id: str, url_manga_name: str
    ) -> str | None:
        async with bot._session.get(cls.fmt_url.format(manga_id=manga_id)) as resp:
            if resp.status != 200:
                return None

            soup = BeautifulSoup(await resp.text(), "html.parser")
            title_div = soup.find("div", {"class": "story-info-right"})
            return title_div.find("h1").text.strip()

    @classmethod
    async def get_curr_chapter_num(
        cls, bot: MangaClient, manga_id: str, url_manga_name: str
    ) -> float | None:
        async with bot._session.get(cls.fmt_url.format(manga_id=manga_id)) as resp:
            if resp.status != 200:
                return None

            soup = BeautifulSoup(await resp.text(), "html.parser")

            chapter_list_container = soup.find(
                "div", {"class": "panel-story-chapter-list"}
            )
            last_chapter_link = chapter_list_container.find("a")
            last_chapter_url = last_chapter_link["href"]
            last_web_chapter = float(
                RegExpressions.chapter_num_from_url.search(last_chapter_url).group(1)
            )

            return last_web_chapter

    @classmethod
    def get_manga_id(cls, manga_url: str) -> str:
        return re.search(r"manga-(.*)", manga_url).group(1)

    @classmethod
    def get_rx_url_name(cls, url: str) -> str | None:
        if RegExpressions.manganato_url.match(url):
            return RegExpressions.manganato_url.search(url).group(4)


class Toonily(ABCScan):
    base_url = "https://toonily.com/webtoon/"
    fmt_url = base_url + "{manga_url_name}"
    name = "toonily"

    @classmethod
    async def check_updates(
        cls,
        bot: MangaClient,
        human_name: str,
        url_manga_name: str,
        manga_id: str,
        last_chapter: int,
    ) -> tuple[str, float, bool] | None:

        url_manga_name = RegExpressions.toonily_url.search(url_manga_name).group(3)

        async with bot._session.get(
            cls.fmt_url.format(manga_url_name=url_manga_name)
        ) as resp:
            if resp.status != 200:
                print("Toonily: Failed to get manga page", resp.status)
                return None

            soup = BeautifulSoup(await resp.text(), "html.parser")

            chapter_list_container = soup.find(
                "ul", {"class": "main version-chap no-volumn"}
            )
            last_chapter_link = chapter_list_container.find("a")
            last_chapter_url = last_chapter_link["href"]
            last_web_chapter = float(
                RegExpressions.chapter_num_from_url.search(last_chapter_url).group(1)
            )

            if float(last_chapter) == last_web_chapter:
                return None
            return last_chapter_url, last_web_chapter, cls._bs_is_series_completed(soup)

    @classmethod
    async def get_curr_chapter_num(
        cls, bot: MangaClient, manga_id: str, url_manga_name: str
    ) -> float | None:
        async with bot._session.get(
            cls.fmt_url.format(manga_url_name=url_manga_name)
        ) as resp:
            if resp.status != 200:
                return None

            soup = BeautifulSoup(await resp.text(), "html.parser")

            chapter_list_container = soup.find(
                "ul", {"class": "main version-chap no-volumn"}
            )
            last_chapter_link = chapter_list_container.find("a")
            last_chapter_url = last_chapter_link["href"]
            last_web_chapter = float(
                RegExpressions.chapter_num_from_url.search(last_chapter_url).group(1)
            )

            return last_web_chapter

    @staticmethod
    def _bs_is_series_completed(soup: BeautifulSoup) -> bool:
        """Returns whether the series is completed or not."""
        status_container = soup.find("div", {"class": "post-status"})
        status_div = status_container.find_all("div", {"class": "post-content_item"})[1]
        status = status_div.find("div", {"class": "summary-content"})
        status = status.text.strip()

        return status != "OnGoing"

    @classmethod
    async def is_series_completed(
        cls, bot: MangaClient, manga_id: str, url_manga_name: str
    ) -> bool:
        async with bot._session.get(
            cls.fmt_url.format(manga_url_name=url_manga_name)
        ) as resp:
            if resp.status != 200:
                raise MangaNotFoundError(manga_url=cls.base_url + url_manga_name)

            soup = BeautifulSoup(await resp.text(), "html.parser")
            return cls._bs_is_series_completed(soup)

    @classmethod
    async def get_human_name(
        cls, bot: MangaClient, manga_id: str, url_manga_name: str
    ) -> str | None:
        async with bot._session.get(cls.base_url + url_manga_name) as resp:
            if resp.status != 200:
                return None

            soup = BeautifulSoup(await resp.text(), "html.parser")
            title_div = soup.find("div", {"class": "post-title"})
            title = title_div.find("h1")
            span_found = title.find("span")
            if span_found:
                span_found.decompose()
            return title.text.strip()

    @classmethod
    def get_manga_id(cls, manga_url: str) -> str:
        return super().get_manga_id(manga_url)

    @classmethod
    def get_rx_url_name(cls, url: str) -> str | None:
        if RegExpressions.toonily_url.match(url):
            return RegExpressions.toonily_url.search(url).group(3)


class MangaDex(ABCScan):
    base_url = "https://mangadex.org/"
    fmt_url = base_url + "title/{manga_id}"
    name = "mangadex"

    @classmethod
    async def check_updates(
        cls,
        bot: MangaClient,
        human_name: str,
        url_manga_name: str,
        manga_id: str,
        last_chapter: int,
    ) -> tuple[str, float, bool] | None:

        chapters = await bot.mangadex_api.get_chapters_list(manga_id)
        last_chapter_url = "https://mangadex.org/chapter/" + chapters[-1]["id"]
        last_web_chapter = float(chapters[-1]["attributes"]["chapter"])

        if float(last_chapter) == last_web_chapter:
            return None

        return (
            last_chapter_url,
            last_web_chapter,
            await cls.is_series_completed(bot, manga_id, url_manga_name),
        )

    @classmethod
    async def get_curr_chapter_num(
        cls, bot: MangaClient, manga_id: str, url_manga_name: str
    ) -> float | None:
        chapters = await bot.mangadex_api.get_chapters_list(manga_id)
        return float(chapters[-1]["attributes"]["chapter"])

    @classmethod
    async def is_series_completed(
        cls, bot: MangaClient, manga_id: str, url_manga_name: str
    ) -> bool:
        manga = await bot.mangadex_api.get_manga(manga_id)
        return manga["data"]["attributes"]["status"] == "completed"

    @classmethod
    async def get_human_name(
        cls, bot: MangaClient, manga_id: str, url_manga_name: str
    ) -> str | None:
        manga = await bot.mangadex_api.get_manga(manga_id)
        return manga["data"]["attributes"]["title"]["en"]

    @classmethod
    def get_manga_id(cls, manga_url: str) -> str:
        return RegExpressions.mangadex_url.search(manga_url).group(3)

    @classmethod
    def get_rx_url_name(cls, url: str) -> str | None:
        if RegExpressions.mangadex_url.match(url):
            return RegExpressions.mangadex_url.search(url).group(3)


SCANLATORS: dict[ABCScan] = {
    Toonily.name: Toonily,
    TritiniaScans.name: TritiniaScans,
    Manganato.name: Manganato,
    MangaDex.name: MangaDex,
}
