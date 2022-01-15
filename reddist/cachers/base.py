import asyncio
import random
import typing as t
from abc import ABC, abstractmethod

from asyncpraw import Reddit, models

from ..utils import RedditSortType, RedditSubmission, RedditSubmissionBase

_T = t.TypeVar("_T")


class RedditCacherBase(ABC):
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

    async def get_random_post(
        self, subreddit_name: str, _return_type: type[_T] | None = None
    ) -> _T:
        return random.choice(await self.get_subreddit_posts(subreddit_name))

    @abstractmethod
    async def _generate_subreddits_cache(
        self, subreddits: list[str]
    ) -> dict[str, t.AnyStr]:
        ...

    @abstractmethod
    async def get_subreddit_posts(
        self, subreddit_name: str, _return_type: type[_T] | None = None
    ) -> list[_T]:
        ...

    @abstractmethod
    async def _cache_loop(self) -> None:
        ...
