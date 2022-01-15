from enum import Enum


class RedditSortType(str, Enum):
    NEW = "new"
    TOP = "top"
    HOT = "hot"
    CONTROVERSIAL = "controversial"
    RISING = "rising"
