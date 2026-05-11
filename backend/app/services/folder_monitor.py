"""
Folder-based CV monitoring service using Watchdog.
Automatically detects new PDF files and queues them for processing.
"""

import logging
from pathlib import Path
from typing import Callable, Optional

from watchdog.events import FileSystemEventHandler, FileModifiedEvent, FileCreatedEvent
from watchdog.observers import Observer

logger = logging.getLogger(__name__)


class CVFolderEventHandler(FileSystemEventHandler):
    """
    Watches a folder for new/modified PDF files and triggers processing.
    """

    def __init__(self, callback: Callable[[str], None], supported_extensions: set[str] = None):
        """
        Args:
            callback: Function to call when a CV file is detected. Receives file path.
            supported_extensions: Set of file extensions to monitor (default: {'.pdf'})
        """
        super().__init__()
        self.callback = callback
        self.supported_extensions = supported_extensions or {".pdf"}
        self.processed_files = set()  # Track processed files to avoid duplicates

    def on_created(self, event: FileCreatedEvent) -> None:
        """Triggered when a new file is created."""
        if event.is_directory:
            return
        
        self._process_file(event.src_path, "created")

    def on_modified(self, event: FileModifiedEvent) -> None:
        """Triggered when a file is modified (fallback for incomplete uploads)."""
        if event.is_directory:
            return
        
        self._process_file(event.src_path, "modified")

    def _process_file(self, file_path: str, event_type: str) -> None:
        """Process a file if it matches criteria."""
        try:
            path = Path(file_path)
            
            # Check if file has supported extension
            if path.suffix.lower() not in self.supported_extensions:
                return
            
            # Check if file is still being written (size stable for 1+ second)
            if not self._is_file_ready(path):
                logger.debug(f"File not ready yet: {path.name}")
                return
            
            # Avoid reprocessing the same file (include mtime so same-size replacements re-queue)
            st = path.stat()
            file_id = (path.name, st.st_size, int(st.st_mtime))
            if file_id in self.processed_files:
                logger.debug(f"File already processed: {path.name}")
                return
            
            self.processed_files.add(file_id)
            logger.info(f"CV file detected ({event_type}): {path.name}")
            
            # Trigger callback
            self.callback(str(path))
        
        except Exception as e:
            logger.error(f"Error processing file event: {str(e)}")

    @staticmethod
    def _is_file_ready(file_path: Path, timeout_seconds: int = 2) -> bool:
        """
        Check if file is ready for processing (not being written).
        Verifies that file size is stable.
        """
        import time
        
        try:
            if not file_path.exists():
                return False
            
            initial_size = file_path.stat().st_size
            time.sleep(0.5)
            
            # File is ready if size hasn't changed
            final_size = file_path.stat().st_size
            is_ready = initial_size == final_size
            
            if not is_ready:
                logger.debug(f"File still being written: {file_path.name} ({initial_size} → {final_size} bytes)")
            
            return is_ready
        
        except Exception as e:
            logger.warning(f"Error checking file ready status: {str(e)}")
            return False


class CVFolderMonitor:
    """
    Manager for folder-based CV monitoring.
    Starts/stops watchdog observer for automated CV detection.
    """

    def __init__(self, watch_folder: str, callback: Callable[[str], None], supported_extensions: set[str] = None):
        """
        Args:
            watch_folder: Path to folder to monitor for CVs
            callback: Function to call when CV file detected (receives file path)
            supported_extensions: File extensions to monitor (default: {'.pdf'})
        """
        self.watch_folder = Path(watch_folder)
        self.callback = callback
        self.supported_extensions = supported_extensions or {".pdf"}
        self.observer: Optional[Observer] = None
        self._is_running = False
        
        if not self.watch_folder.exists():
            self.watch_folder.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created watch folder: {self.watch_folder}")

    def start(self) -> None:
        """Start monitoring the folder."""
        if self._is_running:
            logger.warning(f"Monitor already running for {self.watch_folder}")
            return
        
        try:
            event_handler = CVFolderEventHandler(self.callback, self.supported_extensions)
            
            self.observer = Observer()
            self.observer.schedule(event_handler, str(self.watch_folder), recursive=False)
            self.observer.start()
            
            self._is_running = True
            logger.info(f"Started monitoring folder: {self.watch_folder}")
        
        except Exception as e:
            logger.error(f"Failed to start folder monitor: {str(e)}")
            self._is_running = False

    def stop(self) -> None:
        """Stop monitoring the folder."""
        if not self._is_running:
            logger.warning("Monitor not running")
            return
        
        try:
            if self.observer:
                self.observer.stop()
                self.observer.join(timeout=5)
            
            self._is_running = False
            logger.info(f"Stopped monitoring folder: {self.watch_folder}")
        
        except Exception as e:
            logger.error(f"Error stopping folder monitor: {str(e)}")

    def is_running(self) -> bool:
        """Check if monitor is active."""
        return self._is_running and self.observer is not None and self.observer.is_alive()
