from fastapi import FastAPI

from routers import users
from sql import models
from sql.database import engine
from static_file import r2

models.Base.metadata.create_all(bind=engine)


app = FastAPI()

app.include_router(users.router)


@app.get("/")
def get_all_content_in_r2():
    return r2.list_all_files()


@app.get("/ping")
def heartbeat():
    return "pong"
