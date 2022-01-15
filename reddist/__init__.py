import asyncio
import dataclasses
import pickle
import typing as t
from abc import ABC, abstractmethod
from enum import Enum

import aiofiles
from aioredis import Redis
from asyncpraw import Reddit, models


@dataclasses.dataclass(init=False)
class RedditSubmissionBase:
    def __init__(self, **kwargs):
        names = set([f.name for f in dataclasses.fields(self)])
        {setattr(self, k, v) for (k, v) in kwargs.items() if k in names}


@dataclasses.dataclass(init=False)
class RedditSubmission(RedditSubmissionBase):
    title: str
    permalink: str
    url: str

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
        allowed_extensions: tuple[str] | t.Literal[False] | None = None,
        reddit_submission: RedditSubmissionBase | None = None,
    ) -> None:
        self._subreddits = subreddits or set()
        self._cache_refresh_time = cache_refresh_time or 60 * 60 * 6
        self._cached_posts_count = cached_posts_count or 100
        self._reddit = apraw_reddit_instance
        self._posts_sort_type = posts_sort_type or RedditSortType.HOT
        self._caching_started = False
        self._reddit_submission_object = reddit_submission or RedditSubmission

        if allowed_extensions is None:
            self._allowed_extensions = (".gif", ".png", ".jpg", ".jpeg", ".webp")
        elif not isinstance(allowed_extensions, t.Sequence):
            raise ValueError("allowed_extensions must be a sequence")
        elif allowed_extensions:
            self._allowed_extensions = allowed_extensions

    @property
    def is_caching(self) -> bool:
        return self._caching_started

    def start_caching(self) -> asyncio.Future:
        self._caching_started = True
        return asyncio.create_task(self._cache_loop())

    def stop_caching(self) -> None:
        self._caching_started = False

    async def _generate_subreddits_raw_cache(
        self, subreddits: list[str]
    ) -> dict[str, str]:
        subreddit_cache: tuple[dict[str, str]] = await asyncio.gather(
            *[
                self._generate_single_subreddit_cache(subreddit)
                for subreddit in subreddits
            ]
        )
        return subreddit_cache

    async def _generate_single_subreddit_cache(self, subreddit_name: str):
        subreddit: models.Subreddit = await self._reddit.subreddit(
            subreddit_name, fetch=True
        )
        func = getattr(subreddit, self._posts_sort_type.value)

        if self._allowed_extensions == False:
            return [
                self._reddit_submission_object(**vars(submission))
                async for submission in func(limit=self._cached_posts_count)
            ]

        post_count = 0
        submissions = []
        async for submission in func(limit=None):
            if post_count >= self._cached_posts_count:
                break
            if not submission.url.endswith(self._allowed_extensions):
                continue

            submissions.append(self._reddit_submission_object(**vars(submission)))
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
        **kwargs: dict[str, t.Any],
    ) -> None:
        super().__init__(apraw_reddit_instance, **kwargs)
        self._redis_instance = redis_instance

    async def get_subreddit_posts(self, subreddit_name: str) -> list[RedditSubmission]:
        subreddit_cache = await self._redis_instance.get(subreddit_name)
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


class PickleRedditCacher(RedditCacher):
    def __init__(
        self,
        apraw_reddit_instance: Reddit,
        cache_full_dir: str,
        **kwargs: dict[str, t.Any],
    ) -> None:
        super().__init__(apraw_reddit_instance, **kwargs)
        self._cache_full_dir = cache_full_dir

    async def get_subreddit_posts(self, subreddit_name: str) -> list[RedditSubmission]:
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
