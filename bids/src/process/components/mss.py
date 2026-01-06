#/BDSP/bids_app/src/process/components/mss.py
import os
import json
import logging
from pathlib import Path
from utils.common import bdsp_path_maker

logger = logging.getLogger(__name__)

def _create_initial_state_files(mss_path, structured_config):
    """새로 생성된 MSS 경로에 state 폴더와 초기 파일들 생성"""
    try:
        # state 폴더 경로 생성
        state_path = os.path.join(mss_path, "state")
        bdsp_path_maker(state_path)
        
        # 1. current.json 생성 (빈 파일)
        current_json_path = os.path.join(state_path, "current.json")
        _create_current_json(current_json_path)
        
        # 2. dataset_description.json 생성
        dataset_description_path = os.path.join(state_path, "dataset_description.json")
        _create_dataset_description_json(dataset_description_path, structured_config)
        
        # 3. README.md 생성
        readme_path = os.path.join(state_path, "README.md")
        _create_readme_md(readme_path, structured_config)
        
        logger.info(f"State 폴더와 초기 파일들이 생성됨: {state_path}")
        
    except Exception as e:
        logger.error(f"State 파일들 생성 실패: {e}")
        raise

def _create_current_json(file_path):
    """current.json 빈 파일 생성"""
    try:
        # 빈 JSON 객체 생성
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump({}, f, indent=2, ensure_ascii=False)
        
        logger.info(f"current.json 파일 생성됨: {file_path}")
        
    except Exception as e:
        logger.error(f"current.json 생성 실패: {e}")
        raise

def _create_dataset_description_json(file_path, structured_config):
    """dataset_description.json 빈 파일 생성"""
    try:
        # 빈 JSON 객체 생성
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump({}, f, indent=2, ensure_ascii=False)
        
        logger.info(f"dataset_description.json 파일 생성됨: {file_path}")
        
    except Exception as e:
        logger.error(f"dataset_description.json 생성 실패: {e}")
        raise

def _create_readme_md(file_path, structured_config):
    """README.md 빈 파일 생성"""
    try:
        # 빈 파일 생성
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write("")
        
        logger.info(f"README.md 파일 생성됨: {file_path}")
        
    except Exception as e:
        logger.error(f"README.md 생성 실패: {e}")
        raise

def _scan_directory_structure(mss_path):
    """MSS 경로 하위의 모든 폴더와 파일 구조를 스캔하여 딕셔너리로 반환"""
    try:
        structure = {}
        
        for root, dirs, files in os.walk(mss_path):
            # 상대 경로 계산
            rel_path = os.path.relpath(root, mss_path)
            if rel_path == '.':
                rel_path = ''
            
            # 현재 디렉토리 정보
            current_dict = structure
            if rel_path:
                path_parts = rel_path.split(os.sep)
                for part in path_parts:
                    if part not in current_dict:
                        current_dict[part] = {}
                    current_dict = current_dict[part]
            
            # 파일들 추가
            for file in files:
                file_path = os.path.join(root, file)
                current_dict[file] = {
                    "type": "file",
                    "full_path": os.path.abspath(file_path),
                    "size": os.path.getsize(file_path),
                    "modified": os.path.getmtime(file_path)
                }
            
            # 폴더들 추가 (빈 폴더도 포함)
            for dir_name in dirs:
                if dir_name not in current_dict:
                    current_dict[dir_name] = {}
                dir_path = os.path.join(root, dir_name)
                if not current_dict[dir_name]:  # 빈 딕셔너리인 경우
                    current_dict[dir_name] = {
                        "type": "directory",
                        "full_path": os.path.abspath(dir_path)
                    }
        
        return structure
        
    except Exception as e:
        logger.error(f"디렉토리 구조 스캔 실패: {e}")
        raise

def _update_current_json(mss_path, structure):
    """current.json을 디렉토리 구조로 업데이트"""
    try:
        current_json_path = os.path.join(mss_path, "state", "current.json")
        
        # current.json 내용 구성
        current_data = {
            "last_updated": "",  # 실제 구현시 현재 시간으로 설정
            "mss_path": os.path.abspath(mss_path),
            "directory_structure": structure,
            "total_files": _count_files(structure),
            "total_directories": _count_directories(structure)
        }
        
        with open(current_json_path, 'w', encoding='utf-8') as f:
            json.dump(current_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"current.json이 디렉토리 구조로 업데이트됨: {current_json_path}")
        
    except Exception as e:
        logger.error(f"current.json 업데이트 실패: {e}")
        raise

def _count_files(structure):
    """구조에서 파일 개수 카운트"""
    count = 0
    for key, value in structure.items():
        if isinstance(value, dict):
            if value.get("type") == "file":
                count += 1
            else:
                count += _count_files(value)
    return count

def _count_directories(structure):
    """구조에서 디렉토리 개수 카운트"""
    count = 0
    for key, value in structure.items():
        if isinstance(value, dict):
            if value.get("type") == "directory":
                count += 1
            elif "type" not in value:  # 중첩된 딕셔너리
                count += 1 + _count_directories(value)
    return count

def create_mss_structure(structured_config, global_vars):
    """Step 1: Medical Information System Structure 생성"""
    logger.info("Step1: MSS 구조 생성 시작")
    
    try:
        # request 딕셔너리에서 필요한 entity들 추출
        request = structured_config['request']
        working_dir = global_vars['working_dir']
        
        # Entity 변수들 선언
        system_id = request['systemId']
        project_code = request['projectCode']
        project_name = request['projectName']
        project_seq = request['projectSeq']
        org_id = request['orgId']
        org_no = request['orgNo']
        category = request['category']
        body_part = request['bodyPart']
        domain = request['domain']

        # MSS 경로 구성: working_dir/system_id/project_name/project_seq/org_id/category/body_part/DATA
        mss_path = os.path.join(
            working_dir,
            system_id,
            project_name,
            project_seq,
            org_id,
            category,
            body_part,
            "DATA"
        )
        
        # MSS 경로가 이미 존재하는지 확인
        mss_exists = os.path.exists(mss_path)
        
        if not mss_exists:
            # MSS 경로가 존재하지 않을 경우: 새로 생성하고 초기 파일들 생성
            path_created = bdsp_path_maker(mss_path)
            
            if path_created:
                logger.info(f"새 MSS 구조 생성: {mss_path}")
                # state 폴더 및 초기 파일들 생성
                _create_initial_state_files(mss_path, structured_config)
            else:
                logger.error(f"MSS 구조 생성 실패: {mss_path}")
                raise Exception(f"MSS 구조 생성 실패: {mss_path}")
        else:
            # MSS 경로가 이미 존재할 경우: 전체 구조를 스캔하여 current.json 업데이트
            logger.info(f"기존 MSS 구조 발견: {mss_path}")
            
            # state 폴더가 없다면 생성
            state_path = os.path.join(mss_path, "state")
            if not os.path.exists(state_path):
                bdsp_path_maker(state_path)
                # current.json도 없다면 빈 파일로 생성
                current_json_path = os.path.join(state_path, "current.json")
                if not os.path.exists(current_json_path):
                    _create_current_json(current_json_path)
            
            # 디렉토리 구조 스캔 및 current.json 업데이트
            directory_structure = _scan_directory_structure(mss_path)
            _update_current_json(mss_path, directory_structure)
        
        logger.info("MSS 구조 처리 완료")
        return mss_path
        
    except Exception as e:
        logger.error(f"MSS 구조 처리 실패: {e}")
        raise