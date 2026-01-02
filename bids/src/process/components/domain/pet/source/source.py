#/BDSP/bids_app/src/process/components/domain/pet/source/source.py
import os
import json
import shutil
import logging
from pathlib import Path
from utils import common
from . import validator
from . import separator

logger = logging.getLogger(__name__)

# ===== PET은 DICOM만 지원 =========================
_VALIDATOR_CLASS = {
    "DICOM": "DicomValidator",
}

_SEPARATOR_CLASS = {
    "DICOM": "DicomSeparator",
}

def _as_set_list(vr):
    """
    Validator.run() 반환값을 리스트로 정규화
    - 기존: (validated_dir, set_id)
    - 확장: [(validated_dir, set_id), ...]
    """
    if vr is None:
        return []
    if isinstance(vr, tuple):
        # (validated_dir, set_id)
        return [vr]
    if isinstance(vr, list):
        # [(validated_dir, set_id), ...] 보장
        return [(str(vd), str(sid)) for (vd, sid) in vr]
    raise TypeError(f"Unexpected validator result type: {type(vr)}")

def _get_pipeline_classes(file_format: str):
    """파일 포맷에 맞는 Validator / Separator 클래스를 반환"""
    v_name = _VALIDATOR_CLASS.get(file_format)
    s_name = _SEPARATOR_CLASS.get(file_format)

    if not v_name or not s_name:
        raise ValueError(f"PET 도메인은 DICOM만 지원합니다: {file_format}")

    Validator = getattr(validator, v_name, None)
    Separator = getattr(separator, s_name, None)

    if Validator is None or Separator is None:
        raise ImportError(f"필요 클래스 로드 실패: {v_name}, {s_name}")

    return Validator, Separator

def copy_files_to_invalid(origin_unzip_path, invalid_data_path):
    """origin_unzip_path의 모든 파일을 invalid_data_path로 복사"""
    try:
        origin_path = Path(origin_unzip_path)
        invalid_path = Path(invalid_data_path)

        if not origin_path.exists():
            logger.error(f"원본 경로가 존재하지 않음: {origin_path}")
            return

        for item in origin_path.iterdir():
            if item.is_file():
                shutil.copy2(item, invalid_path)
            elif item.is_dir():
                shutil.copytree(item, invalid_path / item.name, dirs_exist_ok=True)

        logger.info(f"파일 복사 완료: {origin_unzip_path} → {invalid_data_path}")
    except Exception as e:
        logger.error(f"파일 복사 실패: {e}")
        raise

def make_participants_file(subject_path):
    """subject_path에 participants.tsv와 participants.json 파일 생성"""
    try:
        subject_path = Path(subject_path)

        # participants.tsv: 기본 헤더만
        participants_tsv = subject_path / "participants.tsv"
        if not participants_tsv.exists():
            participants_tsv.write_text("participant_id\n", encoding="utf-8")

        # participants.json: 빈 JSON
        participants_json = subject_path / "participants.json"
        if not participants_json.exists():
            participants_json.write_text("{}", encoding="utf-8")

        logger.info(f"Participants 파일 생성 완료: {participants_tsv}, {participants_json}")
    except Exception as e:
        logger.error(f"Participants 파일 생성 실패: {e}")
        raise

def get_file_format(origin_unzip_path):
    """bdsp_file_list.json에서 index 1인 파일의 확장자를 읽어 파일 포맷 판단"""
    try:
        json_file_path = os.path.join(origin_unzip_path, "bdsp_file_list.json")
        if not os.path.exists(json_file_path):
            logger.error(f"bdsp_file_list.json 파일이 존재하지 않음: {json_file_path}")
            return "UNKNOWN"

        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # index가 1인 파일 찾기
        for item in data.get("path", []):
            if item.get("index") == 1:
                file_path = item.get("file_path", "")

                # 확장자 추출 및 분류
                file_ext = Path(file_path).suffix.lower()
                if file_ext in ['.dcm', '.dicom', '.ima']:
                    return "DICOM"
                else:
                    logger.warning(f"PET은 DICOM만 지원합니다. 현재 확장자: {file_ext}")
                    return "UNKNOWN"

        logger.error("index가 1인 파일을 찾을 수 없음")
        return "UNKNOWN"
    except Exception as e:
        logger.error(f"파일 포맷 판단 실패: {e}")
        return "UNKNOWN"

def create_source_path(structured_config, mss_path, origin_unzip_path):
    """PET Source 경로를 생성하고 반환"""
    logger.info("Step 3: PET Source 경로 생성 시작")

    try:
        # 1) entity 정리
        request = structured_config['request']
        public = '1' if request['public'] else '2'
        project_code = request['projectCode']
        project_seq = request['projectSeq']
        org_id = request['orgId']
        subject_id = request['subjectId']

        # 2) source 경로 및 alias/session/format
        source_path = Path(mss_path) / 'sourcedata'
        alias_id = f"{public}{project_code}{project_seq}{org_id}{subject_id}"
        session_num = common.zero_fill(request['trialIndex'])

        # PET은 DICOM만 지원
        file_format = get_file_format(origin_unzip_path)
        if file_format != "DICOM":
            raise ValueError(f"PET 도메인은 DICOM만 지원합니다. 현재 포맷: {file_format}")

        logger.info(f"Entity 정리 완료 - Alias ID: {alias_id}, Session: {session_num}, Format: {file_format}")
        print(f"PET Source 구조 생성: sub-{alias_id}/ses-{session_num}/{file_format}")

        # 3) 디렉토리 생성
        subject_path = source_path / f"sub-{alias_id}"
        session_path = subject_path / f"ses-{session_num}"
        format_path = session_path / file_format
        invalid_data_path = format_path / "invalid_data"
        valid_data_path = format_path / "valid_data"

        invalid_data_path.mkdir(parents=True, exist_ok=True)
        valid_data_path.mkdir(parents=True, exist_ok=True)

        # 4) participants 파일 생성
        make_participants_file(subject_path)

        # 5) 원본 압축해제 경로의 모든 파일을 invalid로 복사
        copy_files_to_invalid(origin_unzip_path, invalid_data_path)

        # 6) invalid 경로에 bdsp_file_list.json 생성 (스캔)
        common.bdsp_walk(str(invalid_data_path), str(invalid_data_path / "bdsp_file_list.json"))


        # 7) DICOM Validator/Separator 실행
        Validator, Separator = _get_pipeline_classes(file_format)

        # 7-1) 유효성 검사 (여러 세트 가능)
        validator_instance = Validator(invalid_data_path, valid_data_path)
        vr = validator_instance.run()
        if vr is None:
            error_msg = "유효성 검사 실패 또는 유효 파일 없음"
            logger.error(error_msg)
            raise Exception(error_msg)

        # 단일/다중 세트 모두 리스트로 정규화
        vr_list = _as_set_list(vr)
        if not vr_list:
            raise Exception("유효성 검사 결과가 비어 있습니다.")

        # 8) invalid/validated 쪽 JSON 생성
        common.bdsp_walk(str(invalid_data_path), str(invalid_data_path / "bdsp_file_list.json"))

        # 세트별로 분리 수행
        validated_sets = []
        separated_paths = []

        for (validated_dir, set_id) in vr_list:
            if not validated_dir or not Path(validated_dir).exists():
                error_msg = f"유효성 검사 디렉토리 없음: {validated_dir}"
                logger.error(error_msg)
                raise Exception(error_msg)

            # validated_dir 쪽 JSON 생성
            common.bdsp_walk(validated_dir, os.path.join(validated_dir, "bdsp_file_list.json"))

            # 9) 분리(Separation): 세트별 실행
            sep = Separator(validated_dir, set_id)
            sr = sep.run(validated_dir, set_id)
            separated_path = sr[0] if isinstance(sr, tuple) else sr

            if not separated_path or not Path(separated_path).exists():
                raise RuntimeError(f"분리 결과(separated_path) 미생성: set_id={set_id}")

            # JSON 업데이트: 분리 결과 경로 기준으로 스캔
            common.separated_walk(str(separated_path), str(Path(separated_path) / "bdsp_file_list.json"))
            logger.info(f"[{set_id}] bdsp_file_list.json 생성 (separated): {Path(separated_path) / 'bdsp_file_list.json'}")

            validated_sets.append({'validated_set_dir': str(validated_dir), 'set_id': str(set_id)})
            separated_paths.append(str(separated_path))

        logger.info(f"PET Source 디렉토리 구조 생성 및 유효성 검사/분리 완료: {invalid_data_path} / {valid_data_path}")

        # 10) 생성된 경로 반환
        source = {
            'source_path': str(source_path),
            'subject_path': str(subject_path),
            'session_path': str(session_path),
            'format_path': str(format_path),
            'invalid_data_path': str(invalid_data_path),
            'valid_data_path': str(valid_data_path),

            # 멀티 세트 대비
            'validated_sets': validated_sets,
            'separated_paths': separated_paths,
        }
        return source

    except Exception as e:
        logger.error(f"PET Source 경로 생성 실패: {e}")
        raise
