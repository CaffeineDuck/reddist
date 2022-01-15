import asyncio
import pickle
import typing as t

import aiofiles
from asyncpraw import Reddit

from . import RedditCacherBase

_T = t.TypeVar("_T")


class PickleRedditCacher(RedditCacherBase):
    def __init__(
        self,
        apraw_reddit_instance: Reddit,
        cache_full_dir: str,
        **kwargs: dict[str, t.Any],
    ) -> None:
        super().__init__(
            apraw_reddit_instance, **kwargs
        )
        self._cache_full_dir = cache_full_dir

    async def get_subreddit_posts(self, subreddit_name: str) -> list[_T]:
        async with aiofiles.open(self._cache_full_dir, "wb+") as f:
            file_data = await f.read()
            prev_cache = pickle.loads(file_data) if file_data else {}

            if not (subreddit_cache := prev_cache.get(subreddit_name)):
                subreddit_cache = pickle.dumps(
                    await self._generate_single_subreddit_cache(subreddit_name), 2
                )

                prev_cache[subreddit_name] = subreddit_cache
                await f.write(pickle.dumps(prev_cache))

                self._subreddits.add(subreddit_name)

        return pickle.loads(subreddit_cache)

    async def _generate_subreddits_cache(
        self, subreddits: list[str]
    ) -> dict[str, t.AnyStr]:
        raw_cache = await self._generate_subreddits_raw_cache(subreddits)
        return dict(zip(subreddits, raw_cache))

    async def _cache_loop(self) -> None:
        while self._caching_started:
            subreddit_cache = await self._generate_subreddits_cache(self._subreddits)

            async with aiofiles.open(self._cache_full_dir, "wb+") as f:
                file_data = await f.read()
                prev_cache: dict = pickle.loads(file_data) if file_data else {}
                new_cache = prev_cache | subreddit_cache
                await f.write(pickle.dumps(new_cache, 2))

            await asyncio.sleep(self._cache_refresh_time)
