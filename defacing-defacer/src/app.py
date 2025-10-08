import os
import time
import shutil
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import logging
import process.main  
from globals import MAX_WORKERS, EVENT_DIR, WORKING_DIR, BACKUP_DIR, ERROR_DIR, LOG_FILENAME, PROCESS, PACKAGE, COMMAND

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

class JSONFileMonitor:
    def __init__(self):
        self.event_dir = EVENT_DIR
        self.working_dir = WORKING_DIR
        self.backup_dir = BACKUP_DIR
        self.error_dir = ERROR_DIR
        self.max_workers = MAX_WORKERS
        self.process = PROCESS
        self.package = PACKAGE
        self.command = COMMAND
        self.executor = ThreadPoolExecutor(max_workers=self.max_workers)
        self.processed_files = set()  # 이미 처리된 파일 추적
        
    
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
            
            # JSON 파일 읽기
            with open(working_file_path, 'r', encoding='utf-8') as f:
                json_data = json.load(f)
            
            # flag 딕셔너리만 추출
            flag_data = json_data.get('flag', [])
            
            if not flag_data:
                logger.warning(f"No flag data found in {file_name}")
                return
            
            # process.main의 함수 호출
            process.main.main(
                flag_data, 
                json_file_path=working_file_path, 
                backup_dir=self.backup_dir,
                process=self.process,
                package=self.package,
                command=self.command
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
    monitor = JSONFileMonitor()
    monitor.monitor_loop()


if __name__ == "__main__":
    main()