import uuid

from sqlalchemy import Column, String

from sql.database import Base


def generate_uuid():
    return str(uuid.uuid4())


class Item(Base):
    __tablename__ = "items"

    id = Column(String(256), primary_key=True, default=generate_uuid)
    title = Column(String(256), index=True)
    description = Column(String(256), index=True)
    owner_id = Column(String(256))
