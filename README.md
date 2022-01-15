# Reddist

Just a python library to make reddit post caching easier.


## Caching Options
1. In Memory Caching
2. Redis Caching
3. Pickle Caching

## Usage

### Installation:

- Developement
```sh
poetry add git+https://github.com/CaffeineDuck/reddist
```

- Stable
```sh
poetry add reddist
```

### Pickle Usage:

```py
import asyncio
import random
from dataclasses import asdict

async def main():
    reddit_cacher = PickleRedditCacher(
            Reddit(
                user_agent="dpydit",
                client_id="CLIENT_ID",
                client_secret="CLIENT_SECRET",
            ),
            'cache.pickle',
            cached_posts_count=100,
        )

    reddit_cacher.start_caching()
    posts = await reddit_cacher.get_subreddit_posts("pics")
    print(asdict(random.choice(posts)))

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
```

### Memory Usage:

```py
import asyncio
import random
from dataclasses import asdict

async def main():
    reddit_cacher = MemoryRedditCacher(
            Reddit(
                user_agent="dpydit",
                client_id="CLIENT_ID",
                client_secret="CLIENT_SECRET",
            ),
            cached_posts_count=100,
        )

    reddit_cacher.start_caching()
    posts = await reddit_cacher.get_subreddit_posts("pics")
    print(asdict(random.choice(posts)))

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
```

### Redis Usage:

```py
import asyncio
import random
from dataclasses import asdict

import aioredis

async def main():
    redis = aioredis.from_url(
        "redis://localhost"
    )
    async with redis.client() as conn:
        reddit_cacher = RedisRedditCacher(
            Reddit(
                user_agent="dpydit",
                client_id="CLIENT_ID",
                client_secret="CLIENT_SECRET",
            ),
            conn,
            cached_posts_count=100
        )
        posts = await reddit_cacher.get_subreddit_posts("pics")
        print(asdict(random.choice(posts)))

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
```

## WIP (Expect Breaking Changes)