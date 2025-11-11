# /BDSP/civet_app/src/process/mock/mock_civet_cleanup.py
"""
테스트용 mock civet_cleanup - 실제 파일 변환 없이 파일명만 변경

실제 civet_cleanup.py와의 차이점:
1. validate_required_folders: moved_items만 확인 (실제 파일 체크 안함)
2. rename_all_files_to_bids: 실제 파일 rename 수행
3. convert_mnc_files_to_nii_gz_mock: mnc2nii, gzip 없이 파일명만 .mnc → .nii.gz 변경
4. create_cleanup_result: 변경된 파일명 기반으로 outputs 생성

사용법:
    # main.py에서:
    # from process.components import civet_cleanup  # 원본
    from process.mock import mock_civet_cleanup as civet_cleanup  # 테스트용
"""

import os
import re
import logging
import time

logger = logging.getLogger(__name__)


def bids_cleanup(execution_results):
    """
    CIVET 실행 결과 정리 (Mock 버전)
    
    실제 파일 변환 없이 파일명만 BIDS 형식으로 변경
    
    Args:
        execution_results (list): pcli.execute_commands() 반환값
    
    Returns:
        list: cleanup_results
    """
    logger.warning("=" * 80)
    logger.warning("USING MOCK CIVET_CLEANUP - NO REAL FILE CONVERSION")
    logger.warning("Only renaming files without mnc2nii/gzip conversion")
    logger.warning("=" * 80)
    
    logger.info(f"[MOCK] Starting CIVET cleanup for {len(execution_results)} results")
    
    # 처리 시뮬레이션 (0.5초 대기)
    time.sleep(0.5)
    
    cleanup_results = []
    
    for result in execution_results:
        if not result["success"]:
            logger.warning(f"[MOCK] Skipping failed result: index={result['index']}")
            continue
        
        logger.info(f"[MOCK] Processing result[{result['index']}]")
        
        output_path = result["output_path"]
        working_name = result["working_name"]
        moved_items = result["moved_items"]
        
        # 1. 필수 폴더 검증 (logs 제외)
        validate_required_folders(moved_items)
        
        # 2. 모든 파일 BIDS 형식으로 파일명 변경
        rename_all_files_to_bids(output_path, working_name, moved_items)
        
        # 3. .mnc 파일을 .nii.gz로 파일명만 변경 (실제 변환 없음)
        convert_mnc_files_to_nii_gz_mock(output_path)
        
        # 4. cleanup_result 생성
        cleanup_result = create_cleanup_result(
            output_path=output_path,
            working_name=working_name
        )
        
        cleanup_results.append(cleanup_result)
        logger.info(f"[MOCK] Cleanup completed for result[{result['index']}]")
    
    logger.info(f"[MOCK] CIVET cleanup completed: {len(cleanup_results)} results")
    logger.warning("=" * 80)
    logger.warning("MOCK CIVET_CLEANUP FINISHED")
    logger.warning("=" * 80)
    
    return cleanup_results


def validate_required_folders(moved_items):
    """
    필수 폴더가 모두 존재하는지 검증 (logs 제외)
    
    Args:
        moved_items (list): 이동된 파일 목록
        
    Raises:
        ValueError: 필수 폴더가 없는 경우
    """
    required_folders = [
        "classify",
        "transforms",
        "final",
        "verify",
        "temp",
        "native",
        "thickness",
        "surfaces",
        "mask"
    ]
    
    for folder in required_folders:
        has_folder = any(item.startswith(f"{folder}/") for item in moved_items)
        
        if not has_folder:
            error_msg = f"Missing required CIVET output folder: {folder}"
            logger.error(f"[MOCK] {error_msg}")
            raise ValueError(error_msg)
    
    logger.info("[MOCK] All required folders validated")


def extract_stage_task(filename, working_name):
    """
    파일명에서 stage task 추출
    
    Args:
        filename (str): 파일명
        working_name (str): working_name
        
    Returns:
        str: stage task 또는 None
    """
    # working_name으로 시작하는지 확인
    if filename.startswith(working_name):
        after_working = filename[len(working_name) + 1:]
    elif filename.startswith(working_name.rsplit('_', 1)[0]):
        # logs 파일 처리
        if '_drv-civet.' in filename or '_drv-civet_' in filename:
            if '_drv-civet.' in filename:
                after_working = filename.split('_drv-civet.', 1)[1]
            else:
                after_working = filename.split('_drv-civet_', 1)[1]
        else:
            logger.debug(f"[MOCK] Cannot extract stage_task from: {filename}")
            return None
    else:
        logger.debug(f"[MOCK] Filename doesn't start with working_name: {filename}")
        return None
    
    # 확장자 제거
    extensions = ['.mnc', '.nii', '.nii.gz', '.obj', '.txt', '.dat', '.xfm', '.sm', '.png', 
                  '.log', '.finished', '.options']
    
    stage_task = after_working
    for ext in extensions:
        if after_working.endswith(ext):
            stage_task = after_working[:-len(ext)]
            break
    
    if not stage_task:
        stage_task = after_working
    
    return stage_task


def to_lower_camel(snake_str):
    """
    snake_case → lowerCamelCase 변환
    
    예시:
        "cls_clean" → "clsClean"
        "white_surface_left_81920" → "whiteSurfaceLeft81920"
    """
    if not snake_str or '_' not in snake_str:
        return snake_str
    
    components = snake_str.split('_')
    return components[0] + ''.join(x.capitalize() for x in components[1:])


def rename_all_files_to_bids(output_path, working_name, moved_items):
    """
    모든 파일을 BIDS 형식으로 파일명 변경
    
    변경 규칙:
        원본: {working_name}_{task}.ext
        변경: {working_name}_stg-{taskCamel}.ext
        .mnc 파일: {working_name}_stg-{taskCamel}_T1w.mnc
    
    Args:
        output_path (str): 출력 디렉토리
        working_name (str): working_name
        moved_items (list): 이동된 파일 목록
    """
    logger.info("[MOCK] Renaming all files to BIDS format")
    
    renamed_count = 0
    
    for item in moved_items:
        old_path = os.path.join(output_path, item)
        
        if not os.path.exists(old_path):
            logger.warning(f"[MOCK] File not found: {old_path}")
            continue
        
        # 파일명 추출
        dir_path = os.path.dirname(old_path)
        filename = os.path.basename(old_path)
        
        # stage task 추출
        stage_task = extract_stage_task(filename, working_name)
        
        if not stage_task:
            logger.warning(f"[MOCK] Could not extract stage task from: {filename}")
            continue
        
        # lowerCamelCase 변환
        stage_task_camel = to_lower_camel(stage_task)
        
        # 확장자 추출
        ext = ''
        for extension in ['.nii.gz', '.mnc', '.obj', '.txt', '.dat', '.xfm', '.sm', '.png', 
                          '.log', '.finished', '.options']:
            if filename.endswith(extension):
                ext = extension
                break
        
        # 새 파일명 생성
        if ext == '.mnc':
            new_filename = f"{working_name}_stg-{stage_task_camel}_T1w{ext}"
        else:
            new_filename = f"{working_name}_stg-{stage_task_camel}{ext}"
        
        new_path = os.path.join(dir_path, new_filename)
        
        # 파일명 변경
        try:
            os.rename(old_path, new_path)
            renamed_count += 1
            logger.debug(f"[MOCK] Renamed: {filename} → {new_filename}")
        except Exception as e:
            logger.error(f"[MOCK] Failed to rename {filename}: {e}")
    
    logger.info(f"[MOCK] Renamed {renamed_count} files to BIDS format")


def convert_mnc_files_to_nii_gz_mock(output_path):
    """
    .mnc 파일을 .nii.gz로 변환 (Mock 버전)
    
    실제 mnc2nii, gzip 변환 없이 파일명만 .mnc → .nii.gz로 변경
    
    Args:
        output_path (str): 출력 디렉토리
    """
    logger.info("[MOCK] Converting .mnc files to .nii.gz (filename only, no actual conversion)")
    
    # _T1w.mnc로 끝나는 파일 찾기
    mnc_files = []
    
    for root, dirs, files in os.walk(output_path):
        for file in files:
            if file.endswith('_T1w.mnc'):
                mnc_files.append(os.path.join(root, file))
    
    logger.info(f"[MOCK] Found {len(mnc_files)} .mnc files to convert")
    
    converted_count = 0
    
    for mnc_file in mnc_files:
        try:
            # .mnc → .nii.gz로 파일명만 변경
            nii_gz_file = mnc_file[:-4] + '.nii.gz'
            
            os.rename(mnc_file, nii_gz_file)
            
            converted_count += 1
            logger.debug(f"[MOCK] Renamed: {os.path.basename(mnc_file)} → {os.path.basename(nii_gz_file)}")
            
        except Exception as e:
            logger.error(f"[MOCK] Rename failed for {mnc_file}: {e}")
            raise
    
    logger.info(f"[MOCK] Converted {converted_count} .mnc files to .nii.gz (filename only)")


def create_cleanup_result(output_path, working_name):
    """
    cleanup_result 생성 (logs 제외, stage별 분류)
    
    실제 파일 시스템을 스캔하여 outputs 딕셔너리 생성
    
    Args:
        output_path (str): 출력 디렉토리
        working_name (str): working_name
        
    Returns:
        dict: cleanup_result
    """
    logger.info("[MOCK] Creating cleanup result")
    
    outputs = {}
    
    # output_path 하위의 모든 파일 탐색
    for root, dirs, files in os.walk(output_path):
        for file in files:
            full_path = os.path.join(root, file)
            
            # output_path 기준 상대 경로
            rel_path = os.path.relpath(full_path, output_path)
            
            # logs 폴더 제외
            if rel_path.startswith('logs/'):
                continue
            
            # 경로 분리
            parts = rel_path.split(os.sep)
            
            if len(parts) < 2:
                continue
            
            stage = parts[0]
            filename = parts[-1]
            
            # _stg-{task} 패턴 추출
            pattern = r'_stg-([a-zA-Z0-9]+)'
            match = re.search(pattern, filename)
            
            if not match:
                logger.debug(f"[MOCK] No stg- pattern in filename: {filename}")
                continue
            
            stage_task_camel = match.group(1)
            
            # outputs에 추가
            if stage not in outputs:
                outputs[stage] = {}
            
            # transforms는 3-depth 구조 (linear, nonlinear, surfreg)
            if stage == "transforms" and len(parts) == 3:
                subdir = parts[1]
                
                if subdir not in outputs[stage]:
                    outputs[stage][subdir] = {}
                
                outputs[stage][subdir][stage_task_camel] = full_path
            else:
                outputs[stage][stage_task_camel] = full_path
            
            logger.debug(f"[MOCK] Added to outputs: {stage}/{stage_task_camel}")
    
    cleanup_result = {
        "output_path": output_path,
        "working_name": working_name,
        "outputs": outputs
    }
    
    # 각 stage별 파일 개수 로깅
    logger.info(f"[MOCK] Cleanup result created with {len(outputs)} stages:")
    for stage, stage_outputs in outputs.items():
        if stage == "transforms":
            total_files = sum(len(v) for v in stage_outputs.values() if isinstance(v, dict))
            logger.info(f"[MOCK]   - {stage}: {total_files} files")
        else:
            logger.info(f"[MOCK]   - {stage}: {len(stage_outputs)} files")
    
    return cleanup_result