from pydantic import BaseModel


class MRAttributes(BaseModel):
    model_config = {"extra": "ignore"}

    action: str
    state: str
    title: str
    url: str


class Commit(BaseModel):
    model_config = {"extra": "ignore"}

    message: str


class GitLabMRPayload(BaseModel):
    model_config = {"extra": "ignore"}

    object_attributes: MRAttributes
    commits: list[Commit] = []
