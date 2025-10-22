#/BDSP/bids_app/src/api/interfacesRoutes.py
from fastapi import APIRouter, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from pathlib import Path
from datetime import datetime
from typing import Optional
import json
import shutil
from globals import (
    EVENT_DIR, WORKING_DIR, UPLOAD_DIR, BACKUP_DIR, ERROR_DIR,
    MAX_WORKERS, LOG_FILENAME, MAGNETIC_STRENGTH_FIELD,
    DICOM_MODALITY, NIFTI_MODALITY, PARREC_MODALITY, SUFFIX_MAP,
    FLAG_DIR
)

router = APIRouter()

#################################################################
#                   1. EVENT JSON 저장                          #
#################################################################
@router.post("/event")
async def save_event(event_data: dict):
    """
    event 폴더에 JSON 파일 저장
    """
    try:
        # EVENT_DIR 확인 및 생성
        event_path = Path(EVENT_DIR)
        event_path.mkdir(parents=True, exist_ok=True)
        
        # 타임스탬프로 파일명 생성
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"event_{timestamp}.json"
        filepath = event_path / filename
        
        # JSON 파일 저장
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(event_data, f, indent=2, ensure_ascii=False)
        
        return {
            "status": "success",
            "message": "Event saved successfully",
            "filepath": str(filepath),
            "filename": filename
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save event: {str(e)}")


#################################################################
#                   2. ZIP 파일 업로드                          #
#################################################################
@router.post("/upload/{user}/{subject_id}/{upload_time}")
async def upload_data(
    user: str,
    subject_id: str,
    upload_time: str,
    file: UploadFile = File(...)
):
    """
    upload_dir/{user}/{subjectId}/{uploadTime} 경로에 ZIP 파일 업로드
    """
    try:
        # ZIP 파일 확인
        if not file.filename.endswith('.zip'):
            raise HTTPException(status_code=400, detail="Only ZIP files are allowed")
        
        # 저장 경로 생성
        upload_path = Path(UPLOAD_DIR) / user / subject_id / upload_time
        upload_path.mkdir(parents=True, exist_ok=True)
        
        # 파일 저장
        file_path = upload_path / file.filename
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        return {
            "status": "success",
            "message": "File uploaded successfully",
            "user": user,
            "subject_id": subject_id,
            "upload_time": upload_time,
            "filename": file.filename,
            "filepath": str(file_path),
            "file_size": file_path.stat().st_size
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload file: {str(e)}")


