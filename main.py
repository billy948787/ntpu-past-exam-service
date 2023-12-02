from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer

from auth.router import auth_middleware
from auth.router import router as auth_router
from courses.router import router as courses_router
from posts.router import router as posts_router
from sql import models
from sql.database import engine
from users.router import router as users_router

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


models.Base.metadata.create_all(bind=engine)


app = FastAPI()

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
app.include_router(auth_router, tags=["Auth"])


# @app.get("/")
# def get_all_content_in_r2():
#     return r2.list_all_files()


@app.get("/ping", tags=["Health Check"])
def heartbeat():
    return "pong"
