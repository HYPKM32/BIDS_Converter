#/BDSP/bids_app/src/api/modalityRoutes.py
from fastapi import APIRouter, HTTPException
from pathlib import Path
import json
from globals import (
    EVENT_DIR, WORKING_DIR, UPLOAD_DIR, BACKUP_DIR, ERROR_DIR,
    MAX_WORKERS, LOG_FILENAME, MAGNETIC_STRENGTH_FIELD,
    DICOM_MODALITY, NIFTI_MODALITY, PARREC_MODALITY, SUFFIX_MAP,
    FLAG_DIR
)

router = APIRouter()

#################################################################
#                   1. SUFFIX_MAP GET                           #
#################################################################
@router.get("/suffixmap")
def get_suffix_map():
    """
    SUFFIX_MAP JSON 파일을 읽어서 반환
    """
    try:
        suffix_map_path = Path(SUFFIX_MAP)
        
        if not suffix_map_path.exists():
            raise HTTPException(status_code=404, detail=f"SUFFIX_MAP file not found: {SUFFIX_MAP}")
        
        with open(suffix_map_path, 'r', encoding='utf-8') as f:
            suffix_map_data = json.load(f)
        
        return {
            "status": "success",
            "data": suffix_map_data,
            "filepath": str(suffix_map_path)
        }
    
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"Invalid JSON format: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read SUFFIX_MAP: {str(e)}")


#################################################################
#                   2. MODALITY MAPPING 저장                    #
#################################################################
@router.post("/mapping/{file_format}/{system_id}/{project_code}/{project_seq}/{org_id}")
async def save_modality_mapping(
    file_format: str,
    system_id: str,
    project_code: str,
    project_seq: str,
    org_id: str,
    modality_data: dict
):
    """
    Modality mapping JSON 저장 (있으면 merge, 없으면 생성)
    """
    try:
        # fileFormat 소문자 변환 및 검증
        file_format_lower = file_format.lower()
        if file_format_lower not in ['dicom', 'parrec']:
            raise HTTPException(
                status_code=400, 
                detail="file_format must be 'dicom' or 'parrec'"
            )
        
        # 폴더 경로 결정
        if file_format_lower == 'dicom':
            base_path = Path(DICOM_MODALITY)
        else:  # parrec
            base_path = Path(PARREC_MODALITY)
        
        # 폴더 생성
        base_path.mkdir(parents=True, exist_ok=True)
        
        # 파일명 생성
        filename = f"{system_id}_{project_code}_{project_seq}_{org_id}_{file_format_lower}_modality.json"
        filepath = base_path / filename
        
        # 기존 파일 확인
        file_existed = filepath.exists()
        
        if file_existed:
            # 기존 파일 읽기
            with open(filepath, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
            
            # Merge 로직
            merged_data = merge_modality_data(existing_data, modality_data)
        else:
            # 새 파일
            merged_data = modality_data
        
        # 파일 저장
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(merged_data, f, indent=2, ensure_ascii=False)
        
        return {
            "status": "success",
            "message": "Modality mapping saved successfully",
            "filepath": str(filepath),
            "filename": filename,
            "merged": file_existed,
            "data": merged_data
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to save modality mapping: {str(e)}"
        )


def merge_modality_data(existing: dict, new: dict) -> dict:
    """
    두 modality 데이터를 merge (중복 제거)
    
    예시:
    existing = {"T1w": [{"SeriesDescription": ["SPGR", "MPRAGE"]}]}
    new = {"T1w": [{"SeriesDescription": ["SPGR", "3D_SAG_T1"]}]}
    결과 = {"T1w": [{"SeriesDescription": ["SPGR", "MPRAGE", "3D_SAG_T1"]}]}
    """
    merged = {}
    
    # 모든 modality key 수집 (T1w, T2w, FLAIR 등)
    all_keys = set(existing.keys()) | set(new.keys())
    
    for modality_key in all_keys:
        existing_conditions = existing.get(modality_key, [])
        new_conditions = new.get(modality_key, [])
        
        # 기존 조건을 복사
        merged_conditions = [cond.copy() for cond in existing_conditions]
        
        # 새로운 조건들을 처리
        for new_cond in new_conditions:
            # new_cond의 키 (예: "SeriesDescription", "ProtocolName", "Modality")
            new_cond_key = list(new_cond.keys())[0]
            
            # 같은 키를 가진 기존 조건 찾기
            found = False
            for merged_cond in merged_conditions:
                if new_cond_key in merged_cond:
                    # 같은 키 발견, 리스트 합치기
                    combined = merged_cond[new_cond_key] + new_cond[new_cond_key]
                    # 중복 제거 (순서 유지)
                    seen = set()
                    unique = []
                    for item in combined:
                        if item not in seen:
                            seen.add(item)
                            unique.append(item)
                    merged_cond[new_cond_key] = unique
                    found = True
                    break
            
            # 같은 키를 가진 조건이 없으면 새로 추가
            if not found:
                merged_conditions.append(new_cond.copy())
        
        merged[modality_key] = merged_conditions
    
    return merged
