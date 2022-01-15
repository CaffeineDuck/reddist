import dataclasses


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
