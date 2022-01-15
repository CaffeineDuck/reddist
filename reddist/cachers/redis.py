import asyncio
import pickle
import typing as t

from aioredis import Redis
from asyncpraw import Reddit

from . import RedditCacherBase

_T = t.TypeVar("_T")


class RedisRedditCacher(RedditCacherBase):
    def __init__(
        self,
        apraw_reddit_instance: Reddit,
        redis_instance: Redis,
        **kwargs: dict[str, t.Any],
    ) -> None:
        super().__init__(apraw_reddit_instance, **kwargs)
        self._redis_instance = redis_instance

    async def get_subreddit_posts(
        self, subreddit_name: str, _return_type: type[_T] = None
    ) -> list[_T]:
        subreddit_cache = await self._redis_instance.get(f"r/{subreddit_name}")
        if not subreddit_cache:
            subreddit_cache = pickle.dumps(
                await self._generate_single_subreddit_cache(subreddit_name), 2
            )
            await self._redis_instance.set(
                f"r/{subreddit_name}", subreddit_cache, ex=self._cache_refresh_time
            )
            self._subreddits.add(subreddit_name)

        return pickle.loads(subreddit_cache)

    async def _generate_subreddits_cache(
        self, subreddits: list[str]
    ) -> dict[str, t.AnyStr]:
        raw_cache = await self._generate_subreddits_raw_cache(subreddits)
        processed_cache = {
            f"r/{subreddit_name}": pickle.dumps(posts, 2)
            for subreddit_name, posts in raw_cache.items()
        }
        return dict(zip(subreddits, processed_cache))

    async def _cache_loop(self) -> None:
        while self.__caching_started:
            subreddit_cache = await self._generate_subreddit_cache(self._subreddits)
            async with self._redis_instance.pipeline() as pipe:
                for subreddit_name, cache in subreddit_cache.items():
                    pipe.set(f"r/{subreddit_name}", cache, ex=self._cache_refresh_time)
                await pipe.execute()
            await asyncio.sleep(self._cache_refresh_time)
