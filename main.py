from fastapi import FastAPI

from routers import users
from sql import models
from sql.database import engine

models.Base.metadata.create_all(bind=engine)


app = FastAPI()

app.include_router(users.router)
