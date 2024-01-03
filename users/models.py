from sqlalchemy import Boolean, Column, String

from sql.database import Base, BaseColumn


class User(Base, BaseColumn):
    __tablename__ = "users"

    email = Column(String(256))
    username = Column(String(256), unique=True)
    readable_name = Column(String(256), nullable=True, default=None)
    hashed_password = Column(String(256), nullable=True)
    school_department = Column(String(256))
    is_super_user = Column(Boolean, default=False)


class UserDepartment(Base, BaseColumn):
    __tablename__ = "users_departments"

    user_id = Column(String(256), index=True)
    department_id = Column(String(256), index=True)
    status = Column(String(256), default="PENDING", index=True)
    is_department_admin = Column(Boolean, default=False, index=True)
