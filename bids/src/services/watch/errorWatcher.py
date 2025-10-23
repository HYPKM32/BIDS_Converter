import os, json, logging, time
from globals import ERROR_DIR, BACKEND_URL
from ._watchEngine import BaseDirectoryEventHandler, start_watcher

logger = logging.getLogger(__name__)

class ErrorWatcherHandler(BaseDirectoryEventHandler):
    def on_created(self, event):
        if event.is_directory or not event.src_path.endswith(".json"):
            return

        json_path = event.src_path
        base_name = os.path.splitext(os.path.basename(json_path))[0]
        log_path = os.path.join(ERROR_DIR, f"{base_name}_error.log")

        # log 파일이 생성될 때까지 대기 (최대 5초)
        for _ in range(10):
            if os.path.exists(log_path):
                break
            time.sleep(0.5)

        payload = {"json_file": json_path}
        try:
            with open(json_path, "r") as fp:
                payload["json_content"] = json.load(fp)
        except Exception as e:
            payload["json_content"] = f"Failed to load: {e}"

        if os.path.exists(log_path):
            try:
                with open(log_path, "r") as lp:
                    payload["log_content"] = lp.read()
            except Exception as e:
                payload["log_content"] = f"Failed to load log: {e}"
        else:
            payload["log_content"] = "log file not found"

        self.post_json("error", payload)

def start_error_watcher():
    start_watcher(ERROR_DIR, ErrorWatcherHandler, recursive=False, backend_url=BACKEND_URL)
