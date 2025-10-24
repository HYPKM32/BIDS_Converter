import os, json, logging, time, hashlib
from globals import EVENT_DIR, BACKEND_URL
from ._watchEngine import BaseDirectoryEventHandler, start_watcher

logger = logging.getLogger(__name__)

class EventWatcherHandler(BaseDirectoryEventHandler):
    """개선: 중복 전송 방지 (시간 필터 + 내용 해시 필터)"""
    
    def __init__(self, backend_url):
        super().__init__(backend_url)
        self.last_send_time = 0  # 마지막 전송 시간
        self.last_content_hash = None  # 마지막 내용 해시
        self.cooldown = 1.0  # 1초 쿨다운
    
    def _calculate_content_hash(self, json_files):
        """event_files 내용으로 해시 생성"""
        # JSON을 정렬된 문자열로 변환
        content_str = json.dumps(json_files, sort_keys=True)
        # MD5 해시 계산
        return hashlib.md5(content_str.encode()).hexdigest()
    
    def on_any_event(self, event):
        # 디렉토리 이벤트 무시
        if event.is_directory:
            return
        
        # 1단계 필터: 시간 기반 중복 방지 (1초 쿨다운)
        now = time.time()
        if now - self.last_send_time < self.cooldown:
            logger.debug(f"[EventWatcher] Cooldown active, skipping event")
            return
        
        # EVENT_DIR 내 모든 json 파일 수집
        json_files = []
        try:
            files = [f for f in os.listdir(EVENT_DIR) if f.endswith(".json")]
            
            for jf in files:
                try:
                    with open(os.path.join(EVENT_DIR, jf), "r") as fp:
                        json_files.append(json.load(fp))
                except Exception as e:
                    logger.error(f"[EventWatcher] Failed to read {jf}: {e}")
            
        except Exception as e:
            logger.error(f"[EventWatcher] Failed to list directory: {e}")
        
        # 2단계 필터: 내용 기반 중복 방지 (해시 비교)
        content_hash = self._calculate_content_hash(json_files)
        
        if content_hash == self.last_content_hash:
            logger.debug(f"[EventWatcher] Same content hash, skipping duplicate")
            return
        
        # 중복이 아니면 전송
        payload = {"event_files": json_files}
        
        self.post_json("event", payload)
        
        # 상태 업데이트
        self.last_send_time = now
        self.last_content_hash = content_hash
        
        if json_files:
            logger.info(f"[EventWatcher] Sent {len(json_files)} event files (hash: {content_hash[:8]}...)")
        else:
            logger.info(f"[EventWatcher] Sent empty event queue (hash: {content_hash[:8]}...)")

def start_event_watcher():
    start_watcher(EVENT_DIR, EventWatcherHandler, recursive=False, backend_url=BACKEND_URL)