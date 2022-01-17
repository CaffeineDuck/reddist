import asyncio
import os
import random

import asyncpraw
from dotenv import load_dotenv

from reddist import MemoryRedditCacher, RedditSortType

load_dotenv()


class RedditCacher(MemoryRedditCacher):
    def __init__(
        self,
        subreddit: str,
        post_count: int,
        refresh_time: int,
        extensions: tuple[str],
        sort_type: RedditSortType,
    ) -> None:
        super().__init__(
            apraw_reddit_instance=asyncpraw.Reddit(
                client_id=os.environ.get("REDDIT_CLIENT_ID"),
                client_secret=os.environ.get("REDDIT_CLIENT_SECRET"),
                user_agent=os.environ.get("REDDIT_USER_AGENT"),
            ),
            cached_posts_count=post_count,
            cache_refresh_time=refresh_time,
            allowed_extensions=extensions,
            posts_sort_type=sort_type,
        )
        self.subreddit = subreddit

    async def main(self) -> None:
        posts = await self.get_subreddit_posts(self.subreddit)
        print(random.choice(posts))


if __name__ == "__main__":
    obj = RedditCacher(
        "pics",
        100,
        60,
        (".jpg", ".png", ".gif", ".jpeg"),
        RedditSortType.NEW,
    )
    loop = asyncio.get_event_loop()
    loop.run_until_complete(obj.main())
