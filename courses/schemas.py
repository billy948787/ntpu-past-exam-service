from pydantic import BaseModel, ConfigDict


class CategoryBase(BaseModel):
    name: str
    category: str


class CourseCreate(CategoryBase):
    pass


class Course(CategoryBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
