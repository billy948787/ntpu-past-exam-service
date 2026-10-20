from sqlalchemy import Boolean, Column, ForeignKey, String, Text

from sql.database import Base, BaseColumn


class User(Base, BaseColumn):
    __tablename__ = "users"

    email = Column(String(256))
    # Production PostgreSQL already represents this as a unique index. Keeping
    # the model explicit prevents Alembic from trying to replace an equivalent
    # index with a table-level unique constraint on every schema check.
    username = Column(String(256), unique=True, index=True)
    readable_name = Column(String(256), nullable=True, default=None)
    note = Column(Text(), nullable=True, default=None)
    hashed_password = Column(String(256), nullable=True)
    school_department = Column(String(256))
    is_super_user = Column(Boolean, default=False)


class UserPreference(Base, BaseColumn):
    __tablename__ = "user_preferences"

    user_id = Column(
        String(256), ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True, nullable=False
    )
    show_empty_courses = Column(Boolean, default=True, nullable=False)
    default_is_anonymous = Column(Boolean, default=False, nullable=False)


class UserDepartment(Base, BaseColumn):
    __tablename__ = "users_departments"

    user_id = Column(String(256), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    department_id = Column(String(256), ForeignKey("departments.id", ondelete="CASCADE"), index=True)
    status = Column(
        String(256), default="PENDING", server_default="PENDING", index=True
    )
    is_department_admin = Column(Boolean, default=False, index=True)
