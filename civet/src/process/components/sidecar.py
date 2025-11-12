# /BDSP/civet_app/src/process/components/sidecar.py
import os
import json
import logging
from utils.common import bdsp_walk

logger = logging.getLogger(__name__)


def make_sidecar_json(execution_results, cleanup_results, process, package, space):
    """
    CIVET 실행 결과를 기반으로 JSON 메타데이터 파일(sidecar) 생성/업데이트
    모든 sidecar 생성 후 output_dir을 스캔하여 파일 목록 JSON 생성
    
    Args:
        execution_results (list): pcli.execute_commands()의 반환값
                                [
                                    {
                                        "index": 0,
                                        "command": "...",
                                        "success": True,
                                        "outputDir": "...",
                                        "working_name": "...",
                                        "derivative": {
                                            "input": ["..."],
                                            "outputDir": "...",
                                            "runNum": "01",
                                            "exeNum": "01"
                                        },
                                        ...
                                    },
                                    ...
                                ]
        cleanup_results (list): civet_cleanup.bids_cleanup()의 반환값
                               [
                                   {
                                       "outputDir": "...",
                                       "working_name": "...",
                                       "outputs": {
                                           "classify": {...},
                                           "transforms": {...},
                                           "surfaces": {...},
                                           ...
                                       }
                                   },
                                   ...
                               ]
        process (str): 프로세스 이름 (예: "T1wPreprocess")
        package (str): 패키지 이름 (예: "civet")
        space (str): 공간 정보 (예: "orig")
    
    Returns:
        list: 각 실행 결과에 대응하는 sidecar 경로 리스트 (index 순서 유지)
              실패한 경우 해당 index에는 빈 문자열
              예: ['/path/to/sidecar1.json', '/path/to/sidecar2.json']
    """
    sidecar_paths = []
    output_dirs = set()  # 중복 제거를 위한 set
    
    # execution_results가 리스트인지 확인
    if not isinstance(execution_results, list):
        logger.error(f"execution_results must be a list, got {type(execution_results)}")
        return []
    
    # cleanup_results가 리스트인지 확인
    if not isinstance(cleanup_results, list):
        logger.error(f"cleanup_results must be a list, got {type(cleanup_results)}")
        return []
    
    # 길이 일치 확인
    if len(execution_results) != len(cleanup_results):
        logger.error(
            f"Length mismatch: execution_results={len(execution_results)}, "
            f"cleanup_results={len(cleanup_results)}"
        )
        return []
    
    # 각 실행 결과에 대해 sidecar 생성 (순서 유지)
    for idx, (execution_result, cleanup_result) in enumerate(zip(execution_results, cleanup_results)):
        # 실패한 실행은 빈 문자열 추가
        if not execution_result.get('success', False):
            logger.warning(f"Skipping failed execution at index {idx}: {execution_result.get('command')}")
            sidecar_paths.append('')
            continue
        
        # output_dir 수집
        output_dir = cleanup_result.get('outputDir', '')
        if output_dir:
            output_dirs.add(output_dir)
        
        try:
            sidecar_path = _create_single_sidecar(
                execution_result,
                cleanup_result,
                process,
                package,
                space
            )
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


def _create_single_sidecar(execution_result, cleanup_result, process, package, space):
    """
    단일 실행 결과에 대한 sidecar JSON 생성
    
    Args:
        execution_result (dict): 단일 실행 결과 (pcli 출력)
        cleanup_result (dict): 단일 cleanup 결과 (civet_cleanup 출력)
        process (str): 프로세스 이름
        package (str): 패키지 이름
        space (str): 공간 정보
    
    Returns:
        str: 생성된 JSON 파일 경로 또는 None
    """
    # 1. input 파일 경로 가져오기 (derivative에서)
    derivative = execution_result.get('derivative', {})
    input_list = derivative.get('input', [])
    
    if not input_list or len(input_list) == 0:
        logger.warning("No input path in derivative")
        return None
    
    input_path = input_list[0]  # 첫 번째 input 파일
    input_basename = os.path.basename(input_path)  # 예: "sub-01_drv-canonical_T1w.nii.gz"
    
    if not input_basename.endswith('.nii.gz'):
        logger.warning(f"Input file doesn't end with .nii.gz: {input_basename}")
        return None
    
    # 모달리티 추출 (T1w, T2w, PDw 등)
    # 예: sub-XXX_drv-canonical_T1w.nii.gz → T1w
    modality = _extract_modality(input_basename)
    if not modality:
        logger.warning(f"Could not extract modality from: {input_basename}")
        return None
    
    logger.info(f"Extracted modality: {modality}")
    
    # input과 같은 디렉토리에서 .json 파일 찾기
    input_dir = os.path.dirname(input_path)
    original_json_filename = input_basename.replace('.nii.gz', '.json')
    original_json_path = os.path.join(input_dir, original_json_filename)
    
    logger.info(f"Looking for original JSON: {original_json_path}")
    
    # 2. working_name 기반으로 새 JSON 파일명 생성
    working_name = cleanup_result.get('working_name', '')
    if not working_name:
        logger.warning("No working_name in cleanup_result")
        return None
    
    # 파일명: {working_name}_{modality}.json
    new_json_filename = f"{working_name}_{modality}.json"
    output_dir = cleanup_result.get('outputDir', '')
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
    # cleanup_result의 outputs를 그대로 저장 (옵션 A)
    derivative_entry = {
        'process': process,
        'space': space,
        'package': package,
        'input': input_path,
        'output_dir': output_dir,
        'outputs': cleanup_result.get('outputs', {})
    }
    
    # 6. derivatives 리스트에 추가
    metadata['derivatives'].append(derivative_entry)
    logger.info(f"Added derivative entry (process={process}, space={space}, package={package})")
    logger.info(f"  with {len(cleanup_result.get('outputs', {}))} output stages")
    
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


def _extract_modality(filename):
    """
    파일명에서 모달리티 추출
    
    Args:
        filename (str): 파일명 (예: "sub-01_drv-canonical_T1w.nii.gz")
    
    Returns:
        str: 모달리티 (예: "T1w", "T2w", "PDw", 또는 임의의 modality)
             None: 추출 실패
    
    예시:
        "sub-01_drv-canonical_T1w.nii.gz" → "T1w"
        "sub-01_ses-01_run-01_T2w.nii.gz" → "T2w"
        "sub-01_ses-01_CustomModality.nii.gz" → "CustomModality"
    """
    # .nii.gz 제거
    if filename.endswith('.nii.gz'):
        basename = filename[:-7]
    elif filename.endswith('.nii'):
        basename = filename[:-4]
    else:
        logger.warning(f"Unsupported file extension: {filename}")
        return None
    
    # 언더스코어로 분리
    parts = basename.split('_')
    
    # 마지막 부분이 modality
    if len(parts) > 0:
        modality = parts[-1]
        
        # 빈 문자열이 아니면 반환
        if modality:
            logger.debug(f"Extracted modality: '{modality}' from {filename}")
            return modality
    
    logger.warning(f"Could not extract modality from filename: {filename}")
    return None