from fastapi import Depends, FastAPI
from fastapi.exception_handlers import http_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from starlette.exceptions import HTTPException

from auth.router import auth_middleware
from auth.router import router as auth_router
from bulletins.router import router as bulletins_router
from courses.router import router as courses_router
from departments.router import router as departments_router
from posts.router import router as posts_router
from sql import models
from sql.database import engine
from users.router import router as users_router
from utils.exception_handlers import (
    request_validation_exception_handler,
    unhandled_exception_handler,
)
from utils.log import log_request_middleware

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


models.Base.metadata.create_all(bind=engine)


app = FastAPI()


app.middleware("http")(log_request_middleware)
app.add_exception_handler(RequestValidationError, request_validation_exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

origins = [
    "https://past-exam.ntpu.cc",
    "https://past-exam.ntpu.xyz",
    "http://localhost",
    "http://localhost:3000",
    "http://localhost:8080",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(
    departments_router,
    tags=["Departments"],
    dependencies=[Depends(auth_middleware), Depends(oauth2_scheme)],
)
app.include_router(
    users_router,
    tags=["Users"],
    dependencies=[Depends(auth_middleware), Depends(oauth2_scheme)],
)
app.include_router(
    courses_router,
    tags=["Courses"],
    dependencies=[Depends(auth_middleware), Depends(oauth2_scheme)],
)
app.include_router(
    posts_router,
    tags=["Posts"],
    dependencies=[Depends(auth_middleware), Depends(oauth2_scheme)],
)

app.include_router(
    bulletins_router,
    tags=["Bulletins"],
    dependencies=[Depends(auth_middleware), Depends(oauth2_scheme)],
)
app.include_router(auth_router, tags=["Auth"])


@app.get("/ping", tags=["Health Check"])
def heartbeat():
    return "pong"
