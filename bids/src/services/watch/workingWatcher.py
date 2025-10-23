import os, json, logging
from globals import WORKING_DIR, BACKEND_URL
from ._watchEngine import BaseDirectoryEventHandler, start_watcher

logger = logging.getLogger(__name__)

class WorkingWatcherHandler(BaseDirectoryEventHandler):
    def on_created(self, event):
        if event.is_directory or not event.src_path.endswith(".json"):
            return

        json_path = event.src_path
        payload = {"file": json_path}

        try:
            with open(json_path, "r") as fp:
                payload["content"] = json.load(fp)
        except Exception as e:
            payload["content"] = f"Failed to read JSON: {e}"

        self.post_json("working", payload)

def start_working_watcher():
    start_watcher(WORKING_DIR, WorkingWatcherHandler, recursive=False, backend_url=BACKEND_URL)
