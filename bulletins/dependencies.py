from typing import Dict

from sqlalchemy.orm import Session

from . import models


def get_bulletins(
    db: Session,
    visible_department_ids: list[str],
    skip: int = 0,
    limit: int = 100,
):
    if not visible_department_ids:
        return []

    normalized_skip = min(max(skip, 0), 10000)
    normalized_limit = max(1, min(limit, 100))
    return (
        db.query(models.Bulletin)
        .filter(models.Bulletin.department_id.in_(visible_department_ids))
        .offset(normalized_skip)
        .limit(normalized_limit)
        .all()
    )


def get_db_bulletin(db: Session, bulletin_id: str):
    bulletin = (
        db.query(models.Bulletin).filter(models.Bulletin.id == bulletin_id).first()
    )

    return bulletin


def make_db_bulletin(db: Session, bulletin: Dict):
    db_bulletin = models.Bulletin(**bulletin)
    db.add(db_bulletin)
    db.commit()
    db.refresh(db_bulletin)
    return db_bulletin
