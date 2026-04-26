import logging
import logging.handlers
import os
import sys
from pathlib import Path

def setup_logging():
    """
    Configure centralized, highly detailed logging for TALASH.
    Logs are written to standard output (for Docker) and to a rotating file in backend/logs/.
    """
    # Create logs directory if it doesn't exist
    log_dir = Path("/app/logs") if os.path.exists("/app") else Path("logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    
    log_file = log_dir / "talash_system.log"

    # Define the detailed format
    # Example: 2026-04-26 14:09:03,123 | INFO     | app.main:42 | [Module] Message
    log_format = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Prevent adding handlers multiple times if imported multiple times
    if root_logger.handlers:
        root_logger.handlers.clear()

    # 1. Console Handler (for Docker logs)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(log_format)
    root_logger.addHandler(console_handler)

    # 2. File Handler (Rotating log file, max 10MB per file, keeps 5 backups)
    try:
        file_handler = logging.handlers.RotatingFileHandler(
            filename=log_file,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
            encoding="utf-8"
        )
        file_handler.setLevel(logging.DEBUG)  # File gets more detailed logs if modules emit them
        file_handler.setFormatter(log_format)
        root_logger.addHandler(file_handler)
    except Exception as e:
        print(f"Warning: Could not set up file logging: {e}")

    # Set specific libraries to WARNING to avoid log spam
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    
    logging.info("=" * 80)
    logging.info("TALASH Centralized Logging Initialized")
    logging.info("=" * 80)
