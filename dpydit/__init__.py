import asyncio
import pickle
import typing as t
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

from aioredis import Redis
from asyncpraw import Reddit


@dataclass
class RedditSubmission:
    image_url: str | None
    title: str
    permalink: str


class RedditSortType(str, Enum):
    NEW = "new"
    TOP = "top"
    HOT = "hot"
    CONTROVERSIAL = "controversial"
    RISING = "rising"


class RedditCacher(ABC):
    def __init__(
        self,
        apraw_reddit_instance: Reddit,
        cached_posts_count: int | None = None,
        subreddits: set[str] | None = None,
        cache_refresh_time: int | None = None,
        posts_sort_type: RedditSortType | None = None,
        allowed_extensions: tuple[str] | None = None,
    ) -> None:
        self._subreddits = subreddits or set()
        self._cache_refresh_time = cache_refresh_time or 60 * 60 * 6
        self._cached_posts_count = cached_posts_count or 100
        self._reddit = apraw_reddit_instance
        self._posts_sort_type = posts_sort_type or RedditSortType.HOT
        self._allowed_extensions = allowed_extensions or (
            ".gif",
            ".png",
            ".jpg",
            ".jpeg",
        )
        self.__caching_started = False

    def start_caching(self) -> None:
        self.__caching_started = True
        asyncio.create_task(self._cache_loop())

    def stop_caching(self) -> None:
        self.__caching_started = False

    async def _generate_subreddits_raw_cache(
        self, subreddits: list[str]
    ) -> dict[str, str]:
        subreddit_cache: tuple[dict[str, str]] = await asyncio.gather(
            *[
                self._generate_single_subreedit_cache(subreddit)
                for subreddit in subreddits
            ]
        )
        return subreddit_cache

    async def _generate_single_subreddit_cache(self, subreddit_name: str):
        subreddit = await self._reddit.subreddit(subreddit_name, fetch=True)

        func = getattr(subreddit, self._posts_sort_type.value)

        post_count = 0
        submissions = []
        async for submission in func(limit=None):
            if post_count >= self._cached_posts_count:
                break
            if not submission.url.endswith(self._allowed_extensions):
                continue

            submissions.append(
                RedditSubmission(
                    image_url=submission.url,
                    title=submission.title,
                    permalink=submission.permalink,
                )
            )
            post_count += 1

        return submissions

    @abstractmethod
    async def _generate_subreddits_cache(
        self, subreddits: list[str]
    ) -> dict[str, t.AnyStr]:
        ...

    @abstractmethod
    async def get_subreddit_posts(self, subreddit_name: str) -> list[RedditSubmission]:
        ...

    @abstractmethod
    async def _cache_loop(self) -> None:
        ...


class RedisRedditCacher(RedditCacher):
    def __init__(
        self,
        apraw_reddit_instance: Reddit,
        redis_instance: Redis,
        **kwargs: dict[str, t.Any]
    ) -> None:
        super().__init__(apraw_reddit_instance, **kwargs)
        self._redis_instance = redis_instance

    async def get_subreddit_posts(self, subreddit_name: str) -> list[RedditSubmission]:
        subreddit_cache = await self._redis_instance.get(subreddit_name)
        if not subreddit_cache:
            subreddit_cache = pickle.dumps(
                await self._generate_single_subreddit_cache(subreddit_name)
            )
            await self._redis_instance.set(subreddit_name, subreddit_cache)
            self._subreddits.add(subreddit_name)

        return pickle.loads(subreddit_cache)

    async def _generate_subreddits_cache(
        self, subreddits: list[str]
    ) -> dict[str, t.AnyStr]:
        raw_cache = await self._generate_subreddits_raw_cache(subreddits)
        processed_cache = {
            subreddit_name: pickle.dumps(posts)
            for subreddit_name, posts in raw_cache.items()
        }
        return dict(zip(subreddits, processed_cache))

    async def _cache_loop(self) -> None:
        while self.__caching_started:
            subreddit_cache = await self._generate_subreddit_cache(self._subreddits)
            await self._redis_instance.mset(subreddit_cache)
            await asyncio.sleep(self._cache_refresh_time)


class MemoryRedditCacher(RedditCacher):
    def __init__(
        self, apraw_reddit_instance: Reddit, **kwargs: dict[str, t.Any]
    ) -> None:
        super().__init__(apraw_reddit_instance, **kwargs)
        self._subreddit_cache: t.Dict[str, list[RedditSubmission]] = {}

    async def get_subreddit_posts(self, subreddit_name: str) -> list[RedditSubmission]:
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
