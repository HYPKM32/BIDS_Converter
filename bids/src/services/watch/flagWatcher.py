import os, json, logging
from globals import FLAG_DIR, BACKEND_URL
from ._watchEngine import BaseDirectoryEventHandler, start_watcher

logger = logging.getLogger(__name__)

class FlagWatcherHandler(BaseDirectoryEventHandler):
    """개선: 파일 생성 시에만 해당 파일 전송"""
    
    def on_created(self, event):
        # 디렉토리 이벤트 무시
        if event.is_directory:
            return
        
        # .json 파일만 처리
        if not event.src_path.endswith(".json"):
            return
        
        try:
            # 경로에서 process, package 추출
            # /flag/{process}/{package}/file.json
            rel = os.path.relpath(event.src_path, FLAG_DIR)
            parts = rel.split(os.sep)
            process = parts[0]
            package = parts[1] if len(parts) > 1 else None
            
            # 생성된 파일만 읽기
            with open(event.src_path, "r") as fp:
                file_content = json.load(fp)
            
            # 배열에 담아서 전송 (API 형식 유지)
            payload = {
                "process": process,
                "package": package,
                "flag_files": [file_content],
            }
            
            self.post_json("flag", payload)
            logger.info(f"[FlagWatcher] Sent new flag file: {event.src_path}")
            
        except Exception as e:
            logger.error(f"[FlagWatcher] Failed to process {event.src_path}: {e}")

def start_flag_watcher():
    start_watcher(FLAG_DIR, FlagWatcherHandler, recursive=True, backend_url=BACKEND_URL)