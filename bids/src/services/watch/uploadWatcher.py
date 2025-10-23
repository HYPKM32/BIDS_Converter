import os, time, logging
from globals import UPLOAD_DIR, BACKEND_URL
from ._watchEngine import BaseDirectoryEventHandler, start_watcher

logger = logging.getLogger(__name__)

class UploadWatcherHandler(BaseDirectoryEventHandler):
    def on_created(self, event):
        if event.is_directory:
            return
        if not event.src_path.endswith(".zip"):
            return

        # /upload/{user}/{subjectId}/{uploadTime}/file.zip
        parts = event.src_path.split(os.sep)
        try:
            user, subjectId, uploadTime = parts[-4], parts[-3], parts[-2]
        except IndexError:
            user, subjectId, uploadTime = None, None, None

        payload = {
            "user": user,
            "subjectId": subjectId,
            "uploadTime": uploadTime,
            "filename": os.path.basename(event.src_path),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }

        self.post_json("upload", payload)

def start_upload_watcher():
    start_watcher(UPLOAD_DIR, UploadWatcherHandler, recursive=True, backend_url=BACKEND_URL)
