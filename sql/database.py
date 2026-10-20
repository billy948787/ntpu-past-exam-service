import os
import uuid

from dotenv import load_dotenv
from sqlalchemy import URL, Column, DateTime, String, create_engine, func
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()


SQLALCHEMY_DATABASE_URL = URL.create(
    drivername=os.getenv("DATABASE_DRIVER", "postgresql+psycopg"),
    username=os.getenv("DATABASE_USERNAME"),
    password=os.getenv("DATABASE_PASSWORD"),
    host=os.getenv("DATABASE_HOST"),
    port=int(os.getenv("DATABASE_PORT", "5432")),
    database=os.getenv("DATABASE"),
).render_as_string(hide_password=False)

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def generate_uuid():
    return str(uuid.uuid4())


class BaseColumn(object):  # pylint: disable=useless-object-inheritance
    id = Column(String(256), primary_key=True, default=generate_uuid)
    create_time = Column(
        DateTime(timezone=True),
        server_default=func.now(),  # pylint: disable=not-callable
    )
    updated_time = Column(
        DateTime(timezone=True),
        onupdate=func.now(),  # pylint: disable=not-callable
    )


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
