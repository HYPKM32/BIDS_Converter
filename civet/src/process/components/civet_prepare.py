#/BDSP/civet_app/src/process/components/civet_prepare.py
import os
import logging
import subprocess
import shutil
import re
import hashlib

logger = logging.getLogger(__name__)

# 임시 작업 디렉토리 base path
TMP_BASE_DIR = "/BDSP/interfaces/tmp"


def prepare_civet_input(flag):
    """
    CIVET 파이프라인 실행을 위한 입력 데이터 전처리
    
    처리 과정:
    1. .nii.gz 파일을 gunzip으로 .nii 압축 해제 (원본 유지)
    2. outputDir을 해시로 변환하여 /BDSP/interfaces/tmp/{hash} 디렉토리 생성
    3. .nii 파일을 임시 디렉토리로 이동
    4. 이동된 위치에서 파일명 변경:
       - drv-canonical → drv-civet 변경
       - 모달리티 변경: T1w→t1, T2w→t2, PDw→pd
    5. run/exe 엔티티를 derivatives의 runNum/exeNum과 매칭
    6. nii2mnc로 .nii → .mnc 변환
    
    Args:
        flag (dict): 필터링된 flag 객체
        
    Returns:
        tuple: (flag, civet_working_mapping)
            - flag: 전처리된 flag 객체 (원본 수정됨)
            - civet_working_mapping: {outputDir: {"tmp_dir": 임시디렉토리, "working_name": 작업폴더명}} 딕셔너리
    """
    logger.info("Starting CIVET input preparation")
    
    derivatives_list = flag.get('derivatives', [])
    civet_working_mapping = {}
    
    if not derivatives_list:
        logger.warning("No derivatives found in flag")
        return flag, civet_working_mapping
    
    # 임시 base 디렉토리 생성
    os.makedirs(TMP_BASE_DIR, exist_ok=True)
    
    for idx, derivative in enumerate(derivatives_list):
        input_files = derivative.get('input', [])
        output_dir = derivative.get('outputDir', '')
        run_num = derivative.get('runNum', '')
        exe_num = derivative.get('exeNum', '')
        
        if not input_files or not output_dir:
            logger.warning(f"Skipping derivatives[{idx}]: missing input or outputDir")
            continue
        
        logger.info(f"Processing derivatives[{idx}]: run={run_num}, exe={exe_num}")
        logger.info(f"Original outputDir: {output_dir}")
        
        # outputDir을 해시로 변환
        path_hash = hash_path(output_dir)
        tmp_dir = os.path.join(TMP_BASE_DIR, path_hash)
        
        # 임시 디렉토리 생성
        os.makedirs(tmp_dir, exist_ok=True)
        logger.info(f"Created tmp directory: {tmp_dir}")
        logger.info(f"  Hash: {path_hash}")
        
        for input_file in input_files:
            if not input_file or not os.path.exists(input_file):
                logger.warning(f"Input file not found: {input_file}")
                continue
            
            try:
                # 1. 압축 해제 (.nii.gz → .nii)
                nii_file = decompress_if_needed(input_file)
                
                # 2. 임시 디렉토리로 이동 (원본 파일명 유지)
                original_filename = os.path.basename(nii_file)
                temp_destination = os.path.join(tmp_dir, original_filename)
                shutil.move(nii_file, temp_destination)
                logger.info(f"Moved to tmp: {temp_destination}")
                
                # 3. 임시 디렉토리에서 파일명 변경
                new_filename = rename_for_civet(
                    original_filename,
                    run_num,
                    exe_num
                )
                final_nii_path = os.path.join(tmp_dir, new_filename)
                os.rename(temp_destination, final_nii_path)
                logger.info(f"Renamed to: {new_filename}")
                
                # 4. nii2mnc 변환 (.nii → .mnc)
                mnc_filename = convert_nii_to_mnc(final_nii_path, tmp_dir)
                logger.info(f"Converted to MINC: {mnc_filename}")
                
                # 5. 작업폴더명 추출 (모달리티 및 확장자 제외)
                # .mnc 파일명 기준으로 추출
                working_name = extract_working_name(mnc_filename)
                
                # 6. 매핑 정보 저장
                civet_working_mapping[output_dir] = {
                    "tmp_dir": tmp_dir,
                    "working_name": working_name
                }
                
                logger.info(f"Prepared file: {mnc_filename}")
                logger.info(f"  Final location: {os.path.join(tmp_dir, mnc_filename)}")
                logger.info(f"  Working name: {working_name}")
                logger.info(f"  Mapped: {output_dir} -> {tmp_dir}")
                
            except Exception as e:
                logger.error(f"Failed to prepare input file {input_file}: {e}")
                raise
    
    logger.info("CIVET input preparation completed")
    logger.info(f"Working mapping: {civet_working_mapping}")
    
    return flag, civet_working_mapping


def hash_path(path):
    """
    경로를 SHA256 해시로 변환 (앞 16자리만 사용)
    
    Args:
        path (str): 해시할 경로
        
    Returns:
        str: 해시 문자열 (16자리)
    """
    hash_obj = hashlib.sha256(path.encode('utf-8'))
    hash_hex = hash_obj.hexdigest()[:16]
    logger.debug(f"Hashed path: {path} -> {hash_hex}")
    return hash_hex


def decompress_if_needed(filepath):
    """
    .nii.gz 파일을 .nii로 압축 해제 (원본 유지)
    .nii 파일은 그대로 반환
    
    시도 순서:
    1. subprocess로 gunzip -k 실행 (빠름)
    2. 실패 시 Python gzip 모듈 사용 (fallback)
    
    Args:
        filepath (str): 입력 파일 경로
        
    Returns:
        str: .nii 파일 경로
    """
    if filepath.endswith('.nii.gz'):
        logger.info(f"Decompressing: {os.path.basename(filepath)}")
        
        nii_file = filepath[:-3]  # .nii.gz → .nii
        
        # 방법 1: subprocess로 gunzip 시도
        try:
            subprocess.run(
                ['gunzip', '-k', filepath],
                capture_output=True,  
                text=True             
            )
            
            if not os.path.exists(nii_file):
                raise FileNotFoundError(f"Decompressed file not found: {nii_file}")
            
            logger.info(f"Decompressed with gunzip: {os.path.basename(nii_file)}")
            return nii_file
            
        except (subprocess.CalledProcessError, FileNotFoundError, OSError) as e:
            logger.warning(f"gunzip failed: {e}, trying Python gzip module...")
            
            # 방법 2: Python gzip 모듈 사용 (fallback)
            try:
                import gzip
                
                with gzip.open(filepath, 'rb') as f_in:
                    with open(nii_file, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                
                if not os.path.exists(nii_file):
                    raise FileNotFoundError(f"Decompressed file not found: {nii_file}")
                
                logger.info(f"Decompressed with gzip module: {os.path.basename(nii_file)}")
                return nii_file
                
            except Exception as gzip_error:
                logger.error(f"gzip module also failed: {gzip_error}")
                raise
    
    elif filepath.endswith('.nii'):
        logger.info(f"Already .nii format: {os.path.basename(filepath)}")
        return filepath
    
    else:
        logger.warning(f"Unsupported file format: {filepath}")
        return filepath


def convert_nii_to_mnc(nii_filepath, output_dir):
    """
    nii2mnc를 사용하여 .nii 파일을 .mnc 파일로 변환
    
    Args:
        nii_filepath (str): 입력 .nii 파일 경로
        output_dir (str): 출력 디렉토리 경로
        
    Returns:
        str: 생성된 .mnc 파일명 (경로 제외)
        
    Raises:
        subprocess.CalledProcessError: nii2mnc 실행 실패 시
        FileNotFoundError: 변환된 파일이 생성되지 않은 경우
    """
    if not nii_filepath.endswith('.nii'):
        raise ValueError(f"Input file must be .nii format: {nii_filepath}")
    
    # .nii → .mnc 파일명 생성
    nii_basename = os.path.basename(nii_filepath)
    mnc_basename = nii_basename[:-4] + '.mnc'  # .nii → .mnc
    mnc_filepath = os.path.join(output_dir, mnc_basename)
    
    logger.info(f"Converting NIfTI to MINC: {nii_basename} → {mnc_basename}")
    
    try:
        # nii2mnc 실행
        result = subprocess.run(
            ['nii2mnc', nii_filepath, mnc_filepath],
            capture_output=True,
            text=True
        )
        # 변환 성공 확인
        if not os.path.exists(mnc_filepath):
            raise FileNotFoundError(f"MINC file not created: {mnc_filepath}")
        
        logger.info(f"Successfully converted to MINC: {mnc_basename}")
        
        if result.stdout:
            logger.debug(f"nii2mnc stdout: {result.stdout}")
        
        # 원본 .nii 파일 삭제 (더 이상 필요 없음)
        os.remove(nii_filepath)
        logger.info(f"Removed original NIfTI file: {nii_basename}")
        
        return mnc_basename
        
    except subprocess.CalledProcessError as e:
        logger.error(f"nii2mnc failed: {e}")
        logger.error(f"stdout: {e.stdout}")
        logger.error(f"stderr: {e.stderr}")
        raise
    
    except Exception as e:
        logger.error(f"Error during NIfTI to MINC conversion: {e}")
        raise


def rename_for_civet(filename, run_num, exe_num):
    """
    CIVET 파이프라인 규칙에 맞게 파일명 변경
    
    변경 규칙:
    1. drv-XXX → drv-civet 변경
    2. exe-XX가 없으면 run-XX 뒤에 exe-{exe_num} 추가
    3. drv 엔티티가 없으면 exe-XX 뒤에 drv-civet 추가
    4. 모달리티 변경: T1w→t1, T2w→t2, PDw→pd
    5. run-XX, exe-XX 엔티티를 runNum, exeNum과 매칭
    
    Args:
        filename (str): 원본 파일명
        run_num (str): derivatives의 runNum
        exe_num (str): derivatives의 exeNum
        
    Returns:
        str: 변경된 파일명
    """
    logger.debug(f"Renaming: {filename}")
    
    # 확장자 제거 (.nii 또는 .nii.gz)
    if filename.endswith('.nii.gz'):
        base_name = filename[:-7]
        extension = '.nii'  # gunzip 후이므로 .nii
    elif filename.endswith('.nii'):
        base_name = filename[:-4]
        extension = '.nii'
    else:
        base_name = filename
        extension = ''
    
    # 파일명을 언더스코어로 분리
    parts = base_name.split('_')
    
    # 1. exe 엔티티 처리 (먼저 처리)
    has_exe = False
    exe_index = -1
    new_parts = []
    
    for i, part in enumerate(parts):
        if part.startswith('exe-'):
            has_exe = True
            exe_index = len(new_parts)  # 새 리스트에서의 인덱스
            # exe 값 검증 및 교체
            file_exe_num = part.split('-')[1] if '-' in part else ''
            if file_exe_num != exe_num:
                logger.info(f"exe mismatch: file has {part}, expected exe-{exe_num}")
                new_parts.append(f'exe-{exe_num}')
            else:
                new_parts.append(part)
        else:
            new_parts.append(part)
    
    # exe가 없으면 run 뒤에 추가
    if not has_exe:
        run_index = -1
        for i, part in enumerate(new_parts):
            if part.startswith('run-'):
                run_index = i
                break
        
        if run_index >= 0:
            # run-XX 바로 뒤에 exe-{exe_num} 삽입
            new_parts.insert(run_index + 1, f'exe-{exe_num}')
            exe_index = run_index + 1
            logger.debug(f"Inserted exe-{exe_num} after run-{run_num}")
        else:
            # run도 없으면 모달리티 앞에 추가
            new_parts.insert(-1, f'exe-{exe_num}')
            exe_index = len(new_parts) - 2
            logger.debug(f"Inserted exe-{exe_num} before modality")
    
    # 2. drv 엔티티 처리
    has_drv = False
    final_parts = []
    
    for i, part in enumerate(new_parts):
        if part.startswith('drv-'):
            # 기존 drv-XXX → drv-civet으로 변경
            final_parts.append('drv-civet')
            has_drv = True
            logger.debug(f"Replaced {part} with drv-civet")
        else:
            final_parts.append(part)
    
    # drv가 없으면 exe-XX 뒤에 추가
    if not has_drv:
        # exe 위치 다시 찾기 (final_parts 기준)
        exe_pos = -1
        for i, part in enumerate(final_parts):
            if part.startswith('exe-'):
                exe_pos = i
                break
        
        if exe_pos >= 0:
            # exe-XX 바로 뒤에 drv-civet 삽입
            final_parts.insert(exe_pos + 1, 'drv-civet')
            logger.debug(f"Inserted drv-civet after exe-{exe_num}")
        else:
            # exe도 없으면 마지막 앞(모달리티 앞)에 추가
            final_parts.insert(-1, 'drv-civet')
            logger.debug(f"Inserted drv-civet before modality")
    
    base_name = '_'.join(final_parts)
    
    # 3. 모달리티 변경
    modality_map = {
        'T1w': 't1',
        'T2w': 't2',
        'PDw': 'pd'
    }
    
    for old_mod, new_mod in modality_map.items():
        # 파일명 끝부분의 모달리티 변경 (확장자 직전)
        base_name = re.sub(f'_{old_mod}$', f'_{new_mod}', base_name)
    
    # 4. run 엔티티 확인 및 수정
    run_match = re.search(r'run-(\d+)', base_name)
    if run_match:
        file_run_num = run_match.group(1)
        if file_run_num != run_num:
            logger.info(f"run mismatch: file has run-{file_run_num}, expected run-{run_num}")
            base_name = re.sub(r'run-\d+', f'run-{run_num}', base_name)
    else:
        logger.warning(f"No run entity found in filename: {filename}")
    
    new_filename = base_name + extension
    
    logger.debug(f"Renamed to: {new_filename}")
    return new_filename


def extract_working_name(filename):
    """
    파일명에서 작업폴더명 추출 (마지막 모달리티 및 확장자 제외)
    
    예시:
        sub-2cna00001Hanyangparknm_ses-01_run-01_exe-01_drv-civet_t1.mnc
        → sub-2cna00001Hanyangparknm_ses-01_run-01_exe-01_drv-civet
    
    Args:
        filename (str): 변환된 파일명 (.nii 또는 .mnc)
        
    Returns:
        str: 작업폴더명 (모달리티 및 확장자 제외)
    """
    # 확장자 제거
    if filename.endswith('.nii.gz'):
        base_name = filename[:-7]
    elif filename.endswith('.nii'):
        base_name = filename[:-4]
    elif filename.endswith('.mnc'):
        base_name = filename[:-4]
    else:
        base_name = filename
    
    # 마지막 언더스코어와 모달리티 제거 (_t1, _t2, _pd 등)
    # 패턴: 마지막 _로 시작하는 모달리티 부분
    working_name = re.sub(r'_[a-z0-9]+$', '', base_name)
    
    logger.debug(f"Extracted working name: {working_name} from {filename}")
    return working_name