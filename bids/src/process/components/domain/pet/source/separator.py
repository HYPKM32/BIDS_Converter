# /BDSP/bids_app/src/process/components/domain/pet/source/separator.py
# PET은 DICOM만 지원하므로 MRI의 DicomSeparator를 그대로 재사용

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class PreWork:
    """모든 Separator 클래스의 공통 부모 클래스"""

    def __init__(self, validated_dir: str, set_id: str = None):
        self.validated_dir = Path(validated_dir)
        self.set_id = set_id

    def _load_json_index(self, json_path: Path):
        """bdsp_file_list.json에서 파일 목록(index 순서대로) 로드"""
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return sorted(data.get("path", []), key=lambda x: x.get("index", 0))
        except Exception as e:
            logger.error(f"JSON index 로드 실패: {json_path} ({e})")
            return []


class DicomSeparator(PreWork):
    def run(self, validated_dir: str = None, set_id: str = None) -> str:
        """
        validated_dir 안의 PET DICOM 파일들을 JSON index 기준으로 재명명(rename).

        Args:
            validated_dir: validation을 통과한 디렉토리 (옵션, 생성자에서 설정 가능)
            set_id: 세트 ID (옵션, 생성자에서 설정 가능)

        Returns:
            str: 분리 결과가 저장된 최종 디렉토리 경로
        """
        # 파라미터 우선순위: 메서드 인자 > 생성자 인자
        work_dir = Path(validated_dir) if validated_dir else self.validated_dir
        work_set_id = set_id if set_id is not None else self.set_id

        if not work_set_id:
            raise ValueError("set_id는 필수 파라미터입니다.")

        json_path = work_dir / "bdsp_file_list.json"

        if not json_path.exists():
            raise FileNotFoundError(f"bdsp_file_list.json 없음: {json_path}")

        file_list = self._load_json_index(json_path)
        if not file_list:
            raise RuntimeError("JSON index에서 파일을 불러오지 못했습니다.")

        # 파일 이동 및 이름 변경 (같은 디렉토리 내에서)
        for item in file_list:
            src_path = work_dir / Path(item.get("file_path")).name  # 파일명만 사용
            if not src_path.exists():
                logger.warning(f"원본 파일 없음: {src_path}")
                continue

            index = item.get("index")
            ext = src_path.suffix  # 원래 확장자 유지
            new_name = f"item_{work_set_id}_{index:04d}{ext}"  # 0-padding 추가
            dst_path = work_dir / new_name

            try:
                src_path.rename(dst_path)
                logger.info(f"[PET DICOM 분리] {src_path} → {dst_path}")
            except Exception as e:
                logger.error(f"파일 이동 실패: {src_path} → {dst_path} ({e})")

        logger.info(f"PET DICOM 분리 완료: {work_dir}")
        return str(work_dir)
