from fastapi import FastAPI

from items.router import router as items_router
from sql import models
from sql.database import engine
from static_file import r2
from users.router import router as users_router

models.Base.metadata.create_all(bind=engine)


app = FastAPI()

app.include_router(users_router)
app.include_router(items_router)


@app.get("/")
def get_all_content_in_r2():
    return r2.list_all_files()


@app.get("/ping")
def heartbeat():
    return "pong"
