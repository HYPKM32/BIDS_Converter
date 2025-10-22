#/BDSP/bids_app/src/api/baseRoutes.py
from fastapi import APIRouter
from pathlib import Path
from globals import (
    EVENT_DIR, WORKING_DIR, UPLOAD_DIR, BACKUP_DIR, ERROR_DIR,
    MAX_WORKERS, LOG_FILENAME, MAGNETIC_STRENGTH_FIELD,
    DICOM_MODALITY, NIFTI_MODALITY, PARREC_MODALITY, SUFFIX_MAP,
    FLAG_DIR
)

router = APIRouter()

#################################################################
#                            BASE                               #
#################################################################
@router.get("/")
def root():
    return {"message": "BIDS is running"}

#################################################################
@router.get("/interfaces")
def interfaces():
    return {
        "EVENT_DIR": str(EVENT_DIR),
        "WORKING_DIR": str(WORKING_DIR),
        "UPLOAD_DIR": str(UPLOAD_DIR),
        "BACKUP_DIR": str(BACKUP_DIR),
        "ERROR_DIR": str(ERROR_DIR),
    }

#################################################################    
@router.get("/modality")
def modality():
    return {
        "DICOM_MODALITY": str(DICOM_MODALITY),
        "NIFTI_MODALITY": str(NIFTI_MODALITY),
        "PARREC_MODALITY": str(PARREC_MODALITY)
    }
    
#################################################################    
@router.get("/flag")
def flag():
    # FLAG_DIR을 Path 객체로 변환
    flag_path = Path(FLAG_DIR) if FLAG_DIR else Path("/default/flag/path")
    
    return {
        "defacing-defacer": str(flag_path / "defacing" / "defacer"),
        "defacing-medfacer": str(flag_path / "defacing" / "medfacer"),
        "canonical": str(flag_path / "canonical" / "canonical"),
        "T1w_preprocessing-civet": str(flag_path / "T1w_preprocessing" / "civet"),
        "T1w_preprocessing-freesurfer": str(flag_path / "T1w_preprocessing" / "freesurfer")
    }