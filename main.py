from fastapi import Depends, FastAPI
from fastapi.security import OAuth2PasswordBearer

from auth.router import auth_middleware
from auth.router import router as auth_router
from items.router import router as items_router
from posts.router import router as posts_router
from sql import models
from sql.database import engine
from users.router import router as users_router

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


models.Base.metadata.create_all(bind=engine)


app = FastAPI()


app.include_router(
    users_router,
    tags=["Users"],
    dependencies=[Depends(auth_middleware), Depends(oauth2_scheme)],
)
app.include_router(
    items_router,
    tags=["Items"],
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
