from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from database.connection import create_db_and_tables
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from routers.auth import authentication
from routers.user import users


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield


app = FastAPI(lifespan=lifespan)

origins = [
    "http://localhost",
    "http://localhost:3000",
    "http://localhost:8080",
    "https://dashboard-kraliknorbert.azurewebsites.net",
    "https://dashboard.kraliknorbert.com/",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(authentication.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
