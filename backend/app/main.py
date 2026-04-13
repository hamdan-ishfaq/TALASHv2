import logging

from fastapi import FastAPI

from app.db import create_all_tables
from app.routers.upload import router as upload_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

app = FastAPI(title="TALASH API")


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
