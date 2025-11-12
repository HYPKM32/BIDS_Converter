#/BDSP/civet_app/src/process/components/civet_cleanup.py
import os
import re
import logging
import subprocess
import gzip
import shutil

logger = logging.getLogger(__name__)


def bids_cleanup(execution_results):
    """
    CIVET 실행 결과 정리
    
    Args:
        execution_results (list): pcli.execute_commands() 반환값
    
    Returns:
        list: cleanup_results
    """
    logger.info(f"Starting CIVET cleanup for {len(execution_results)} results")
    
    cleanup_results = []
    
    for result in execution_results:
        if not result["success"]:
            logger.warning(f"Skipping failed result: index={result['index']}")
            continue
        
        logger.info(f"Processing result[{result['index']}]")
        
        output_dir = result["outputDir"]
        working_name = result["working_name"]
        moved_items = result["moved_items"]
        
        # 1. 필수 폴더 검증 (logs 제외)
        validate_required_folders(moved_items)
        
        # 2. 모든 파일 BIDS 형식으로 파일명 변경 (logs 포함)
        rename_all_files_to_bids(output_dir, working_name, moved_items)
        
        # 3. .mnc 파일만 .nii.gz로 변환
        convert_mnc_files_to_nii_gz(output_dir, moved_items)
        
        # 4. cleanup_result 생성 (logs 제외)
        cleanup_result = create_cleanup_result(
            output_dir=output_dir,
            working_name=working_name,
            moved_items=moved_items
        )
        
        cleanup_results.append(cleanup_result)
        logger.info(f"Cleanup completed for result[{result['index']}]")
    
    logger.info(f"CIVET cleanup completed: {len(cleanup_results)} results")
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
            logger.error(error_msg)
            raise ValueError(error_msg)
    
    logger.info("All required folders validated")


def extract_stage_task(filename, working_name):
    """
    파일명에서 stage task 추출
    
    Args:
        filename (str): 파일명
        working_name (str): working_name (예: sub-XXX_ses-01_run-01_exe-01_drv-civet)
        
    Returns:
        str: stage task (예: "cls_clean", "white_surface_left_81920")
             None: 추출 실패
    
    예시:
        sub-XXX_drv-civet_cls_clean.mnc → "cls_clean"
        sub-XXX_drv-civet_white_surface_left_81920.obj → "white_surface_left_81920"
        sub-XXX_drv-civet.options → "options" (logs 폴더)
    """
    # 1. working_name으로 시작하는지 확인
    if filename.startswith(working_name):
        # working_name_ 이후 추출
        after_working = filename[len(working_name) + 1:]  # +1은 언더스코어
    elif filename.startswith(working_name.rsplit('_', 1)[0]):
        # logs 파일의 경우: sub-XXX_drv-civet.XXX 형식
        # working_name에서 마지막 _drv-civet 제거 후 비교
        base_name = working_name.rsplit('_', 1)[0]  # sub-XXX_ses-01_run-01_exe-01
        # sub-XXX_drv-civet 부분 찾기
        prefix = '_'.join(working_name.split('_')[:-1])  # drv-civet 직전까지
        
        # 파일명이 "sub-XXX_drv-civet.XXX" 형식인지 확인
        if '_drv-civet.' in filename or '_drv-civet_' in filename:
            # _drv-civet. 이후 또는 _drv-civet_ 이후 추출
            if '_drv-civet.' in filename:
                after_working = filename.split('_drv-civet.', 1)[1]
            else:
                after_working = filename.split('_drv-civet_', 1)[1]
        else:
            logger.debug(f"Cannot extract stage_task from: {filename}")
            return None
    else:
        logger.debug(f"Filename doesn't start with working_name: {filename}")
        return None
    
    # 2. 확장자 제거
    extensions = ['.mnc', '.nii', '.nii.gz', '.obj', '.txt', '.dat', '.xfm', '.sm', '.png', 
                  '.log', '.finished', '.options']
    
    stage_task = after_working
    for ext in extensions:
        if after_working.endswith(ext):
            stage_task = after_working[:-len(ext)]
            break
    
    # 빈 문자열이면 확장자만 있는 경우
    if not stage_task:
        stage_task = after_working
    
    logger.debug(f"Extracted stage_task: '{stage_task}' from {filename}")
    return stage_task


def to_lower_camel(snake_str):
    """
    snake_case → lowerCamelCase 변환
    
    예시:
        "cls_clean" → "clsClean"
        "white_surface_left_81920" → "whiteSurfaceLeft81920"
        "t1_tal_to_7" → "t1TalTo7"
        "options" → "options"
    """
    # 빈 문자열이거나 언더스코어가 없으면 그대로 반환
    if not snake_str or '_' not in snake_str:
        return snake_str
    
    components = snake_str.split('_')
    # 첫 번째는 소문자 유지, 나머지는 capitalize
    return components[0] + ''.join(x.capitalize() for x in components[1:])


def rename_all_files_to_bids(output_dir, working_name, moved_items):
    """
    모든 파일을 BIDS 형식으로 파일명 변경 (logs 포함)
    
    변경 규칙:
        _drv-civet_XXX.ext → _drv-civet_stg-XXX.ext
        _drv-civet.ext → _drv-civet_stg-XXX.ext (logs)
        
        XXX는 lowerCamelCase로 변환
        .mnc 파일은 _T1w 추가
    
    Args:
        output_dir (str): 출력 디렉토리
        working_name (str): working_name
        moved_items (list): 이동된 파일 목록
    """
    logger.info("Renaming all files to BIDS format")
    
    renamed_count = 0
    
    for item in moved_items:
        old_path = os.path.join(output_dir, item)
        
        if not os.path.exists(old_path):
            logger.warning(f"File not found: {old_path}")
            continue
        
        # 파일명 추출
        dir_path = os.path.dirname(old_path)
        filename = os.path.basename(old_path)
        
        # stage task 추출
        stage_task = extract_stage_task(filename, working_name)
        
        if not stage_task:
            logger.warning(f"Could not extract stage task from: {filename}")
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
            # .mnc 파일은 _T1w 추가
            new_filename = f"{working_name}_stg-{stage_task_camel}_T1w{ext}"
        else:
            # 나머지는 확장자만 추가
            new_filename = f"{working_name}_stg-{stage_task_camel}{ext}"
        
        new_path = os.path.join(dir_path, new_filename)
        
        # 파일명 변경
        try:
            os.rename(old_path, new_path)
            renamed_count += 1
            logger.debug(f"Renamed: {filename} → {new_filename}")
        except Exception as e:
            logger.error(f"Failed to rename {filename}: {e}")
    
    logger.info(f"Renamed {renamed_count} files to BIDS format")


def convert_mnc_files_to_nii_gz(output_dir, moved_items):
    """
    .mnc 파일만 .nii.gz로 변환
    
    과정:
        1. .mnc → .nii 변환 (mnc2nii)
        2. .nii → .nii.gz 압축 (gzip)
        3. .mnc, .nii 파일 삭제
    
    Args:
        output_dir (str): 출력 디렉토리
        moved_items (list): 이동된 파일 목록
    """
    logger.info("Converting .mnc files to .nii.gz")
    
    # 변경된 파일명으로 .mnc 파일 찾기 (stg-XXX_T1w.mnc 형식)
    mnc_files = []
    
    for root, dirs, files in os.walk(output_dir):
        for file in files:
            if file.endswith('_T1w.mnc'):
                mnc_files.append(os.path.join(root, file))
    
    logger.info(f"Found {len(mnc_files)} .mnc files to convert")
    
    converted_count = 0
    
    for mnc_file in mnc_files:
        try:
            # 1. .mnc → .nii 변환
            nii_file = mnc_file[:-4] + '.nii'  # .mnc → .nii
            
            subprocess.run(
                ['mnc2nii', '-nii', mnc_file, nii_file],
                capture_output=True,
                text=True
            )
            
            logger.debug(f"Converted to NIfTI: {os.path.basename(nii_file)}")
            
            # 2. .nii → .nii.gz 압축
            gz_file = nii_file + '.gz'
            
            with open(nii_file, 'rb') as f_in:
                with gzip.open(gz_file, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            
            logger.debug(f"Compressed to: {os.path.basename(gz_file)}")
            
            # 3. 원본 .mnc, .nii 삭제
            os.remove(mnc_file)
            os.remove(nii_file)
            
            converted_count += 1
            logger.debug(f"Cleaned up: {os.path.basename(mnc_file)}, {os.path.basename(nii_file)}")
            
        except subprocess.CalledProcessError as e:
            logger.error(f"mnc2nii failed for {mnc_file}: {e}")
            logger.error(f"stderr: {e.stderr}")
            raise
        except Exception as e:
            logger.error(f"Conversion failed for {mnc_file}: {e}")
            raise
    
    logger.info(f"Converted {converted_count} .mnc files to .nii.gz")


def create_cleanup_result(output_dir, working_name, moved_items):
    """
    cleanup_result 생성 (logs 제외, stage별 분류)
    
    Returns:
        dict: {
            "outputDir": "...",
            "working_name": "...",
            "outputs": {
                "classify": {
                    "clsClean": "/path/to/file.nii.gz",
                    ...
                },
                "transforms": {
                    "linear": {...},
                    "nonlinear": {...},
                    "surfreg": {...}
                },
                ...
            }
        }
    """
    logger.info("Creating cleanup result")
    
    outputs = {}
    
    # output_dir 하위의 모든 파일 탐색
    for root, dirs, files in os.walk(output_dir):
        for file in files:
            full_path = os.path.join(root, file)
            
            # output_dir 기준 상대 경로
            rel_path = os.path.relpath(full_path, output_dir)
            
            # logs 폴더 제외
            if rel_path.startswith('logs/'):
                continue
            
            # 경로 분리
            parts = rel_path.split(os.sep)
            
            if len(parts) < 2:
                continue
            
            stage = parts[0]
            filename = parts[-1]
            
            # Stage task 추출 (변경된 파일명에서)
            # 예: sub-XXX_stg-clsClean_T1w.nii.gz → "clsClean"
            pattern = r'_stg-([a-zA-Z0-9]+)'
            match = re.search(pattern, filename)
            
            if not match:
                logger.debug(f"No stg- pattern in filename: {filename}")
                continue
            
            stage_task_camel = match.group(1)
            
            # outputs에 추가
            if stage not in outputs:
                outputs[stage] = {}
            
            # transforms는 하위 폴더 구조 유지 (linear, nonlinear, surfreg)
            if stage == "transforms" and len(parts) == 3:
                subdir = parts[1]
                
                if subdir not in outputs[stage]:
                    outputs[stage][subdir] = {}
                
                outputs[stage][subdir][stage_task_camel] = full_path
            else:
                outputs[stage][stage_task_camel] = full_path
            
            logger.debug(f"Added to outputs: {stage}/{stage_task_camel} = {full_path}")
    
    cleanup_result = {
        "outputDir": output_dir,
        "working_name": working_name,
        "outputs": outputs
    }
    
    logger.info(f"Cleanup result created with {len(outputs)} stages")
    return cleanup_result