from typing import Optional

from pydantic import BaseModel


class UserBase(BaseModel):
    username: str


class UserCreate(UserBase):
    hashed_password: str
    readable_name: str


class User(UserBase):
    id: str
    email: Optional[str]
    is_active: bool
    is_admin: bool

    class Config:
        from_attributes = True
