import asyncio
import os

import aioredis
import asyncpraw
from dotenv import load_dotenv

from reddist import RedisRedditCacher

load_dotenv()


async def main() -> None:
    redis = aioredis.from_url("redis://localhost")

    async with redis.client() as conn:
        reddit_cacher = RedisRedditCacher(
            apraw_reddit_instance=asyncpraw.Reddit(
                client_id=os.environ.get("REDDIT_CLIENT_ID"),
                client_secret=os.environ.get("REDDIT_CLIENT_SECRET"),
                user_agent=os.environ.get("REDDIT_USER_AGENT"),
            ),
            redis_instance=conn,
            cached_posts_count=100,
        )

        posts = await reddit_cacher.get_random_post("pics")
        print(posts)


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
