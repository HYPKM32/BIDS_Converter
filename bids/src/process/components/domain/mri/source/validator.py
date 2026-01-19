import json
import hashlib
import logging
from pathlib import Path
import pydicom
from pydicom.errors import InvalidDicomError
import shutil
import os
import nibabel as nib
import numpy as np
from typing import List, Tuple

logger = logging.getLogger(__name__)


def _sha1(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:16]


def validate_parrec_files(par_path):
    """
    PAR/REC 파일 최소 유효성 검사
    
    Args:
        par_path (str): PAR 파일 경로
    
    Returns:
        bool: 유효성 여부 (True/False)
    """
    # REC 파일 경로 생성
    rec_path = par_path.replace('.par', '.rec')
    
    try:
        # 1. 파일 존재 확인
        if not os.path.exists(par_path):
            return False
            
        if not os.path.exists(rec_path):
            return False
        
        # 2. REC 파일 크기 확인 (비어있지 않은지만)
        if os.path.getsize(rec_path) == 0:
            return False
        
        # 3. PAR 파일 기본 파싱 가능 확인
        has_image_section = False
        image_count = 0
        
        with open(par_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.strip()
                
                # IMAGE INFORMATION 섹션 시작 확인
                if line.startswith("#  sl ec  dyn"):
                    has_image_section = True
                    continue
                
                # 데이터 라인 카운트 (최소 1개 이상)
                if has_image_section and line and not line.startswith("#"):
                    parts = line.split()
                    if len(parts) >= 10:  # 최소 필수 컬럼 수
                        image_count += 1
        
        # 4. 최소 요구사항 확인
        if not has_image_section:
            return False
        
        if image_count == 0:
            return False
        
        # 모든 필수 검증 통과
        return True
        
    except Exception:
        return False


def validate_nifti_file(nifti_path):
    """
    NIfTI 파일 유효성 검사 함수
    
    Args:
        nifti_path (str): NIfTI 파일 경로
    
    Returns:
        dict: 검사 결과
    """
    results = {
        'valid': True,
        'errors': [],
        'warnings': [],
        'success': [],
        'info': {}
    }
    
    try:
        # 1. 파일 존재 확인
        if not os.path.exists(nifti_path):
            results['errors'].append(f"NIfTI 파일이 존재하지 않음: {nifti_path}")
            results['valid'] = False
            return results
        else:
            results['success'].append("✓ NIfTI 파일 존재 확인")
        
        # 2. 파일 로드 시도
        img = nib.load(nifti_path)
        results['success'].append("✓ NIfTI 파일 로드 성공")
        
        # 3. 기본 정보 추출
        shape = img.shape
        data_dtype = img.get_data_dtype()
        
        results['info']['shape'] = shape
        results['info']['data_type'] = str(data_dtype)
        results['info']['dimensions'] = len(shape)
        
        # 4. 헤더 정보 검사
        header = img.header
        results['info']['header_valid'] = True
        
        # 복셀 크기 정보
        try:
            pixdim = header.get_zooms()
            results['info']['voxel_size'] = pixdim[:3]
            results['success'].append("✓ 복셀 크기 정보 추출 성공")
        except Exception as e:
            results['warnings'].append(f"복셀 크기 정보 추출 실패: {e}")
        
        # 공간 정보 (affine matrix)
        try:
            affine = img.affine
            det = np.linalg.det(affine[:3, :3])
            results['info']['affine_determinant'] = det
            
            if abs(det) < 1e-10:
                results['warnings'].append("변환 행렬의 determinant가 0에 가까움")
            else:
                results['success'].append("✓ 공간 변환 행렬 정상")
        except Exception as e:
            results['warnings'].append(f"공간 정보 검사 실패: {e}")
        
        # 5. 데이터 유효성 검사
        try:
            data = img.get_fdata()
            
            # NaN 값 확인
            nan_count = np.isnan(data).sum()
            if nan_count > 0:
                results['warnings'].append(f"NaN 값 {nan_count}개 발견")
            else:
                results['success'].append("✓ NaN 값 없음")
            
            # 무한값 확인
            inf_count = np.isinf(data).sum()
            if inf_count > 0:
                results['warnings'].append(f"무한값 {inf_count}개 발견")
            else:
                results['success'].append("✓ 무한값 없음")
            
            # 데이터 통계
            results['info']['data_range'] = [float(np.min(data)), float(np.max(data))]
            results['info']['non_zero_voxels'] = int(np.count_nonzero(data))
            results['info']['total_voxels'] = int(data.size)
            
            results['success'].append("✓ 데이터 접근 및 기본 통계 계산 성공")
            
        except Exception as e:
            results['errors'].append(f"데이터 접근 실패: {e}")
            results['valid'] = False
        
        # 6. 차원 유효성 검사
        if len(shape) < 3:
            results['errors'].append(f"잘못된 차원: {len(shape)}D (최소 3D 필요)")
            results['valid'] = False
        elif len(shape) > 4:
            results['warnings'].append(f"비정상적인 고차원: {len(shape)}D")
        else:
            results['success'].append(f"✓ 적절한 차원: {len(shape)}D")
        
        # 7. 파일 크기 일관성 검사
        try:
            expected_size = np.prod(shape) * np.dtype(data_dtype).itemsize
            actual_size = os.path.getsize(nifti_path)
            
            # .nii.gz 파일은 압축되어 있으므로 크기가 다를 수 있음
            if nifti_path.endswith('.gz'):
                results['info']['compressed'] = True
                results['success'].append("✓ 압축 파일 확인")
            else:
                results['info']['compressed'] = False
                # 비압축 파일의 경우 대략적인 크기 검사
                if actual_size < expected_size * 0.5:  # 너무 작으면 문제
                    results['warnings'].append("파일 크기가 예상보다 현저히 작음")
        except Exception as e:
            results['warnings'].append(f"파일 크기 검사 실패: {e}")
        
        return results
        
    except Exception as e:
        results['errors'].append(f"NIfTI 파일 검사 중 오류 발생: {str(e)}")
        results['valid'] = False
        return results

class DicomValidator:
    def __init__(self, invalid_data_path: str | Path, valid_data_path: str | Path):
        self.invalid_data_path = Path(invalid_data_path)
        self.valid_data_path = Path(valid_data_path)

    def run(self) -> List[Tuple[str, str]] | None:
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
            # 파일명에 glob 특수문자([, ], *, ? 등)가 있을 수 있으므로
            # rglob("*")으로 모든 파일을 찾은 후 이름으로 필터링
            cur = None
            for file in self.invalid_data_path.rglob("*"):
                if file.is_file() and file.name == src_filename:
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
            logger.error("No valid DICOM files found")
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

            logger.info(f"[DICOM] Validation group → {target_dir} (files: {len(files)})")
            results.append((str(target_dir), set_id))

        return results


class ParrecValidator:
    def __init__(self, invalid_data_path: str | Path, valid_data_path: str | Path):
        self.invalid_data_path = Path(invalid_data_path)
        self.valid_data_path = Path(valid_data_path)

    def _fix_par_header(self, par_file: Path) -> None:
        """PAR 파일 헤더의 CLINICAL TRYOUT 라인 수정"""
        correct_line = "# CLINICAL TRYOUT             Research image export tool     V4.2"

        try:
            with open(par_file, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()

            modified = False
            for i, line in enumerate(lines):
                if "# CLINICAL TRYOUT" in line and line.strip() != correct_line:
                    lines[i] = correct_line + "\n"
                    modified = True
                    break  # 보통 첫 번째만 있으므로

            if modified:
                with open(par_file, 'w', encoding='utf-8') as f:
                    f.writelines(lines)
                logger.info(f"Fixed CLINICAL TRYOUT header in {par_file.name}")
        except Exception as e:
            logger.warning(f"Failed to fix PAR header {par_file.name}: {e}")

    def run(self) -> List[Tuple[str, str]] | None:
        jpath = self.invalid_data_path / "bdsp_file_list.json"
        if not jpath.exists():
            logger.error(f"{jpath} not found")
            return None
        try:
            data = json.loads(jpath.read_text(encoding="utf-8"))
        except Exception as e:
            logger.error(f"Failed to read {jpath}: {e}")
            return None

        # stem -> {'par': Path|None, 'rec': Path|None}
        pairs: dict[str, dict[str, Path | None]] = {}

        for item in data.get("path", []):
            file_path = item.get("file_path", "")
            if not file_path:
                continue

            # file_path는 원본 파일의 절대 경로, 파일명만 추출
            src_filename = Path(file_path).name

            # invalid_data에서 재귀적으로 파일 찾기
            # 파일명에 glob 특수문자([, ], *, ? 등)가 있을 수 있으므로
            # rglob("*")으로 모든 파일을 찾은 후 이름으로 필터링
            cur = None
            for file in self.invalid_data_path.rglob("*"):
                if file.is_file() and file.name == src_filename:
                    cur = file
                    break

            if not cur:
                # 파일이 복사되지 않았으면 건너뛰기
                logger.debug(f"File not found in invalid_data (skipped): {src_filename}")
                continue

            suf = cur.suffix.lower()
            if suf == '.par' or suf == '.rec':
                info = pairs.setdefault(cur.stem, {'par': None, 'rec': None})
                if suf == '.par':
                    info['par'] = cur
                else:
                    info['rec'] = cur

        results: List[Tuple[str, str]] = []

        for stem, pr in pairs.items():
            par_file, rec_file = pr['par'], pr['rec']
            if not par_file or not rec_file:
                logger.error(f"Missing PAR/REC pair for stem '{stem}'")
                continue

            # 최소 유효성 검사
            if not validate_parrec_files(str(par_file)):
                logger.error(f"Invalid PAR/REC: {par_file.name} / {rec_file.name}")
                continue

            # PAR 헤더 수정
            self._fix_par_header(par_file)

            set_id = "set-" + _sha1(f"{par_file.name}|{rec_file.name}")
            target_dir = self.valid_data_path / set_id
            target_dir.mkdir(parents=True, exist_ok=True)

            for src in (par_file, rec_file):
                dst = target_dir / src.name
                try:
                    src.rename(dst)
                except OSError:
                    shutil.move(str(src), str(dst))

            logger.info(f"[PAR/REC] Valid pair → {target_dir}")
            results.append((str(target_dir), set_id))

        if not results:
            logger.error("No valid PAR/REC pairs found")
            return None
        return results
    


class NiftiValidator:
    def __init__(self, invalid_data_path: str | Path, valid_data_path: str | Path):
        self.invalid_data_path = Path(invalid_data_path)
        self.valid_data_path = Path(valid_data_path)

    def run(self) -> List[Tuple[str, str]] | None:
        jpath = self.invalid_data_path / "bdsp_file_list.json"
        if not jpath.exists():
            logger.error(f"{jpath} not found")
            return None
        try:
            data = json.loads(jpath.read_text(encoding="utf-8"))
        except Exception as e:
            logger.error(f"Failed to read {jpath}: {e}")
            return None

        # stem -> [Path...(.nii / .nii.gz)]
        groups: dict[str, list[Path]] = {}

        for item in data.get("path", []):
            file_path = item.get("file_path", "")
            if not file_path:
                continue

            # file_path는 원본 파일의 절대 경로, 파일명만 추출
            src_filename = Path(file_path).name

            # invalid_data에서 재귀적으로 파일 찾기
            # 파일명에 glob 특수문자([, ], *, ? 등)가 있을 수 있으므로
            # rglob("*")으로 모든 파일을 찾은 후 이름으로 필터링
            cur = None
            for file in self.invalid_data_path.rglob("*"):
                if file.is_file() and file.name == src_filename:
                    cur = file
                    break

            if not cur:
                # 파일이 복사되지 않았으면 건너뛰기
                logger.debug(f"File not found in invalid_data (skipped): {src_filename}")
                continue
            name_low = cur.name.lower()
            if cur.suffix.lower() == '.nii' or name_low.endswith('.nii.gz'):
                groups.setdefault(cur.stem, []).append(cur)

        if not groups:
            logger.error("No NIfTI files found")
            return None

        results: List[Tuple[str, str]] = []

        for stem, files in groups.items():
            # 파일들 전부 유효성 검사 (하나라도 invalid면 해당 그룹 skip)
            all_valid = True
            for nf in files:
                vr = validate_nifti_file(str(nf))
                if not vr.get('valid'):
                    logger.error(f"✗ NIfTI validation failed: {nf.name}")
                    all_valid = False
                    break
            if not all_valid:
                continue

            # set_id: stem 기반 (간단하고 안정적)
            fnames = "|".join(sorted(f.name for f in files))
            set_id = "set-" + _sha1(f"{stem}|{fnames}")

            target_dir = self.valid_data_path / set_id
            target_dir.mkdir(parents=True, exist_ok=True)

            for src in files:
                dst = target_dir / src.name
                try:
                    src.rename(dst)
                except OSError:
                    shutil.move(str(src), str(dst))

            logger.info(f"[NIfTI] Validation group → {target_dir} (files: {len(files)})")
            results.append((str(target_dir), set_id))

        if not results:
            logger.error("No valid NIfTI sets produced")
            return None
        return results