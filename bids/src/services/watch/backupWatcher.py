import os, json, logging
from globals import BACKUP_DIR, BACKEND_URL
from ._watchEngine import BaseDirectoryEventHandler, start_watcher

logger = logging.getLogger(__name__)

class BackupWatcherHandler(BaseDirectoryEventHandler):
    """개선: JSON 파일 내용도 함께 전송"""
    
    def on_created(self, event):
        # 디렉토리면 무시
        if event.is_directory:
            return
        
        # .json 파일만 처리
        if not event.src_path.endswith(".json"):
            return

        try:
            # 경로: /BDSP/interfaces/backup/{systemId}/file.json
            rel_path = os.path.relpath(event.src_path, BACKUP_DIR)
            parts = rel_path.split(os.sep)
            system_id = parts[0] if len(parts) > 1 else "unknown"

            # JSON 파일 내용 읽기
            with open(event.src_path, "r") as fp:
                content = json.load(fp)

            payload = {
                "systemId": system_id,
                "filename": os.path.basename(event.src_path),
                "path": event.src_path,
                "content": content,  # 👈 파일 내용 추가!
            }

            self.post_json("backup", payload)
            logger.info(f"[BackupWatcher] Detected new backup file: {event.src_path}")
        
        except json.JSONDecodeError as e:
            logger.error(f"[BackupWatcher] Invalid JSON in {event.src_path}: {e}")
        except Exception as e:
            logger.error(f"[BackupWatcher] Failed to process {event.src_path}: {e}")

def start_backup_watcher():
    """백업 디렉토리 감시 시작 (모든 systemId 하위 폴더 포함)"""
    start_watcher(BACKUP_DIR, BackupWatcherHandler, recursive=True, backend_url=BACKEND_URL)