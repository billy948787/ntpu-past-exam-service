from pydantic import BaseModel

from items.schemas import Item


class UserBase(BaseModel):
    email: str


class UserCreate(UserBase):
    password: str


class User(UserBase):
    id: str
    is_active: bool
    items: list[Item] = []

    class Config:
        from_attributes = True
