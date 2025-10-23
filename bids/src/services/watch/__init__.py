import threading
import logging
from .eventWatcher import start_event_watcher
from .workingWatcher import start_working_watcher
from .errorWatcher import start_error_watcher
from .flagWatcher import start_flag_watcher
from .uploadWatcher import start_upload_watcher
from .backupWatcher import start_backup_watcher

logger = logging.getLogger(__name__)

__all__ = [
    "start_event_watcher",
    "start_working_watcher",
    "start_error_watcher",
    "start_flag_watcher",
    "start_upload_watcher",
    "start_backup_watcher",
    "start_all_watchers",
]


def start_all_watchers():
    """모든 Watcher를 병렬 스레드로 실행"""
    watchers = [
        ("EventWatcher", start_event_watcher),
        ("UploadWatcher", start_upload_watcher),
        ("FlagWatcher", start_flag_watcher),
        ("ErrorWatcher", start_error_watcher),
        ("WorkingWatcher", start_working_watcher),
        ("BackupWatcher", start_backup_watcher)
    ]

    threads = []
    for name, func in watchers:
        t = threading.Thread(target=func, name=name, daemon=True)
        t.start()
        threads.append(t)
        logger.info(f"[WatcherInit] Started {name}")

    # main thread: watcher 유지 루프
    try:
        logger.info("[WatcherInit] All watchers running.")
        for t in threads:
            t.join()
    except KeyboardInterrupt:
        logger.warning("[WatcherInit] KeyboardInterrupt received. Shutting down...")
