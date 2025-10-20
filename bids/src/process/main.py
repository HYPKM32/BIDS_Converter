#/BDSP/bids_app/src/process/main.py
import json
import logging
import os
import shutil
from pathlib import Path
from process.components import mss, origin, export, flag
from utils import common

logger = logging.getLogger(__name__)

# 전역 변수를 저장할 딕셔너리
global_vars = {}

def __init__():
    """초기화 함수"""
    logger.info("Process module initialized")

def load_json_config(json_file_path):
    """JSON 설정 파일 로드"""
    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        logger.info(f"JSON 설정 파일 로드 성공: {json_file_path}")
        return config
    except Exception as e:
        logger.error(f"JSON 설정 파일 로드 실패: {e}")
        raise

def remove_whitespace_from_dict(data):
    """딕셔너리의 모든 문자열 값에서 공백 제거 (재귀적으로 처리)"""
    if isinstance(data, dict):
        return {key: remove_whitespace_from_dict(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [remove_whitespace_from_dict(item) for item in data]
    elif isinstance(data, str):
        return common.remove_all_whitespace(data)
    else:
        return data

def validate_and_initialize_config(config):
    """Step 0: JSON 변수 정리 및 초기화"""
    logger.info("Step 0: 설정 검증 및 초기화")
    
    try:
        # 필수 필드 확인 (uploadTime 추가)
        required_fields = ['user', 'systemId', 'projectCode', 'projectSeq', 'orgId', 'trialIndex', 'uploadTime','subjectId']
        missing_fields = []
        
        for field in required_fields:
            if field not in config:
                missing_fields.append(field)
        
        if missing_fields:
            logger.error(f"누락된 필수 필드: {missing_fields}")
            raise Exception(f"누락된 필수 필드: {missing_fields}")
                
        # 선택적 필드 초기화
        
        if 'bids' not in config or config['bids'] is None:
            config['bids'] = True
            print("bids 필드를 기본값으로 초기화: True")
        else:
            print(f"bids: {config['bids']}")
        
        if 'domain' not in config or not config['domain']:
            config['domain'] = "DATA"
            print("Domain 필드를 기본값으로 초기화")
        
        # bodyPart 필드 초기화 (기본값: BRAIN)
        if 'bodyPart' not in config or not config['bodyPart']:
            config['bodyPart'] = "BRAIN"
            print("BodyPart 필드를 기본값으로 초기화: BRAIN")
        else:
            print(f"Body Part: {config['bodyPart']}")
        
        # category 필드 초기화 (기본값: IMAGE)
        if 'category' not in config or not config['category']:
            config['category'] = "IMAGE"
            print("Category 필드를 기본값으로 초기화: IMAGE")
        else:
            print(f"Category: {config['category']}")
        
        # public 필드 초기화 (기본값: False)
        if 'public' not in config or config['public'] is None:
            config['public'] = False
            print("Public 필드를 기본값으로 초기화: False")
        else:
            print(f"Public: {config['public']}")
        
        # task 필드 초기화 (기본값: isFunc: False, option: "")
        if 'task' not in config:
            config['task'] = {
                "isFunc": False,
                "option": ""
            }
            print("Task 설정을 기본값으로 초기화")
        else:
            # task 필드 검증
            task = config['task']
            if 'isFunc' not in task:
                task['isFunc'] = False
            if 'option' not in task:
                task['option'] = ""
            print(f"Task 설정 검증 완료 - isFunc: {task['isFunc']}")
        
        if 'flag' not in config:
            config['flag'] = []
            print("Flag 배열을 빈 배열로 초기화")
        elif not isinstance(config['flag'], list):
            raise Exception("Flag는 리스트 형태여야 합니다")
        else:
            print(f"{len(config['flag'])}개의 flag 항목 발견")
        
        # 프로젝트 시퀀스를 문자열로 변환 (경로 생성시 일관성 위해)
        config['projectSeq'] = str(config['projectSeq'])
        
        # structured_config 생성 - request 딕셔너리에 bodyPart, category, public 포함
        structured_config = {
            'request': {
                'user': config['user'],
                'systemId': config['systemId'],
                'projectCode': config['projectCode'],
                'projectSeq': config['projectSeq'],
                'orgId': config['orgId'],
                'trialIndex': config['trialIndex'],
                'uploadTime': config['uploadTime'],
                'domain': config['domain'],
                'bodyPart': config['bodyPart'],  
                'category': config['category'],
                'public': config['public'],
                'subjectId': config['subjectId']
            },
            'task': config['task'],
            'flag': config['flag'] 
        }
        
        # 모든 딕셔너리 문자열 값에서 공백 제거
        structured_config = remove_whitespace_from_dict(structured_config)
        
        logger.info("설정 검증 및 초기화가 성공적으로 완료됨")
        print("모든 설정 변수가 검증 및 초기화됨 (공백 제거 완료)")
        
        return structured_config
        
    except Exception as e:
        logger.error(f"설정 검증 및 초기화 실패: {e}")
        raise

def update_paths_after_step(paths, step_name, **step_paths):
    """각 스텝 완료 후 경로 정보를 업데이트"""
    if step_name not in paths:
        paths[step_name] = {}
    
    paths[step_name].update(step_paths)
    
    logger.info(f"{step_name} 경로 정보 업데이트 완료")
    for key, value in step_paths.items():
        print(f"  {key}: {value}")
    
    return paths

def process_flags(structured_config, paths):
    """Step 7: process flag 처리 (조건부 실행)"""
    logger.info("Step 7: Flag 처리")
    flag = structured_config['flag']
    print(flag)

def main(json_file_path, upload_dir=None, backup_dir=None, error_dir=None, working_dir=None,
         dicom_modality=None, nifti_modality=None, parrec_modality=None, suffix_map=None,
         flag_dir=None, magnetic_strength_field = None):
    """JSON 파일을 처리하는 메인 함수"""
    global global_vars
    
    __init__()
    
    # app.py에서 전달받은 모든 변수들을 global_vars 딕셔너리에 저장
    global_vars = {
        'json_file_path': json_file_path,
        'upload_dir': upload_dir,
        'backup_dir': backup_dir,
        'error_dir': error_dir,
        'working_dir': working_dir,
        'dicom_modality': dicom_modality,
        'nifti_modality': nifti_modality,
        'parrec_modality': parrec_modality,
        'suffix_map': suffix_map,
        'flag_dir': flag_dir,
        'magnetic_strength_field': magnetic_strength_field 
    }
    
    logger.info(f"JSON 파일 처리 시작: {json_file_path}")
    logger.info(f"전역 변수 저장 완료: {len(global_vars)}개 변수")
    print(f"전역 변수들이 global_vars 딕셔너리에 저장됨:")
    for key, value in global_vars.items():
        if value is not None:
            print(f"  {key}: {value}")
    
    try:
        # 모든 경로 정보를 저장할 딕셔너리 초기화
        paths = {}
        
        # JSON 설정 로드
        config = load_json_config(json_file_path)
        
        # Step 0: 변수 정리 및 초기화
        structured_config = validate_and_initialize_config(config)
        if not config.get('bids', True):
            logger.info("bids=False이므로 Step 1-6을 건너뛰고 Step 7로 점프합니다")
            print("bids=False: 데이터 처리를 건너뛰고 Flag 처리만 수행합니다")
            
            # Step 7: 전처리 Flag 처리만 수행
            logger.info("Step 7: 전처리 Flag 처리만 진행")
            derived_export_json = flag.process_flags(structured_config['flag'], global_vars, json_file_path)
        else:
            # Step 1: MSS 구조 생성
            mss_path = mss.create_mss_structure(structured_config, global_vars)
            mss_state_path = os.path.join(mss_path, "state")
            paths = update_paths_after_step(paths, "step1_mss", 
                                        mss_path=mss_path,
                                        mss_state_path=mss_state_path)
            
            
            # Step 2: origin 경로 생성 (origin.py에서 처리)
            origin_path = origin.create_origin_path(structured_config, global_vars, mss_path)
            origin_zip_path = os.path.join(origin_path,"zip")
            origin_unzip_path = os.path.join(origin_path,"unzip")
            paths = update_paths_after_step(paths, "step2_origin",
                                        origin_path=origin_path,
                                        origin_zip_path=origin_zip_path,
                                        origin_unzip_path=origin_unzip_path)
            
            # Step 3,4,5: domain에 따른 source/raw/thumbnail 생성 (domain별 모듈에서 처리)
            domain = structured_config['request']['domain'].upper()
            logger.info(f"Step 3: Domain '{domain}'에 따른 source 처리")
            
            try:
                if domain == "MRI" or domain == "DATA" or domain == "CT":
                    # MRI 또는 DATA 도메인인 경우 MRI 모듈 사용
                    from process.components.domain.mri.source import source as mri_source
                    from process.components.domain.mri.raw import raw as mri_raw
                    from process.components.domain.mri.post import bids_checker as mri_checker
                    from process.components.domain.mri.post import byproduct as mri_byproduct
                    from process.components.domain.mri.post import thumbnail as mri_thumbnail
                    # source_path로 받아서 개별 변수로 저장
                    source_path = mri_source.create_source_path(structured_config, mss_path, origin_unzip_path)
                    paths = update_paths_after_step(paths, "step3_source",
                                source_path=source_path)
                    
                    logger.info(f"Step 4: Domain '{domain}'에 따른 raw 처리")
                    raw_path = mri_raw.create_raw_path(structured_config,source_path,global_vars)
                    paths = update_paths_after_step(paths,"step4_raw",
                                raw_path=raw_path)
                    
                    logger.info(f"Step 5-1: Domain '{domain}' 후처리: BIDS modality Checker")
                    bids_checklist = mri_checker.check_modality(raw_path)
                    paths = update_paths_after_step(paths,"step5_checklist",
                                bids_checklist=bids_checklist)
                    
                    logger.info(f"Step 5-2: Domain '{domain}' 후처리: BIDS mdality Byproduct Checker")
                    byproduct_path = mri_byproduct.check_byproduct(raw_path)
                    
                    
                    logger.info(f"Step 5-3: Domain '{domain}' 후처리: Thumbnail 생성")
                    thumbnail_path = mri_thumbnail.thumbnail(raw_path)
                    
                    raw_to_source = {}
                    for source_key, raw_key in raw_path.items():
                        raw_to_source[raw_key] = source_key

                    
                    for nifti_key in bids_checklist.keys():
                        # byproduct 추가
                        if nifti_key in byproduct_path:
                            bids_checklist[nifti_key]['byproduct'] = byproduct_path[nifti_key]
                        
                        # thumbnail 추가
                        if nifti_key in thumbnail_path:
                            bids_checklist[nifti_key]['thumbnail'] = thumbnail_path[nifti_key]
                        
                        # source 추가
                        if nifti_key in raw_to_source:
                            bids_checklist[nifti_key]['source'] = raw_to_source[nifti_key]

                    # 통합된 checklist만 paths에 업데이트
                    paths = update_paths_after_step(paths, "step5_checklist",
                                bids_checklist=bids_checklist)

                    print(f"MRI 도메인 source 처리 완료 (Domain: {domain})")
                    
                elif domain == "PET":
                    # CT 도메인인 경우 CT 모듈 사용
                    from process.components.domain.pet import source as pet_source
                    from process.components.domain.pet import raw as pet_raw
                    from process.components.domain.pet import thumbnail as pet_thumbnail
                    print(f"PET 도메인 source 처리 완료")
                    
                else:
                    # 지원되지 않는 도메인인 경우 에러 처리
                    logger.error(f"지원되지 않는 도메인: {domain}")
                    raise Exception(f"지원되지 않는 도메인: {domain}")
                
            except ImportError as e:
                logger.error(f"도메인 '{domain}' 모듈에서 에러: {e}")
                raise Exception(f"도메인 '{domain}' 모듈에서 에러: {e}")
                
            except Exception as e:
                logger.error(f"Domain '{domain}'처리 실패: {e}")
                raise
            
            logger.info("Step 6: export.json 처리")
            # Step 6: Export JSON 생성 (export.py에서 처리)
            export_json = export.create_export(config,global_vars, paths)
            
            logger.info("Step 7: 전처리 Flag 처리")
            # Step 7: 전처리 Flag 처리 
            derived_export_json = flag.process_flags(structured_config['flag'],global_vars, export_json) 
            
            # Step 8: backup_dir/system_id로 export_json옮기고 종료 
            backup_path = os.path.join(backup_dir, config['systemId'])
            if not os.path.exists(backup_path):
                os.makedirs(backup_path)
            else:
                logger.info(f"백업 디렉토리 존재: {backup_path}")
            if derived_export_json and os.path.exists(derived_export_json):
                source_file = derived_export_json
                file_name = os.path.basename(derived_export_json)
            elif os.path.exists(export_json):
                source_file = export_json
                file_name = os.path.basename(export_json)
            
            destination_file = os.path.join(backup_path, file_name)
            shutil.move(source_file, destination_file)
            
            logger.info("BIDS Converting has done")
        
    except Exception as e:
        logger.error(f"Fail: {e}")
        raise