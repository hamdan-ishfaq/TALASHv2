import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import create_all_tables
from app.routers.upload import router as upload_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

app = FastAPI(title="TALASH API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    create_all_tables()


app.include_router(upload_router)


@app.get("/")
def read_root() -> dict[str, str]:
    return {"status": "TALASH backend is online"}


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"system": "healthy"}
