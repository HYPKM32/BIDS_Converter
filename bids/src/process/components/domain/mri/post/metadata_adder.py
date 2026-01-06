import os
import json
import yaml
import re
import logging
import pydicom
from pathlib import Path
from globals import DICOM_METADATA, PARREC_METADATA

logger = logging.getLogger(__name__)


def _get_lowercase_key_map(sidecar_data: dict) -> dict:
    """
    sidecar JSON의 키들을 소문자로 매핑한 딕셔너리 반환

    Args:
        sidecar_data: sidecar JSON 데이터

    Returns:
        dict: {lowercase_key: original_key} 매핑
    """
    return {k.lower(): k for k in sidecar_data.keys()}


def _key_exists(sidecar_data: dict, key: str, lowercase_map: dict) -> bool:
    """
    대소문자 구분 없이 키 존재 여부 확인

    Args:
        sidecar_data: sidecar JSON 데이터
        key: 찾을 키
        lowercase_map: 소문자 매핑 딕셔너리

    Returns:
        bool: 키 존재 여부
    """
    return key.lower() in lowercase_map


def _parse_dicom_tag(tag_str: str) -> tuple:
    """
    DICOM 태그 문자열을 파싱
    예: "(0018,0087)" -> (0x0018, 0x0087)

    Args:
        tag_str: DICOM 태그 문자열

    Returns:
        tuple: (group, element)
    """
    match = re.match(r'\(([0-9A-Fa-f]{4}),([0-9A-Fa-f]{4})\)', tag_str)
    if match:
        return (int(match.group(1), 16), int(match.group(2), 16))
    return None


def _extract_entity_from_filename(filename: str, entity: str) -> str:
    """
    BIDS 파일명에서 특정 entity 값 추출
    예: sub-01_ses-01_trc-AV45_pet.nii.gz에서 trc -> AV45

    Args:
        filename: BIDS 파일명
        entity: 추출할 entity (예: 'trc')

    Returns:
        str: entity 값 또는 'unknown'
    """
    pattern = rf'{entity}-([^_]+)'
    match = re.search(pattern, filename)
    if match:
        return match.group(1)
    return 'unknown'


def _get_dicom_value_by_tag(dicom_path: str, tag: tuple) -> str:
    """
    DICOM 파일에서 특정 태그 값 추출

    Args:
        dicom_path: DICOM 파일 경로
        tag: DICOM 태그 튜플

    Returns:
        str: 태그 값 또는 None
    """
    try:
        ds = pydicom.dcmread(dicom_path, stop_before_pixels=True)
        if tag in ds:
            value = ds[tag].value
            if value is not None:
                return str(value)
    except Exception as e:
        logger.debug(f"Failed to read DICOM tag {tag}: {e}")
    return None


def _get_dicom_value_by_keyword(dicom_path: str, keyword: str) -> str:
    """
    DICOM 파일에서 키워드로 값 추출

    Args:
        dicom_path: DICOM 파일 경로
        keyword: DICOM 키워드

    Returns:
        str: 키워드 값 또는 None
    """
    try:
        ds = pydicom.dcmread(dicom_path, stop_before_pixels=True)
        if hasattr(ds, keyword):
            value = getattr(ds, keyword)
            if value is not None:
                return str(value)
    except Exception as e:
        logger.debug(f"Failed to read DICOM keyword {keyword}: {e}")
    return None


def _find_dicom_file(source_path: str) -> str:
    """
    소스 경로에서 DICOM 파일 찾기

    Args:
        source_path: 소스 디렉토리 경로

    Returns:
        str: DICOM 파일 경로 또는 None
    """
    source_dir = Path(source_path)
    if not source_dir.exists():
        return None

    # 일반적인 DICOM 확장자들
    for ext in ['*.dcm', '*.DCM', '*.dicom', '*.DICOM', '*']:
        for f in source_dir.rglob(ext):
            if f.is_file() and not f.name.startswith('.'):
                try:
                    # DICOM 파일인지 확인
                    pydicom.dcmread(str(f), stop_before_pixels=True)
                    return str(f)
                except:
                    continue
    return None


def _load_yaml_config(format_type: str) -> dict:
    """
    포맷 타입에 따른 YAML 설정 로드

    Args:
        format_type: 'DICOM' 또는 'PARREC'

    Returns:
        dict: YAML 설정 데이터
    """
    if format_type.upper() == 'DICOM':
        yaml_path = os.path.join(DICOM_METADATA, 'required_medata_mri.yaml')
    elif format_type.upper() == 'PARREC':
        yaml_path = os.path.join(PARREC_METADATA, 'required_medata_mri.yaml')
    else:
        logger.warning(f"Unknown format type: {format_type}")
        return {}

    if not os.path.exists(yaml_path):
        logger.warning(f"YAML config not found: {yaml_path}")
        return {}

    try:
        with open(yaml_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        logger.error(f"Failed to load YAML config: {e}")
        return {}


def add_metadata(validation_results: dict, source_paths: dict, format_type: str) -> dict:
    """
    sidecar JSON에 누락된 메타데이터 추가

    Args:
        validation_results: bids_checker의 검증 결과 딕셔너리
            {nifti_path: {'sidecar_json': json_path, ...}}
        source_paths: {source_path: nifti_path} 매핑
        format_type: 'DICOM' 또는 'PARREC'

    Returns:
        dict: 업데이트된 validation_results
    """
    logger.info(f"Adding metadata for format: {format_type}")

    # YAML 설정 로드
    yaml_config = _load_yaml_config(format_type)
    if not yaml_config:
        logger.warning("No YAML config loaded, skipping metadata addition")
        return validation_results

    present_fields = yaml_config.get('present', {})
    absent_fields = yaml_config.get('absent', {})

    # source_path -> nifti_path 역매핑 생성
    nifti_to_source = {v: k for k, v in source_paths.items()}

    for nifti_path, result in validation_results.items():
        sidecar_json_path = result.get('sidecar_json')
        if not sidecar_json_path:
            logger.warning(f"No sidecar JSON for {nifti_path}, skipping")
            continue

        # sidecar JSON 로드
        try:
            with open(sidecar_json_path, 'r', encoding='utf-8') as f:
                sidecar_data = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load sidecar JSON {sidecar_json_path}: {e}")
            continue

        # 소문자 키 매핑 생성
        lowercase_map = _get_lowercase_key_map(sidecar_data)

        # 소스 경로에서 DICOM 파일 찾기
        source_path = nifti_to_source.get(nifti_path)
        dicom_file = None
        if source_path and format_type.upper() == 'DICOM':
            dicom_file = _find_dicom_file(source_path)

        filename = os.path.basename(nifti_path)
        updated = False

        # present 필드 처리: DICOM에서 추출
        for key, value_config in present_fields.items():
            if _key_exists(sidecar_data, key, lowercase_map):
                continue

            extracted_value = None

            # source가 bids:entity 형태인 경우
            if isinstance(value_config, dict) and 'source' in value_config:
                source = value_config['source']
                if source.startswith('bids:'):
                    entity = source.replace('bids:', '')
                    extracted_value = _extract_entity_from_filename(filename, entity)

            # 단일 태그 문자열인 경우
            elif isinstance(value_config, str):
                if dicom_file:
                    # 먼저 키워드로 시도
                    extracted_value = _get_dicom_value_by_keyword(dicom_file, key)
                    # 키워드로 못찾으면 태그로 시도
                    if extracted_value is None:
                        tag = _parse_dicom_tag(value_config)
                        if tag:
                            extracted_value = _get_dicom_value_by_tag(dicom_file, tag)

            # 태그 리스트인 경우: 순서대로 시도
            elif isinstance(value_config, list):
                if dicom_file:
                    # 먼저 키워드로 시도
                    extracted_value = _get_dicom_value_by_keyword(dicom_file, key)
                    # 키워드로 못찾으면 태그들 순서대로 시도
                    if extracted_value is None:
                        for tag_str in value_config:
                            tag = _parse_dicom_tag(tag_str)
                            if tag:
                                extracted_value = _get_dicom_value_by_tag(dicom_file, tag)
                                if extracted_value:
                                    break

            # 값을 찾았으면 추가, 못찾았으면 기본값("unknown") 추가
            if extracted_value:
                sidecar_data[key] = extracted_value
                updated = True
                logger.info(f"Added {key}={extracted_value} to {sidecar_json_path}")
            else:
                # 키워드, 태그 모두 실패 시 기본값 사용
                default_value = "unknown"
                sidecar_data[key] = default_value
                updated = True
                logger.info(f"Added {key}={default_value} (fallback) to {sidecar_json_path}")

        # absent 필드 처리: 기본값 사용
        for key, default_value in absent_fields.items():
            if _key_exists(sidecar_data, key, lowercase_map):
                continue

            sidecar_data[key] = default_value
            updated = True
            logger.info(f"Added {key}={default_value} (default) to {sidecar_json_path}")

        # 변경사항 저장
        if updated:
            try:
                with open(sidecar_json_path, 'w', encoding='utf-8') as f:
                    json.dump(sidecar_data, f, indent=2, ensure_ascii=False)
                logger.info(f"Updated sidecar JSON: {sidecar_json_path}")
            except Exception as e:
                logger.error(f"Failed to save sidecar JSON {sidecar_json_path}: {e}")

    return validation_results
