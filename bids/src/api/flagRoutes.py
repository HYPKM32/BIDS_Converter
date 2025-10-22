#/BDSP/bids_app/src/api/flagRoutes.py
from fastapi import APIRouter
from pathlib import Path
from globals import (
    EVENT_DIR, WORKING_DIR, UPLOAD_DIR, BACKUP_DIR, ERROR_DIR,
    MAX_WORKERS, LOG_FILENAME, MAGNETIC_STRENGTH_FIELD,
    DICOM_MODALITY, NIFTI_MODALITY, PARREC_MODALITY, SUFFIX_MAP,
    FLAG_DIR
)

router = APIRouter()