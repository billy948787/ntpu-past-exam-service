from pydantic import BaseModel


class CategoryBase(BaseModel):
    name: str
    category: str


class CourseCreate(CategoryBase):
    pass


class Course(CategoryBase):
    id: str

    class Config:
        from_attributes = True
