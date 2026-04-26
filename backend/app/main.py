import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import create_all_tables
from app.routers.upload import router as upload_router
from app.routers.admin import router as admin_router
from app.routers.analysis_router import router as analysis_router
from app.services.cv_queue import queue_cv_from_path
from app.services.folder_monitor import CVFolderMonitor

from app.logging_config import setup_logging
setup_logging()

logger = logging.getLogger(__name__)

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

# Global folder monitor instance
folder_monitor = None


@app.on_event("startup")
def on_startup() -> None:
    global folder_monitor
    
    # Create database tables
    create_all_tables()
    
    # Start folder monitor for automatic CV processing
    watch_folder = Path("data/cvs")
    watch_folder.mkdir(parents=True, exist_ok=True)
    
    folder_monitor = CVFolderMonitor(
        watch_folder=watch_folder,
        callback=queue_cv_from_path,
        supported_extensions={".pdf"}
    )
    folder_monitor.start()
    logger.info(f"[STARTUP] Folder monitor started | watching: {watch_folder}")


@app.on_event("shutdown")
def on_shutdown() -> None:
    global folder_monitor
    
    if folder_monitor:
        folder_monitor.stop()
        logger.info("[SHUTDOWN] Folder monitor stopped")


app.include_router(upload_router)
app.include_router(admin_router)
app.include_router(analysis_router)


@app.get("/")
def read_root() -> dict[str, str]:
    return {"status": "TALASH backend is online"}


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"system": "healthy"}
