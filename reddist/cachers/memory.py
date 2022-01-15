import asyncio
import typing as t

from asyncpraw import Reddit

from . import RedditCacherBase

_T = t.TypeVar("_T")


class MemoryRedditCacher(RedditCacherBase):
    def __init__(
        self,
        apraw_reddit_instance: Reddit,
        **kwargs
    ) -> None:
        super().__init__(
            apraw_reddit_instance, **kwargs
        )
        self._subreddit_cache = {}

    async def get_subreddit_posts(self, subreddit_name: str) -> list[_T]:
        if subreddit_name not in self._subreddit_cache:
            subreddit_cache = await self._generate_single_subreddit_cache(
                subreddit_name
            )
            self._subreddit_cache[subreddit_name] = subreddit_cache
            self._subreddits.add(subreddit_name)

        return self._subreddit_cache[subreddit_name]

    async def _generate_subreddits_cache(
        self, subreddits: list[str]
    ) -> dict[str, t.AnyStr]:
        raw_cache = await self._generate_subreddits_raw_cache(subreddits)
        return dict(zip(subreddits, raw_cache))

    async def _cache_loop(self) -> None:
        while self.__caching_started:
            subreddit_cache = await self._generate_subreddit_cache(self._subreddits)
            self._subreddit_cache.update(subreddit_cache)
            await asyncio.sleep(self._cache_refresh_time)
