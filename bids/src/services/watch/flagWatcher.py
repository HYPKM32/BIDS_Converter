import os, json, logging
from globals import FLAG_DIR, BACKEND_URL
from ._watchEngine import BaseDirectoryEventHandler, start_watcher

logger = logging.getLogger(__name__)

class FlagWatcherHandler(BaseDirectoryEventHandler):
    def on_any_event(self, event):
        if event.is_directory:
            return
        if not event.src_path.endswith(".json"):
            return

        # /flag/{process}/{package}/file.json
        rel = os.path.relpath(event.src_path, FLAG_DIR)
        parts = rel.split(os.sep)
        process, package = parts[0], parts[1] if len(parts) > 1 else None

        target_dir = os.path.join(FLAG_DIR, process, package)
        json_files = [f for f in os.listdir(target_dir) if f.endswith(".json")]
        payload = {
            "process": process,
            "package": package,
            "flag_files": [],
        }

        for jf in json_files:
            try:
                with open(os.path.join(target_dir, jf), "r") as fp:
                    payload["flag_files"].append(json.load(fp))
            except Exception as e:
                logger.error(f"[FlagWatcher] Failed to read {jf}: {e}")

        if not payload["flag_files"]:
            payload["flag_files"] = "no flag files"

        self.post_json("flag", payload)

def start_flag_watcher():
    start_watcher(FLAG_DIR, FlagWatcherHandler, recursive=True, backend_url=BACKEND_URL)
