from sqlalchemy import Column, String

from sql.database import Base, BaseColumn


class Course(Base, BaseColumn):
    __tablename__ = "courses"

    name = Column(String(256))
    category = Column(String(256))
    department_id = Column(String(256), index=True)
