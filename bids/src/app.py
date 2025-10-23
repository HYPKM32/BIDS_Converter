#/BDSP/bids_app/src/app.py
import os
import sys
import time
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import logging
import process.main  
from globals import (
    EVENT_DIR, WORKING_DIR, UPLOAD_DIR, BACKUP_DIR, ERROR_DIR, 
    MAX_WORKERS, LOG_FILENAME, MAGNETIC_STRENGTH_FIELD,
    DICOM_MODALITY, NIFTI_MODALITY, PARREC_MODALITY, SUFFIX_MAP,
    FLAG_DIR
)
import threading

from services.watch import start_all_watchers


# 로그 파일 디렉토리 자동 생성
log_dir = os.path.dirname(LOG_FILENAME)
if log_dir and not os.path.exists(log_dir):
    os.makedirs(log_dir, exist_ok=True)

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILENAME),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def run_api_server():
    """Thread로 FastAPI API 서버 실행"""
    import uvicorn
    from services.api import app
    
    HOST = "0.0.0.0"
    PORT = int(os.getenv("PORT", "8896"))
    
    try:
        logger.info(f"[BDSP] Starting API server on {HOST}:{PORT}")
        uvicorn.run(app, host=HOST, port=PORT, log_level="info")
    except Exception as e:
        logger.error(f"Failed to start API server: {e}")
        import traceback
        logger.error(traceback.format_exc())

class JSONFileMonitor:
    def __init__(self):
        self.event_dir = EVENT_DIR
        self.working_dir = WORKING_DIR
        self.upload_dir = UPLOAD_DIR
        self.backup_dir = BACKUP_DIR
        self.error_dir = ERROR_DIR
        self.max_workers = MAX_WORKERS
        self.magnetic_strength_field = MAGNETIC_STRENGTH_FIELD
        # Modality paths
        self.dicom_modality = DICOM_MODALITY
        self.nifti_modality = NIFTI_MODALITY
        self.parrec_modality = PARREC_MODALITY
        self.suffix_map = SUFFIX_MAP
        # Flag paths
        self.flag_dir = FLAG_DIR
        self.executor = ThreadPoolExecutor(max_workers=self.max_workers)
        self.processed_files = set()  # 이미 처리된 파일 추적
        
        logger.info(f"Monitor initialized - Event Dir: {self.event_dir}, Working Dir: {self.working_dir}, Upload Dir: {self.upload_dir}, "
                   f"Backup Dir: {self.backup_dir}, Error Dir: {self.error_dir}, Max Workers: {self.max_workers}")
        logger.info(f"Modality paths - DICOM: {self.dicom_modality}, NIFTI: {self.nifti_modality}, PARREC: {self.parrec_modality}, SUFFIX_MAP: {self.suffix_map}")
    
    
    def get_json_files(self):
        """EVENT_DIR에서 JSON 파일들을 찾기"""
        json_files = []
        try:
            for file in os.listdir(self.event_dir):
                if file.endswith('.json') and file not in self.processed_files:
                    file_path = os.path.join(self.event_dir, file)
                    if os.path.isfile(file_path):
                        json_files.append(file_path)
        except FileNotFoundError:
            logger.error(f"Event directory not found: {self.event_dir}")
        except Exception as e:
            logger.error(f"Error scanning event directory: {e}")
        
        return json_files
    
    
    def move_file_to_working(self, json_file_path):
        """JSON 파일을 WORKING_DIR로 이동"""
        try:
            file_name = os.path.basename(json_file_path)
            destination = os.path.join(self.working_dir, file_name)
            shutil.move(json_file_path, destination)
            logger.info(f"Moved file: {file_name} to working directory")
            return destination
        except Exception as e:
            logger.error(f"Error moving file {json_file_path}: {e}")
            return None
    
    
    def move_file_to_error(self, file_path, error_msg):
        """처리 실패한 파일을 ERROR_DIR로 이동"""
        try:
            file_name = os.path.basename(file_path)
            error_destination = os.path.join(self.error_dir, file_name)
            
            # 같은 이름의 파일이 있으면 타임스탬프 추가
            if os.path.exists(error_destination):
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                name, ext = os.path.splitext(file_name)
                error_destination = os.path.join(self.error_dir, f"{name}_{timestamp}{ext}")
            
            shutil.move(file_path, error_destination)
            logger.info(f"Moved error file to error directory: {file_name}")
            
            # 에러 로그 파일 생성
            error_log_path = error_destination.replace('.json', '_error.log')
            with open(error_log_path, 'w') as f:
                f.write(f"Error occurred at: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Error message: {error_msg}\n")
                
        except Exception as e:
            logger.error(f"Error moving file to error directory {file_path}: {e}")
    
    def process_json_file(self, json_file_path):
        """JSON 파일을 처리하는 메인 로직"""
        file_name = os.path.basename(json_file_path)
        logger.info(f"Processing file: {file_name}")
        
        working_file_path = None
        try:
            # 파일을 WORKING_DIR로 이동
            working_file_path = self.move_file_to_working(json_file_path)
            if not working_file_path:
                return
            
            # process.main의 함수 직접 호출 (전역변수들과 함께)
            process.main.main(
                working_file_path,
                upload_dir=self.upload_dir,
                backup_dir=self.backup_dir,
                error_dir=self.error_dir,
                working_dir=self.working_dir,
                dicom_modality=self.dicom_modality,
                nifti_modality=self.nifti_modality,
                parrec_modality=self.parrec_modality,
                suffix_map = self.suffix_map,
                flag_dir=self.flag_dir,
                magnetic_strength_field = self.magnetic_strength_field
            )
            logger.info(f"Successfully processed: {file_name}")
                
        except Exception as e:
            error_msg = f"Error processing {file_name}: {e}"
            logger.error(error_msg)
            
            # 에러 발생 시 ERROR_DIR로 이동
            if working_file_path and os.path.exists(working_file_path):
                self.move_file_to_error(working_file_path, str(e))
            
        finally:
            # 처리 완료된 파일을 추적 목록에서 제거 (재처리 가능하게)
            self.processed_files.discard(file_name)
    
    def monitor_loop(self):
        """5초마다 EVENT_DIR을 체크하는 메인 루프"""
        logger.info("Starting JSON file monitoring...")
        
        while True:
            try:
                json_files = self.get_json_files()
                
                for json_file in json_files:
                    file_name = os.path.basename(json_file)
                    # 중복 처리 방지
                    if file_name not in self.processed_files:
                        self.processed_files.add(file_name)
                        # 스레드풀에 작업 제출
                        self.executor.submit(self.process_json_file, json_file)
                        logger.info(f"Submitted for processing: {file_name}")
                
                time.sleep(5)  # 5초 대기
                
            except KeyboardInterrupt:
                logger.info("Monitor stopped by user")
                break
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")
                time.sleep(5)
        
        # 종료 시 스레드풀 정리
        self.executor.shutdown(wait=True)
        logger.info("Monitor shutdown complete")

def main():
    """메인 함수"""
    #api
    threading.Thread(target=run_api_server, daemon=True).start()
    
    # Watchers 5종
    threading.Thread(target=start_all_watchers, daemon=True).start()

    #main
    monitor = JSONFileMonitor()
    monitor.monitor_loop()

if __name__ == "__main__":
    main()