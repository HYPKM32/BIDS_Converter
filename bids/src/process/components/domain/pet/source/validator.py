# /BDSP/bids_app/src/process/components/domain/pet/source/validator.py
# PET은 DICOM만 지원하므로 MRI의 DicomValidator를 그대로 재사용

import json
import hashlib
import logging
from pathlib import Path
import pydicom
from pydicom.errors import InvalidDicomError
import shutil
from typing import List, Tuple

logger = logging.getLogger(__name__)


def _sha1(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:16]


class DicomValidator:
    def __init__(self, invalid_data_path: str | Path, valid_data_path: str | Path):
        self.invalid_data_path = Path(invalid_data_path)
        self.valid_data_path = Path(valid_data_path)

    def run(self) -> List[Tuple[str, str]] | None:
        """
        PET DICOM 파일들을 Study/Series UID로 그룹핑하여 검증

        Returns:
            List[Tuple[str, str]]: [(validated_dir, set_id), ...]
        """
        jpath = self.invalid_data_path / "bdsp_file_list.json"
        if not jpath.exists():
            logger.error(f"{jpath} not found")
            return None
        try:
            data = json.loads(jpath.read_text(encoding="utf-8"))
        except Exception as e:
            logger.error(f"Failed to read {jpath}: {e}")
            return None

        # (StudyUID, SeriesUID) -> [Path...]
        groups: dict[tuple[str, str], list[Path]] = {}

        for item in data.get("path", []):
            file_path = item.get("file_path", "")
            if not file_path:
                continue

            # file_path는 원본 파일의 절대 경로, 파일명만 추출
            src_filename = Path(file_path).name

            # invalid_data에서 재귀적으로 파일 찾기
            cur = None
            for file in self.invalid_data_path.rglob(src_filename):
                if file.is_file():
                    cur = file
                    break

            if not cur:
                # 파일이 복사되지 않았으면 건너뛰기
                logger.debug(f"File not found in invalid_data (skipped): {src_filename}")
                continue
            try:
                ds = pydicom.dcmread(str(cur), stop_before_pixels=True, force=True)
            except (InvalidDicomError, Exception):
                logger.info(f"Skipping non-DICOM file: {cur.name}")
                continue

            study_uid = getattr(ds, "StudyInstanceUID", None)
            series_uid = getattr(ds, "SeriesInstanceUID", None)
            if not study_uid or not series_uid:
                logger.warning(f"Missing StudyUID or SeriesUID in {cur}")
                continue

            groups.setdefault((study_uid, series_uid), []).append(cur)

        if not groups:
            logger.error("No valid PET DICOM files found")
            return None

        results: List[Tuple[str, str]] = []
        for (study_uid, series_uid), files in groups.items():
            set_id = "set-" + _sha1(f"{study_uid}|{series_uid}")
            target_dir = self.valid_data_path / set_id
            target_dir.mkdir(parents=True, exist_ok=True)

            for src in files:
                dst = target_dir / src.name
                try:
                    src.rename(dst)
                except OSError:
                    shutil.move(str(src), str(dst))

            logger.info(f"[PET DICOM] Validation group → {target_dir} (files: {len(files)})")
            results.append((str(target_dir), set_id))

        return results
