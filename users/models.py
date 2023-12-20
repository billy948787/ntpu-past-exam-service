import uuid

from sqlalchemy import Boolean, Column, String

from sql.database import Base


def generate_uuid():
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id = Column(String(256), primary_key=True, default=generate_uuid)
    email = Column(String(256))
    username = Column(String(256), unique=True)
    readable_name = Column(String(256), nullable=True, default=None)
    school_department = Column(String(256))
    is_super_user = Column(Boolean, default=False)


class UserDepartment(Base):
    __tablename__ = "users_departments"

    id = Column(String(256), primary_key=True, default=generate_uuid)
    user_id = Column(String(256), index=True)
    department_id = Column(String(256), index=True)
    status = Column(String(256), default="PENDING", index=True)
    is_department_admin = Column(Boolean, default=False, index=True)
