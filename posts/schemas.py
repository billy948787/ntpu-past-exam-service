from pydantic import BaseModel


class PostBase(BaseModel):
    title: str
    content: str
    course_id: str


class Post(PostBase):
    id: str
    owner_id: int
    # files: List[str]
