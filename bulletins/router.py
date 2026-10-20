from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi_cache.decorator import cache
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from auth.router import admin_middleware
from departments import dependencies as department_dependencies
from sql.database import get_db
from utils.cache import clear_namespace
from utils.token import get_access_token_payload

from . import dependencies

router = APIRouter(prefix="/bulletins")


@router.get("")
@cache(expire=60, namespace="bulletins")
def get_all_bulletins(
    request: Request,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    user_id = get_access_token_payload(request).get("id")
    visible_department_ids = department_dependencies.get_viewable_departments_ids(
        db, user_id
    )
    items = dependencies.get_bulletins(
        db,
        visible_department_ids=visible_department_ids,
        skip=skip,
        limit=limit,
    )
    return items


@router.get("/{bulletin_id}")
@cache(expire=60, namespace="bulletins")
def get_single_bulletin(
    request: Request,
    bulletin_id: str,
    db: Session = Depends(get_db),
):
    data = dependencies.get_db_bulletin(db, bulletin_id)

    if data is None:
        raise HTTPException(status_code=404, detail="Bulletin not found")

    user_id = get_access_token_payload(request).get("id")
    department_dependencies.require_viewable_department(
        db,
        user_id=user_id,
        department_id=data.department_id,
    )

    return jsonable_encoder(data)


@router.post("/{department_id}", dependencies=[Depends(admin_middleware)])
async def create_bulletin(
    department_id: str,
    title: Annotated[str, Form()],
    content: Annotated[str, Form()],
    db: Session = Depends(get_db),
):
    bulletin = {"title": title, "content": content, "department_id": department_id}
    bulletin = await run_in_threadpool(dependencies.make_db_bulletin, db, bulletin)
    await clear_namespace("bulletins")
    await clear_namespace("dept-bulletins")
    return jsonable_encoder(bulletin)
