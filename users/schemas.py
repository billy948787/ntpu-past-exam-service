from typing import Optional

from pydantic import BaseModel, ConfigDict


class UserBase(BaseModel):
    username: str


class UserCreate(UserBase):
    hashed_password: str
    readable_name: str


class User(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: Optional[str]


class UserPreferencesUpdate(BaseModel):
    show_empty_courses: bool
    default_is_anonymous: bool
