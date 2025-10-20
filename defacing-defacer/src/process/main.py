#/BDSP/defacer_app/src/process/main.py
import os
import json
import shutil
import logging
import subprocess
from process.components import parser, filter, cli, export, sidecar

logger = logging.getLogger(__name__)


def backup_json_file(json_file_path, backup_dir):
    """
    JSON 파일을 백업 디렉토리로 복사
    
    Args:
        json_file_path (str): 백업할 JSON 파일 경로
        backup_dir (str): 백업 디렉토리 경로
        
    Returns:
        str: 백업된 파일의 전체 경로
        
    Raises:
        Exception: 백업 실패 시
    """
    try:
        # 백업 디렉토리가 없으면 생성
        os.makedirs(backup_dir, exist_ok=True)
        
        # 원본 파일명 추출
        filename = os.path.basename(json_file_path)
        
        # 백업 파일 전체 경로
        backup_path = os.path.join(backup_dir, filename)
        
        # 파일 복사
        shutil.move(json_file_path, backup_path)
        
        logger.info(f"JSON file backed up successfully")
        logger.info(f"  Source: {json_file_path}")
        logger.info(f"  Backup: {backup_path}")
        
        return backup_path
        
    except Exception as e:
        logger.error(f"Failed to backup JSON file: {e}")
        raise


def extract_space_from_flag(flag_data, process, package):
    """
    flag 리스트에서 process와 package가 일치하는 객체의 space 값을 추출
    
    Args:
        flag_data (list): flag 딕셔너리 리스트
        process (str): 필터링할 process 이름
        package (str): 필터링할 package 이름
        
    Returns:
        str: space 값 (없으면 빈 문자열)
    """
    for flag in flag_data:
        if flag.get('process') == process and flag.get('package') == package:
            space = flag.get('space', '')
            logger.info(f"Extracted space value: '{space}' for process={process}, package={package}")
            return space
    
    logger.warning(f"No space value found for process={process}, package={package}")
    return ''


def main(flag_data, json_file_path, backup_dir, process, package, command):
    """
    메인 처리 함수
    
    Args:
        flag_data (list): flag 딕셔너리 리스트
        json_file_path (str): JSON 파일 경로
        backup_dir (str): 백업 디렉토리 경로
        process (str): 필터링할 process 이름
        package (str): 필터링할 package 이름
        command (str): 실행할 CLI 커맨드 (예: "python3 defacer_cli.py")
    """
    logger.info(f"Starting main process")
    logger.info(f"JSON file: {json_file_path}")
    logger.info(f"Backup dir: {backup_dir}")
    logger.info(f"Filter: process={process}, package={package}")
    logger.info(f"Command: {command}")
    
    # space 값 추출
    space = extract_space_from_flag(flag_data, process, package)
    
    # flag 필터링
    filtered_flags = filter.filter_flags(flag_data, process, package)
    
    if not filtered_flags:
        logger.warning(f"No matching flags found for process={process}, package={package}")
        return
    
    logger.info(f"Found {len(filtered_flags)} matching flag(s)")
    
    # flag 유효성 검증 (1개만 있어야 하고, status가 pending이어야 함)
    try:
        flag = filter.validate_filtered_flags(filtered_flags)
    except ValueError as e:
        logger.error(f"Flag validation failed: {e}")
        raise
    
    # status를 pending -> running으로 변경
    filter.update_flag_status(flag, 'running')
    
    # components.parser 호출 (command와 flag 전달)
    command_list = parser.parser(command, [flag])
    
    logger.info(f"Starting defacing process...")
    
    try:
        execution_result = cli.execute_commands(command_list, flag['derived_data'])
        
        # space 값을 sidecar 모듈에 전달
        sidecar_json = sidecar.make_sidecar_json(execution_result, process, package, space)
        
        is_exported = export.export_json(execution_result, json_file_path, process, package, sidecar_json)
        
        # export 성공 시 JSON 파일 백업
        if is_exported:
            logger.info(f"Export successful, backing up JSON file...")
            try:
                backup_path = backup_json_file(json_file_path, backup_dir)
                logger.info(f"Backup completed: {backup_path}")
            except Exception as e:
                logger.error(f"Backup failed, but export was successful: {e}")
                # 백업 실패해도 프로세스는 성공으로 간주 (export는 성공했으므로)
        else:
            logger.error(f"Export failed, skipping backup")
            return
        
        logger.info(f"All commands executed successfully")
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Command execution failed: {e}")
        logger.error(f"Process stopped due to command failure")
        raise
        
    except Exception as e:
        logger.error(f"Unexpected error during execution: {e}")
        raise