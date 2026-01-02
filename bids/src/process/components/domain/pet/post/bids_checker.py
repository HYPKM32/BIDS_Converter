# /BDSP/bids_app/src/process/components/domain/pet/post/bids_checker.py
# PET 도메인 전용 BIDS Checker
# PET은 data_type과 modality가 모두 'pet'으로 고정됩니다.

import os
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

def check_modality(raw_path):
    """
    PET BIDS 규격에 따른 모달리티 검증을 수행합니다.

    Args:
        raw_path (dict): {source_path: nifti_file_path} 형태의 딕셔너리

    Returns:
        dict: 검증 결과를 담은 딕셔너리

    Raises:
        ValueError: NIfTI 파일이 존재하지 않는 경우

    Note:
        PET은 data_type='pet', modality='pet'으로 고정됩니다.
        파일명 예시: sub-xxx_ses-01_trc-18FFDG_run-01_pet.nii.gz
    """
    validation_results = {}
    
    # 1. raw_path의 value 값들을 순회
    for source_path, nifti_path in raw_path.items():
        logger.info(f"BIDS 검증 시작: {nifti_path}")
        
        file_result = {
            'nifti_exists': False,
            'sidecar_json': None,  # 변경: json_exists → sidecar_json
            'bids_guess': None,
            'data_type': None,
            'modality': None,
            'folder_structure_valid': False,
            'warnings': []
        }
        
        # 2. NIfTI 파일 존재 확인
        if not os.path.exists(nifti_path):
            raise ValueError(f"NIfTI 파일이 존재하지 않습니다: {nifti_path}")
        
        file_result['nifti_exists'] = True
        logger.info(f"NIfTI 파일 확인 완료: {nifti_path}")
        
        # data_type과 modality 추출
        data_type, modality = _extract_data_type_and_modality(nifti_path)
        file_result['data_type'] = data_type
        file_result['modality'] = modality
        logger.info(f"추출된 data_type: {data_type}, modality: {modality}")
        
        # 3. Sidecar JSON 파일 확인
        json_path = nifti_path.replace('.nii.gz', '.json')
        
        if not os.path.exists(json_path):
            warning_msg = f"Sidecar JSON 파일이 존재하지 않습니다: {json_path}"
            logger.warning(warning_msg)
            file_result['warnings'].append(warning_msg)
        else:
            file_result['sidecar_json'] = json_path  # 변경: 실제 경로 저장
            logger.info(f"Sidecar JSON 파일 확인 완료: {json_path}")
            
            # 4. BidsGuess 키 확인
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    json_data = json.load(f)
                
                if 'BidsGuess' in json_data:
                    bids_guess_list = json_data['BidsGuess']
                    if isinstance(bids_guess_list, list) and len(bids_guess_list) > 0:
                        modality = bids_guess_list[0]  # 첫번째 객체값 가져오기
                        file_result['bids_guess'] = modality
                        logger.info(f"BidsGuess 모달리티 추출: {modality}")
                        
                        # 6-8. 폴더 구조 검증
                        folder_validation = _validate_folder_structure(nifti_path, modality)
                        file_result['folder_structure_valid'] = folder_validation['valid']
                        file_result['warnings'].extend(folder_validation['warnings'])
                        
                    else:
                        warning_msg = f"BidsGuess 값이 올바르지 않습니다: {json_path}"
                        logger.warning(warning_msg)
                        file_result['warnings'].append(warning_msg)
                else:
                    # 5. BidsGuess가 없는 경우
                    warning_msg = f"BidsGuess 키가 JSON 파일에 존재하지 않습니다: {json_path}"
                    logger.warning(warning_msg)
                    file_result['warnings'].append(warning_msg)
                    
            except (json.JSONDecodeError, IOError) as e:
                warning_msg = f"JSON 파일 읽기 오류: {json_path}, Error: {str(e)}"
                logger.warning(warning_msg)
                file_result['warnings'].append(warning_msg)
        
        validation_results[nifti_path] = file_result
    
    _log_validation_summary(validation_results)
    return validation_results


def _extract_data_type_and_modality(nifti_path):
    """
    PET 파일 경로에서 data_type과 modality를 추출합니다.

    Args:
        nifti_path (str): NIfTI 파일의 전체 경로

    Returns:
        tuple: (data_type, modality)
        - data_type: 항상 'pet' (PET 도메인은 고정)
        - modality: 항상 'pet' (PET 도메인은 고정)

    Note:
        PET은 MRI와 달리 data_type과 modality가 모두 'pet'으로 고정됩니다.
        파일명 예시: sub-xxx_ses-01_trc-18FFDG_run-01_pet.nii.gz
    """
    # PET은 data_type과 modality 모두 'pet'으로 고정
    return 'pet', 'pet'


def _validate_folder_structure(nifti_path, expected_modality):
    """
    PET 파일 경로의 폴더 구조를 검증합니다.

    Args:
        nifti_path (str): NIfTI 파일의 전체 경로
        expected_modality (str): 예상되는 모달리티 (PET의 경우 항상 'pet')

    Returns:
        dict: {'valid': bool, 'warnings': list}

    Note:
        PET 파일의 예상 경로: .../rawdata/sub-xxx/ses-01/pet/sub-xxx_ses-01_trc-XXX_run-01_pet.nii.gz
    """
    result = {'valid': False, 'warnings': []}

    # 파일 경로를 Path 객체로 변환
    path_obj = Path(nifti_path)
    parent_folders = [part for part in path_obj.parts]

    # PET의 경우 expected_modality는 항상 'pet'
    if 'pet' in parent_folders:
        # pet 폴더의 위치 찾기
        pet_index = parent_folders.index('pet')

        # 마지막 폴더인지 확인 (파일명 제외)
        # parent_folders[-1]은 파일명이므로 [-2]가 마지막 폴더
        if pet_index == len(parent_folders) - 2:
            result['valid'] = True
            logger.info(f"PET 폴더 구조 검증 성공: 'pet' 폴더가 올바른 위치에 있습니다.")
        else:
            warning_msg = f"PET 폴더가 존재하지만 올바른 위치에 있지 않습니다: {nifti_path}"
            logger.warning(warning_msg)
            result['warnings'].append(warning_msg)
    else:
        warning_msg = f"PET 폴더가 경로에 존재하지 않습니다: {nifti_path}"
        logger.warning(warning_msg)
        result['warnings'].append(warning_msg)

    return result


def _log_validation_summary(validation_results):
    """
    검증 결과 요약을 로그로 출력합니다.
    """
    total_files = len(validation_results)
    valid_files = sum(1 for result in validation_results.values() 
                     if result['nifti_exists'] and result['sidecar_json'] and result['folder_structure_valid'])  # 변경
    
    logger.info(f"BIDS 검증 완료: 총 {total_files}개 파일, {valid_files}개 파일 검증 성공")
    
    # 경고가 있는 파일들 요약
    files_with_warnings = [(path, result) for path, result in validation_results.items() 
                          if result['warnings']]
    
    if files_with_warnings:
        logger.warning(f"{len(files_with_warnings)}개 파일에서 경고 발생")
        for path, result in files_with_warnings:
            logger.warning(f"경고 파일: {path}")
            for warning in result['warnings']:
                logger.warning(f"  - {warning}")