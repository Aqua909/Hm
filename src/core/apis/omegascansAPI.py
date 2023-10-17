from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.apis import APIManager

import aiohttp
from bs4 import BeautifulSoup

from src.core.cache import CachedClientSession


class OmegaScansAPI:
    def __init__(
            self,
            api_manager: APIManager
    ):
        self.api_url: str = "https://api.omegascans.org"
        self.manager: APIManager = api_manager
        self.headers = {
            # "User-Agent": "github.com/MooshiMochi/ManhwaUpdatesBot",
        }
        self.rate_limit_remaining = 300
        self.rate_limit_reset = datetime.now().timestamp() + 60

    async def __request(
            self,
            method: str,
            endpoint: str,
            params: Optional[Dict[str, Any]] = None,
            data: Optional[Dict[str, Any]] = None,
            headers: Optional[Dict[str, Any]] = None,
            **kwargs
    ) -> Dict[str, Any]:
        url = f"{self.api_url}/{endpoint}"
        if not headers:
            headers = self.headers

        if self.rate_limit_remaining is not None and self.rate_limit_remaining == 0:
            await asyncio.sleep(self.rate_limit_reset)

        try:
            async with self.manager.session.request(
                    method, url, params=params, json=data, headers=headers, **kwargs
            ) as response:
                json_data = await response.json()
                if limit_remaining := response.headers.get("X-RateLimit-Remaining"):
                    self.rate_limit_remaining = int(limit_remaining)
                else:
                    self.rate_limit_remaining -= 1

                if limit_reset := response.headers.get("X-RateLimit-Reset"):
                    self.rate_limit_reset = int(limit_reset)
                else:
                    if datetime.now().timestamp() > self.rate_limit_reset:
                        self.rate_limit_reset = datetime.now().timestamp() + 60
                        self.rate_limit_remaining = 300

                if response.status != 200:
                    raise Exception(
                        f"Request failed with status {response.status}: {json_data}"
                    )
                return json_data
        except aiohttp.ServerDisconnectedError:
            self.manager.session.logger.error("Server disconnected, retrying with new session...")
            # noinspection PyProtectedMember
            session_proxy = self.manager.session._proxy
            await self.manager.session.close()
            self.manager._session = CachedClientSession(proxy=session_proxy, name=self.manager.session._name,  # noqa
                                                        trust_env=True)
            return await self.__request(method, endpoint, params, data, headers, **kwargs)

    async def get_manga(self, url_name: str) -> Dict[str, Any]:
        endpoint = f"series/{url_name}"
        return await self.__request("GET", endpoint)

    async def get_synopsis(self, url_name: str) -> Optional[str]:
        manga = await self.get_manga(url_name)
        if (html_code := manga.get("description")) is not None:
            soup = BeautifulSoup(html_code, "html.parser")
            return soup.get_text(strip=True)
        return None

    async def get_chapters_list(
            self, url_name: str, limit: int = -1
    ) -> list[Dict[str, Any]]:
        """
        Summary:
            Return a list of chapters in ascending order

        Args:
            url_name (str): The url_name of the manga
            limit (int, optional): The number of chapters to return. Defaults to -1 (no limit).

        Returns:
            list[Dict[str, Any]]: A list of chapters in ascending order

        """
        endpoint = f"series/{url_name}"
        result = await self.__request("GET", endpoint)
        chapters = result.get("chapters") or []
        chapters = [x for x in chapters if x.get("price", 0) == 0]
        if limit == 0:
            raise ValueError("limit must be greater than 0")
        elif limit < 0:
            return list(chapters)
        else:
            return list(chapters)[:limit]

    async def search(self, title: str, limit: Optional[int] = None) -> Dict[str, Any]:
        endpoint = "series/search"
        params = {"term": title}
        kwargs = {}
        if isinstance(self.manager.session, CachedClientSession):
            kwargs["cache_time"] = 0
        results = await self.__request("POST", endpoint, params=params, **kwargs)
        if limit is not None:
            results = list(results)[:limit]
        return results

    async def get_cover(self, url_name: str) -> Optional[str]:
        result = await self.get_manga(url_name)
        return result.get("thumbnail")

    async def get_status(self, url_name: str) -> Optional[str]:
        chapters = await self.get_chapters_list(url_name)
        if chapters:
            last_chapter = chapters[-1]
            release_date = datetime.fromisoformat(last_chapter["created_at"])
            if (
                    datetime.now().timestamp() - release_date.timestamp()
                    > self.manager.bot.config["constants"]["time-for-manga-to-be-considered-stale"]
            ):
                return "Completed"
            else:
                return "Ongoing"
