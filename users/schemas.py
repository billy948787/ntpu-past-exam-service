from typing import Optional

from pydantic import BaseModel

from items.schemas import Item


class UserBase(BaseModel):
    username: str


class UserCreate(UserBase):
    hashed_password: str


class User(UserBase):
    id: str
    email: Optional[str]
    is_active: bool
    items: list[Item] = []

    class Config:
        from_attributes = True
