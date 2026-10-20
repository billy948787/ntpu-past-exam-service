from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi_cache.decorator import cache
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from auth.router import admin_middleware, super_user_middleware
from sql.database import get_db
from utils.cache import clear_namespace
from utils.token import get_access_token_payload

from . import dependencies, schemas

router = APIRouter(prefix="/users")


@router.get("", dependencies=[Depends(super_user_middleware)])
def read_users(
    is_active: bool = None,
    skip: Annotated[int, Query(ge=0, le=10000)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    db: Session = Depends(get_db),
):
    if is_active is not None:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="The is_active user field is no longer supported",
        )

    users = dependencies.get_users(db, skip=skip, limit=limit)
    data = []
    for user in users:
        u = jsonable_encoder(user)
        u.pop("hashed_password", None)
        data.append(u)
    return data


@router.get("/{user_id}")
def read_user(request: Request, user_id: str, db: Session = Depends(get_db)):
    is_me = user_id == "me"
    payload = get_access_token_payload(request)
    viewer_id: str = payload.get("id")
    if is_me:
        user_id = viewer_id

    if not dependencies.can_view_user_details(db, viewer_id, user_id):
        raise HTTPException(status_code=403, detail="Not allowed to view this user")

    db_user = dependencies.get_user(db, user_id=user_id)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    data = jsonable_encoder(db_user)
    data.pop("hashed_password", None)
    if is_me:
        pref = dependencies.get_user_preference(db, user_id)
        data["show_empty_courses"] = pref.show_empty_courses if pref else True
        data["default_is_anonymous"] = pref.default_is_anonymous if pref else False
    else:
        # Department admins only need profile and join-request information.
        data.pop("email", None)
        data.pop("is_super_user", None)
    return data


@router.get("/me/departments-admin")
@cache(expire=30, namespace="user-admin")
def read_user_admin_scopes(request: Request, db: Session = Depends(get_db)):
    payload = get_access_token_payload(request)
    user_id: str = payload.get("id")
    scopes = dependencies.get_user_department_admin(db, user_id=user_id)

    return scopes


@router.put("/update/me")
async def update_user_info(
    request: Request,
    major: Annotated[str, Form()],
    note: Annotated[str, Form()] = "",
    db: Session = Depends(get_db),
):
    payload = get_access_token_payload(request)
    user_id: str = payload.get("id")
    user = await run_in_threadpool(dependencies.get_user, db, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    await run_in_threadpool(
        dependencies.update_user,
        db,
        {
            "username": user.username,
            "readable_name": user.readable_name,
            "school_department": major,
            "email": user.email,
            "note": note,
        },
    )
    await clear_namespace("user-detail")
    await clear_namespace("verify-token")
    updated_user = await run_in_threadpool(dependencies.get_user, db, user_id)
    data = jsonable_encoder(updated_user)
    data.pop("hashed_password", None)
    pref = dependencies.get_user_preference(db, user_id)
    data["show_empty_courses"] = pref.show_empty_courses if pref else True
    data["default_is_anonymous"] = pref.default_is_anonymous if pref else False
    return data


@router.put("/me/preferences")
async def update_user_preferences(
    request: Request,
    preferences: schemas.UserPreferencesUpdate,
    db: Session = Depends(get_db),
):
    payload = get_access_token_payload(request)
    user_id: str = payload.get("id")
    pref = await run_in_threadpool(
        dependencies.update_user_preference,
        db,
        user_id,
        preferences.show_empty_courses,
        preferences.default_is_anonymous,
    )
    await clear_namespace("user-detail")
    await clear_namespace("verify-token")
    return {
        "show_empty_courses": pref.show_empty_courses if pref else True,
        "default_is_anonymous": pref.default_is_anonymous if pref else False,
    }


@router.put(
    "/status/{department_id}/{user_id}", dependencies=[Depends(admin_middleware)]
)
async def update_user_active_status(
    is_active: Annotated[bool, Form()], department_id: str, user_id: str
):
    del is_active, department_id, user_id
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="Global user status is no longer supported",
    )


@router.put(
    "/admin/{department_id}/{user_id}", dependencies=[Depends(admin_middleware)]
)
async def update_user_admin_status(
    is_admin: Annotated[bool, Form()], department_id: str, user_id: str
):
    del is_admin, user_id
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail=f"Use /departments/{department_id}/admin instead",
    )
