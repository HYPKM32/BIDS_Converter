# /BDSP/defacer_app/src/process/components/sidecar.py
import os
import json
import logging
from utils.common import bdsp_walk
logger = logging.getLogger(__name__)


def make_sidecar_json(execution_results, process, package):
    """
    실행 결과를 기반으로 JSON 메타데이터 파일(sidecar) 생성/업데이트
    모든 sidecar 생성 후 output_dir을 스캔하여 파일 목록 JSON 생성
    
    Args:
        execution_results (list): cli.execute_commands()의 반환값 (리스트)
                                [
                                    {
                                        "index": 0,
                                        "command": "...",
                                        "success": True,
                                        "input": "...",
                                        "output_dir": "...",
                                        "outputs": {...},
                                        ...
                                    },
                                    ...
                                ]
        process (str): 프로세스 이름
        package (str): 패키지 이름
    
    Returns:
        list: 각 실행 결과에 대응하는 sidecar 경로 리스트 (index 순서 유지)
              실패한 경우 해당 index에는 None 또는 빈 문자열
              예: ['/path/to/sidecar1.json', '/path/to/sidecar2.json']
    """
    sidecar_paths = []
    output_dirs = set()  # 중복 제거를 위한 set
    
    # execution_results가 리스트인지 확인
    if not isinstance(execution_results, list):
        logger.error(f"execution_results must be a list, got {type(execution_results)}")
        return []
    
    # 각 실행 결과에 대해 sidecar 생성 (순서 유지)
    for idx, execution_result in enumerate(execution_results):
        # 실패한 실행은 빈 문자열 추가
        if not execution_result.get('success', False):
            logger.warning(f"Skipping failed execution at index {idx}: {execution_result.get('command')}")
            sidecar_paths.append('')
            continue
        
        # output_dir 수집
        output_dir = execution_result.get('output_dir', '')
        if output_dir:
            output_dirs.add(output_dir)
        
        try:
            sidecar_path = _create_single_sidecar(execution_result, process, package)
            sidecar_paths.append(sidecar_path if sidecar_path else '')
            logger.info(f"Created sidecar for index {idx}: {sidecar_path}")
        except Exception as e:
            logger.error(f"Failed to create sidecar for index {idx}: {e}")
            # 한 개 실패해도 계속 진행, 해당 위치에 빈 문자열
            sidecar_paths.append('')
            continue
    
    logger.info(f"Created {len([p for p in sidecar_paths if p])} sidecar file(s) out of {len(execution_results)}")
    
    # 모든 sidecar 생성 후 각 output_dir에 대해 bdsp_walk 실행
    for output_dir in output_dirs:
        if os.path.exists(output_dir):
            try:
                logger.info(f"Running bdsp_walk on output_dir: {output_dir}")
                bdsp_walk(output_dir)
                logger.info(f"Successfully created file list JSON in: {output_dir}")
            except Exception as e:
                logger.error(f"Failed to run bdsp_walk on {output_dir}: {e}")
        else:
            logger.warning(f"Output directory does not exist: {output_dir}")
    
    return sidecar_paths


def _create_single_sidecar(execution_result, process, package):
    """
    단일 실행 결과에 대한 sidecar JSON 생성
    
    Args:
        execution_result (dict): 단일 실행 결과
        process (str): 프로세스 이름
        package (str): 패키지 이름
    
    Returns:
        str: 생성된 JSON 파일 경로 또는 None
    """
    # 1. input 파일 경로 가져오기
    input_path = execution_result.get('input', '')
    if not input_path:
        logger.warning("No input path in execution result")
        return None
    
    input_basename = os.path.basename(input_path)  # 예: "sub-01_T1w.nii.gz"
    
    if not input_basename.endswith('.nii.gz'):
        logger.warning(f"Input file doesn't end with .nii.gz: {input_basename}")
        return None
    
    # input과 같은 디렉토리에서 .json 파일 찾기
    input_dir = os.path.dirname(input_path)
    original_json_filename = input_basename.replace('.nii.gz', '.json')  # "sub-01_T1w.json"
    original_json_path = os.path.join(input_dir, original_json_filename)
    
    logger.info(f"Looking for original JSON: {original_json_path}")
    
    # 2. defaced_data 파일명 기반으로 새 JSON 파일명 생성
    outputs = execution_result.get('outputs', {})
    defaced_data_path = outputs.get('defaced_data', '')
    
    if not defaced_data_path:
        logger.warning("No defaced_data path in execution result")
        return None
    
    defaced_basename = os.path.basename(defaced_data_path)  # 예: "sub-01_T1w-defaced.nii.gz"
    
    if not defaced_basename.endswith('.nii.gz'):
        logger.warning(f"Defaced data doesn't end with .nii.gz: {defaced_basename}")
        return None
    
    # defaced_data와 같은 이름의 JSON 파일명
    new_json_filename = defaced_basename.replace('.nii.gz', '.json')  # "sub-01_T1w-defaced.json"
    output_dir = execution_result.get('output_dir', '')
    new_json_path = os.path.join(output_dir, new_json_filename)
    
    logger.info(f"Target JSON path: {new_json_path}")
    
    # 3. 원본 JSON 파일 존재 여부 확인 및 복사/생성
    metadata = {}
    
    if os.path.exists(original_json_path):
        logger.info(f"Original JSON file found, loading metadata")
        try:
            # 원본 JSON 읽기
            with open(original_json_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            logger.info(f"Loaded metadata from: {original_json_path}")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse original JSON file: {e}")
            metadata = {}
    else:
        logger.info(f"No original JSON file found at {original_json_path}, creating new metadata")
    
    # 4. derivatives 리스트 확인 및 초기화
    if 'derivatives' not in metadata:
        metadata['derivatives'] = []
        logger.info("Created new 'derivatives' list")
    
    # 5. 새로운 derivative 객체 생성
    derivative_entry = {
        'process': process,
        'package': package,
        'input': input_path,
        'output_dir': output_dir,
        'defaced_data': outputs.get('defaced_data', ''),
        'thumbnail': outputs.get('thumbnail_img', ''),
        'defacing_mask': outputs.get('defacing_mask', '')
    }
    
    # 6. derivatives 리스트에 추가
    metadata['derivatives'].append(derivative_entry)
    logger.info(f"Added derivative entry (process={process}, package={package})")
    
    # 7. 새 경로에 JSON 파일 저장
    try:
        os.makedirs(output_dir, exist_ok=True)
        with open(new_json_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        logger.info(f"Sidecar JSON file saved successfully: {new_json_path}")
        return new_json_path
    except Exception as e:
        logger.error(f"Failed to save sidecar JSON file: {e}")
        raise