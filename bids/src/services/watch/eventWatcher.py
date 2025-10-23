import os, json, logging
from globals import EVENT_DIR, BACKEND_URL
from ._watchEngine import BaseDirectoryEventHandler, start_watcher

logger = logging.getLogger(__name__)

class EventWatcherHandler(BaseDirectoryEventHandler):
    def on_any_event(self, event):
        if event.is_directory:
            return

        # 폴더 내 모든 json 수집
        json_files = [f for f in os.listdir(EVENT_DIR) if f.endswith(".json")]
        payload = {"event_files": []}

        for jf in json_files:
            try:
                with open(os.path.join(EVENT_DIR, jf), "r") as fp:
                    payload["event_files"].append(json.load(fp))
            except Exception as e:
                logger.error(f"[EventWatcher] Failed to read {jf}: {e}")

        if not payload["event_files"]:
            payload["event_files"] = "no event files"

        self.post_json("event", payload)

def start_event_watcher():
    start_watcher(EVENT_DIR, EventWatcherHandler, recursive=False, backend_url=BACKEND_URL)
