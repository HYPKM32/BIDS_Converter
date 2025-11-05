#/BDSP/civet_app/src/process/components/filter.py
import logging
import json

logger = logging.getLogger(__name__)


def filter_flags(flag_data, process, package):
    """
    flag_data에서 지정된 process와 package가 일치하는 항목만 필터링
    
    Args:
        flag_data (list): flag 딕셔너리 리스트
        process (str): 필터링할 process 이름
        package (str): 필터링할 package 이름
        
    Returns:
        list: 필터링된 flag 리스트
    """
    filtered_flags = []
    
    for flag in flag_data:
        flag_process = flag.get('process', '')
        flag_package = flag.get('package', '')
        
        # process와 package가 일치하는 경우만 추가
        if flag_process == process and flag_package == package:
            filtered_flags.append(flag)
            logger.info(f"Matched flag: process={flag_process}, package={flag_package}")
        else:
            logger.debug(f"Filtered out flag: process={flag_process}, package={flag_package}")
    
    return filtered_flags


def validate_filtered_flags(filtered_flags):
    """
    필터링된 flag 데이터의 유효성 검증
    
    Args:
        filtered_flags (list): 필터링된 flag 리스트
        
    Returns:
        dict: 유효한 flag 객체 (단일)
        
    Raises:
        ValueError: 유효성 검증 실패 시
    """
    # 1. flag가 정확히 1개인지 확인
    if len(filtered_flags) == 0:
        error_msg = "No filtered flags found"
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    if len(filtered_flags) > 1:
        error_msg = f"Multiple flags found: expected 1, got {len(filtered_flags)}"
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    flag = filtered_flags[0]
    
    # 2. status가 pending인지 확인 후 running으로 변경
    status = flag.get('status', '')
    if status != 'pending':
        error_msg = f"Invalid status: expected 'pending', got '{status}'"
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    # 상태 변경
    flag['status'] = 'running'
    logger.info(f"Flag validation passed: status changed pending -> running")
    
    return flag


def update_flag_status(flag, new_status, json_file_path):
    """
    flag의 status를 업데이트하고 JSON 파일에도 반영
    """
    flag['status'] = new_status
    logger.info(f"Status updated to '{new_status}'")
    
    # JSON 파일 읽기
    with open(json_file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # 해당 flag 찾아서 status 업데이트
    for item in data.get('flag', []):
        if (item.get('process') == flag['process'] and 
            item.get('package') == flag['package']):
            item['status'] = new_status
            break
    
    # JSON 파일에 쓰기
    with open(json_file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    logger.info(f"JSON file updated: {json_file_path}")