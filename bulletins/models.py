from sqlalchemy import Column, String, Text

from sql.database import Base, BaseColumn


class Bulletin(Base, BaseColumn):
    __tablename__ = "bulletins"

    title = Column(String(256))
    content = Column(Text)
    department_id = Column(String(256), index=True)
