import uuid

from sqlalchemy import Column, String, Text

from sql.database import Base


def generate_uuid():
    return str(uuid.uuid4())


class Bulletin(Base):
    __tablename__ = "bulletins"

    id = Column(String(256), primary_key=True, default=generate_uuid)
    title = Column(String(256))
    content = Column(Text)
    department_id = Column(String(256), index=True)
