import json
import os
import shutil
import logging
from datetime import datetime
logger = logging.getLogger(__name__)


def create_trace_json(config, paths):
    """trace.json 파일 생성"""
    
    # 1. mss_state_path에서 trace 폴더 경로 설정
    mss_state_path = paths['step1_mss']['mss_state_path']
    trace_folder = os.path.join(mss_state_path, 'trace')
    
    # 2. trace 폴더가 없으면 생성
    if not os.path.exists(trace_folder):
        os.makedirs(trace_folder)
        logger.info(f"trace 폴더 생성: {trace_folder}")
    else:
        logger.info(f"trace 폴더 이미 존재: {trace_folder}")
    
    # 3. trace.json 파일명 생성
    user = config['user']
    subject_id = config['subjectId']
    upload_time = config['uploadTime']
    trace_filename = f"{user}_{subject_id}_{upload_time}_trace.json"
    trace_filepath = os.path.join(trace_folder, trace_filename)
    
    # 4. 파일이 이미 존재하면 ValueError
    if os.path.exists(trace_filepath):
        error_msg = f"trace 파일이 이미 존재함: {trace_filepath}"
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    # 5. paths 딕셔너리를 JSON으로 저장
    try:
        with open(trace_filepath, 'w', encoding='utf-8') as f:
            json.dump(paths, f, ensure_ascii=False, indent=2)
        logger.info(f"trace.json 파일 생성 완료: {trace_filepath}")
        print(f"trace.json 생성됨: {trace_filename}")
        
        return trace_filepath
        
    except Exception as e:
        logger.error(f"trace.json 파일 생성 실패: {e}")
        raise


def create_export_json(config, global_vars, paths):
    """export.json 파일 생성"""
    
    # 1. 원본 JSON 파일 존재 확인
    original_json_path = global_vars['json_file_path']
    
    if not os.path.exists(original_json_path):
        error_msg = f"원본 JSON 파일이 존재하지 않음: {original_json_path}"
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    logger.info(f"원본 JSON 파일 확인: {original_json_path}")
    
    # 2. 파일명 변경
    user = config['user']
    subject_id = config['subjectId']
    upload_time = config['uploadTime']
    system_id = config['systemId']
    
    working_dir = os.path.dirname(original_json_path)
    now_time = datetime.now().strftime('%Y%m%d%H%M%S')
    new_filename = f"{user}_{subject_id}_{upload_time}_{now_time}_export.json"
    export_filepath = os.path.join(working_dir, new_filename)
    
    # 원본 파일 이름 변경
    os.rename(original_json_path, export_filepath)
    logger.info(f"파일명 변경: {original_json_path} -> {export_filepath}")
    
    # 3. 기존 JSON 파일 읽기
    try:
        with open(export_filepath, 'r', encoding='utf-8') as f:
            export_data = json.load(f)
    except Exception as e:
        logger.error(f"export.json 파일 읽기 실패: {e}")
        raise
    
    # 4. export 키 추가 및 데이터 구성
    mss_path = paths['step1_mss']['mss_path']
    origin_path = paths['step2_origin']['origin_path']
    bids_checklist = paths['step5_checklist']['bids_checklist']
    
    # data 리스트 생성
    data_list = []
    for index, (raw_path, checklist_data) in enumerate(bids_checklist.items()):
        # byproduct 가져오기 (없으면 빈 딕셔너리)
        byproduct = checklist_data.get('byproduct', {})
        
        # thumbnail을 byproduct에 추가
        thumbnail = checklist_data.get('thumbnail', '')
        if thumbnail:
            byproduct['thumbnail'] = thumbnail
        
        data_item = {
            'index': index,
            'modality': checklist_data.get('modality', ''),
            'raw': raw_path,
            'source': checklist_data.get('source',''),
            'sidecar': checklist_data.get('sidecar_json', ''),
            'byproduct': byproduct
        }
        data_list.append(data_item)
    
    # export 키 추가
    export_data['export'] = {
        'mssPath': mss_path,
        'origin': origin_path,
        'bidsPath': data_list
    }
    
    # 5. 파일에 저장
    try:
        with open(export_filepath, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)
        logger.info(f"export.json 파일 생성 완료: {export_filepath}")
        print(f"export.json 생성됨: {new_filename}")
        
        return export_filepath
        
    except Exception as e:
        logger.error(f"export.json 파일 저장 실패: {e}")
        raise



def create_export(config, global_vars, paths):
    """export 메인 함수"""
    logger.info("Step 6: Export 시작")
    
    try:
        # 1. trace.json 생성
        trace_filepath = create_trace_json(config, paths)
        
        # 2. export.json 생성
        export_filepath = create_export_json(config, global_vars, paths)
        
        logger.info("Export 완료")
        print("="*50)
        print("Export 작업 완료")
        print(f"  - trace.json: {trace_filepath}")
        print(f"  - export.json: {export_filepath}")
        print("="*50)
        
        return export_filepath
        
    except Exception as e:
        logger.error(f"Export 작업 실패: {e}")
        raise