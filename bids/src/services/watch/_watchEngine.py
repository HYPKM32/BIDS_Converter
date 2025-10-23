import os
import time
import json
import logging
import requests
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

logger = logging.getLogger(__name__)

class BaseDirectoryEventHandler(FileSystemEventHandler):
    """모든 Watcher의 공통 베이스"""
    def __init__(self, backend_url):
        super().__init__()
        self.backend_url = backend_url.rstrip("/")

    def post_json(self, endpoint, payload):
        """공통 POST 함수"""
        try:
            url = f"{self.backend_url}/{endpoint.lstrip('/')}"
            r = requests.post(url, json=payload, timeout=5)
            r.raise_for_status()
            logger.info(f"[Watcher POST] {endpoint} OK: {payload}")
        except Exception as e:
            logger.error(f"[Watcher POST] Failed ({endpoint}): {e}")

def start_watcher(path, handler_cls, recursive=False, *args, **kwargs):
    """공통 감시 루프"""
    if not os.path.exists(path):
        logger.warning(f"[Watcher] Path not found: {path}")
        return

    observer = Observer()
    handler = handler_cls(*args, **kwargs)
    observer.schedule(handler, path, recursive=recursive)
    observer.start()
    logger.info(f"[Watcher] Watching {path} ({handler_cls.__name__}, recursive={recursive})")

    try:
        while True:
            time.sleep(3)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
