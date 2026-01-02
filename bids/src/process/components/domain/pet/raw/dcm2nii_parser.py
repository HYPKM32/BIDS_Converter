import os
import shutil
import gzip
import json
import logging
import re
import subprocess
from pathlib import Path
from utils.common import bdsp_walk, compress_nii_gz

logger = logging.getLogger(__name__)

def clean_filename(filename: str) -> str:
    """
    파일명에서 %가 포함된 entity를 제거

    Args:
        filename (str): 원본 파일명

    Returns:
        str: 정리된 파일명
    """
    # BIDS entity 패턴: _키-값_ 형태 중 값에 %가 포함된 경우 제거
    pattern = r'_[a-zA-Z]+-[^_]*%[^_]*'
    cleaned_filename = re.sub(pattern, '', filename)
    # 연속된 언더스코어나 시작/끝의 언더스코어 정리
    cleaned_filename = re.sub(r'_{2,}', '_', cleaned_filename)
    cleaned_filename = cleaned_filename.strip('_')
    return cleaned_filename


# === NEW: helpers ============================================================

def _percent_to_glob_pattern(filename_without_ext: str) -> str:
    """
    dcm2niix의 %-포맷이 들어간 베이스 파일명(확장자 없음)을
    glob 패턴으로 변환(e.g., acq-%u -> acq-*)
    """
    # '%...' (다음 '_' 이전까지) -> '*'
    pattern_base = re.sub(r'%[^_]*', '*', filename_without_ext)
    return pattern_base  # 확장자는 호출부에서 붙임


def _resolve_actual_output(raw_dir: str, filename_without_ext: str) -> Path:
    """
    dcm2niix 실행 후, %-포맷이 포함된 파일명으로부터 실제 생성 파일(.nii.gz)을 찾아서 반환.
    여러 개면 mtime 최신 파일 선택.
    """
    raw_dir_p = Path(raw_dir)
    glob_base = _percent_to_glob_pattern(filename_without_ext)

    # 기본은 .nii.gz ( -z y )
    candidates = list(raw_dir_p.glob(glob_base + '.nii.gz'))

    # 압축이 꺼져 있거나 예외적 상황 대비
    if not candidates:
        candidates = list(raw_dir_p.glob(glob_base + '.nii'))

    if not candidates:
        raise FileNotFoundError(
            f"No output matched pattern: {raw_dir_p / (glob_base + '.nii.gz')}"
        )

    if len(candidates) > 1:
        candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        logger.warning(
            "Multiple outputs matched pattern; picking the most recent: %s",
            [str(c) for c in candidates]
        )

    return candidates[0]


# === UPDATED: NIfTI processing ==============================================

def process_nifti_files(src_path: str, raw_path: str, raw_file_option: str) -> str:
    """
    NIFTI 파일 처리

    Args:
        src_path (str): 소스 경로
        raw_path (str): 타겟 경로
        raw_file_option (str): 타겟 파일명(요구 포맷)

    Returns:
        str: 최종 결과 NIfTI(.nii.gz) 파일의 풀 경로
    """
    try:
        # 숨김/디렉토리/관리파일 제외
        files_in_src = [
            f for f in os.listdir(src_path)
            if f != 'bdsp_file_list.json'
            and not f.startswith('.')
            and os.path.isfile(os.path.join(src_path, f))
        ]

        # 대표 이미지 파일만 선택
        nii_cands = [f for f in files_in_src if f.endswith(('.nii', '.nii.gz'))]
        if len(nii_cands) != 1:
            logger.error("Expected 1 NIfTI image (.nii/.nii.gz), found %d in %s",
                         len(nii_cands), src_path)
            return None

        data_file = nii_cands[0]
        src_file_path = os.path.join(src_path, data_file)

        # 타깃 파일명은 % entity 제거(clean) 규칙 유지
        cleaned_filename = clean_filename(raw_file_option)
        target_file_path = os.path.join(raw_path, cleaned_filename)

        logger.info("Processing NIFTI file: %s", data_file)
        logger.info("Original filename: %s", raw_file_option)
        logger.info("Cleaned filename: %s", cleaned_filename)

        os.makedirs(raw_path, exist_ok=True)

        if data_file.endswith('.nii.gz'):
            shutil.copy2(src_file_path, target_file_path)
            logger.info("Copied .nii.gz: %s -> %s", src_file_path, target_file_path)
            final_path = target_file_path
        else:
            # .nii → .nii.gz 압축
            temp_nii_path = target_file_path
            if temp_nii_path.endswith('.nii.gz'):
                temp_nii_path = temp_nii_path[:-3]  # '.gz' 제거 -> '.nii'
            shutil.copy2(src_file_path, temp_nii_path)
            compressed_path = compress_nii_gz(temp_nii_path)
            logger.info("Copied+compressed .nii: %s -> %s", src_file_path, compressed_path)
            final_path = compressed_path

        # 사이드카 동반 복사(json/bval/bvec) - 있으면 동일 basename으로 맞춰줌
        base_src = re.sub(r'\.nii(\.gz)?$', '', data_file)
        base_tgt = re.sub(r'\.nii(\.gz)?$', '', os.path.basename(final_path))
        for side_ext in ('.json', '.bval', '.bvec'):
            sp = os.path.join(src_path, base_src + side_ext)
            if os.path.exists(sp):
                dp = os.path.join(raw_path, base_tgt + side_ext)
                shutil.copy2(sp, dp)
                logger.info("Copied sidecar: %s -> %s", sp, dp)

        return final_path

    except Exception as e:
        logger.error("Failed to process NIFTI files: %s", e)
        raise


# === UPDATED: dcm2niix runner ===============================================

def run_dcm2niix(src_path: str, raw_path: str, raw_file_option: str) -> str:
    """
    dcm2niix를 사용하여 DICOM/PARREC 파일을 NIFTI로 변환하고,
    %-포맷을 실제 생성 결과 파일 경로로 해석하여 반환한다.

    Args:
        src_path (str): 소스 경로
        raw_path (str): 타겟 경로
        raw_file_option (str): 타겟 파일명 형식 (확장자 포함 가능)

    Returns:
        str: 실제 생성된 NIfTI(.nii.gz or .nii) 파일의 "풀 경로"
    """
    try:
        # dcm2niix가 붙일 확장자를 제거한 베이스명 준비
        # (여기서는 clean_filename을 쓰지 않는다: %-포맷을 유지해야 dcm2niix가 해석)
        filename_base = raw_file_option
        filename_without_ext = re.sub(r'\.nii(\.gz)?$', '', filename_base)

        # dcm2niix 명령어 구성
        cmd = [
            'dcm2niix',
            '-f', filename_without_ext,
            '-z', 'y',            # gzip 압축
            '-o', raw_path,
            src_path
        ]

        logger.info("Running dcm2niix: %s", ' '.join(cmd))

        # 실행
        result = subprocess.run(
            cmd, capture_output=True, text=True, check=True
        )
        logger.info("dcm2niix completed successfully")
        if result.stdout:
            logger.debug("dcm2niix stdout: %s", result.stdout)
        if result.stderr:
            # dcm2niix는 stderr로도 유용 로그를 찍는 경우가 있음
            logger.warning("dcm2niix stderr: %s", result.stderr)

        # 실제 생성된 결과 파일(.nii.gz) 경로 해석
        actual_path = _resolve_actual_output(raw_path, filename_without_ext)
        logger.info("Resolved actual output: %s", actual_path)
        return str(actual_path)

    except subprocess.CalledProcessError as e:
        logger.error("dcm2niix failed with return code %s", e.returncode)
        logger.error("dcm2niix stdout: %s", e.stdout)
        logger.error("dcm2niix stderr: %s", e.stderr)
        raise ValueError(f"dcm2niix conversion failed: {e.stderr}") from e

    except Exception as e:
        logger.error("Failed to run dcm2niix: %s", e)
        raise ValueError(f"dcm2niix execution failed: {e}") from e


# === UPDATED: main conversion orchestrator ==================================

def process_bids_conversion(bids_mapping: dict) -> dict:
    """
    BIDS 매핑을 처리하여 변환 준비

    Args:
        bids_mapping (dict): {src_path: raw_full_path} 매핑 딕셔너리
                             raw_full_path는 '원하는' 경로(파일명 옵션 포함)

    Returns:
        dict: {src_path: 실제 생성/복사된 NIfTI 파일의 풀 경로}
    """
    logger.info("Processing %d BIDS mappings", len(bids_mapping))
    src2raw_mapping = {}

    for src_path, raw_full_path in bids_mapping.items():
        try:
            # 1) 타겟 디렉토리
            raw_path = os.path.dirname(raw_full_path)

            # 2) file_format: src_path에서 {format}/valid_data/set-* 패턴의 format 부분 추출
            path_parts = src_path.split('/')
            format_index = -1
            for i, part in enumerate(path_parts):
                if i < len(path_parts) - 2:
                    if (path_parts[i + 1] == 'valid_data' and
                        path_parts[i + 2].startswith('set-')):
                        format_index = i
                        break

            file_format = path_parts[format_index] if format_index != -1 else "UNKNOWN"

            # 3) 파일 옵션(원하는 파일명)
            raw_file_option = os.path.basename(raw_full_path)

            logger.info(
                "Processing - Format: %s, Source: %s, TargetDir: %s, FilenameOpt: %s",
                file_format, src_path, raw_path, raw_file_option
            )

            os.makedirs(raw_path, exist_ok=True)

            # 4) 포맷별 처리
            if file_format.upper() == 'NIFTI':
                actual_path = process_nifti_files(src_path, raw_path, raw_file_option)
            else:
                # DICOM, PARREC 등 -> dcm2niix 변환
                logger.info("Converting %s using dcm2niix", file_format)
                actual_path = run_dcm2niix(src_path, raw_path, raw_file_option)

            # 5) bdsp_file_list.json 생성/갱신
            logger.info("Generating bdsp_file_list.json for %s", raw_path)
            bdsp_walk(raw_path)
            logger.info("Successfully generated bdsp_file_list.json in %s", raw_path)

            # 6) src2raw_mapping에 '실제 결과 경로'로 기록
            if actual_path:
                src2raw_mapping[src_path] = actual_path
                logger.info("Mapped %s -> %s", src_path, actual_path)
            else:
                logger.warning("No actual output path resolved for %s", src_path)

        except Exception as e:
            logger.error("Failed to process mapping for %s: %s", src_path, e)
            continue

    logger.info("Successfully processed %d mappings", len(src2raw_mapping))
    return src2raw_mapping
