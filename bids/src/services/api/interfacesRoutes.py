#/BDSP/bids_app/src/api/interfacesRoutes.py
from fastapi import APIRouter, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, StreamingResponse
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict
import json
import shutil
import zipfile
import tempfile
import os
import io
import uuid
import asyncio
from concurrent.futures import ThreadPoolExecutor
from globals import (
    EVENT_DIR, WORKING_DIR, UPLOAD_DIR, BACKUP_DIR, ERROR_DIR,
    MAX_WORKERS, LOG_FILENAME, MAGNETIC_STRENGTH_FIELD,
    DICOM_MODALITY, NIFTI_MODALITY, PARREC_MODALITY, SUFFIX_MAP,
    FLAG_DIR
)

router = APIRouter()

# 태스크 상태 저장소
task_store: Dict[str, dict] = {}

# ThreadPoolExecutor for CPU-bound tasks
executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)

# 청크 크기 (10MB) - 대용량 파일 업로드용
CHUNK_SIZE = 10 * 1024 * 1024

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


#################################################################
#                   3. 단일 요청 (Event + Upload 통합)            #
#################################################################
@router.post("/request/single")
async def request_single(
    event: str = File(...),
    data: UploadFile = File(...)
):
    """
    Event JSON 저장 + ZIP 파일 업로드를 한 번에 처리
    event_data에서 user, subjectId, uploadTime을 추출하여 업로드 경로 결정
    """
    try:
        # 1. event JSON 파싱
        try:
            event_dict = json.loads(event)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON format in event_data")

        # 2. 필수 키 추출
        user = event_dict.get("user")
        subject_id = event_dict.get("subjectId")
        upload_time = event_dict.get("uploadTime")

        # uploadTime이 빈 문자열일 경우 현재 시간으로 채움 (YYMMDDHHmmssSSS 형식)
        if not upload_time:
            upload_time = datetime.now().strftime("%y%m%d%H%M%S") + datetime.now().strftime("%f")[:3]
            event_dict["uploadTime"] = upload_time

        if not all([user, subject_id]):
            raise HTTPException(
                status_code=400,
                detail="Missing required keys: user, subjectId"
            )

        # 3. ZIP 파일 확인
        if not data.filename.endswith('.zip'):
            raise HTTPException(status_code=400, detail="Only ZIP files are allowed")

        # 4. ZIP 파일 업로드 (먼저 저장)
        upload_path = Path(UPLOAD_DIR) / user / subject_id / upload_time
        upload_path.mkdir(parents=True, exist_ok=True)

        zip_file_path = upload_path / data.filename
        with open(zip_file_path, "wb") as buffer:
            shutil.copyfileobj(data.file, buffer)

        # 5. Event JSON 저장
        event_path = Path(EVENT_DIR)
        event_path.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        event_filename = f"event_{timestamp}.json"
        event_filepath = event_path / event_filename

        with open(event_filepath, 'w', encoding='utf-8') as f:
            json.dump(event_dict, f, indent=2, ensure_ascii=False)

        return {
            "status": "success",
            "message": "Event saved and file uploaded successfully",
            "event": {
                "filepath": str(event_filepath),
                "filename": event_filename
            },
            "upload": {
                "user": user,
                "subject_id": subject_id,
                "upload_time": upload_time,
                "filename": data.filename,
                "filepath": str(zip_file_path),
                "file_size": zip_file_path.stat().st_size
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process request: {str(e)}")


#################################################################
#                   4. 다중 요청 (여러 Subject 처리)               #
#################################################################
def validate_subject_folder(subject_path: Path) -> dict:
    """
    Subject 폴더 내 파일 유효성 검사
    - DICOM: *.dcm 파일 존재
    - PAR/REC: .par와 .rec 파일이 페어로 존재
    - NIfTI: *.nii, *.nii.gz, *.nifti 파일 존재

    Returns: {"valid": bool, "modalities": list, "error": str or None}
    """
    modalities = []

    # DICOM 검사 (*.dcm)
    dcm_files = list(subject_path.glob("*.dcm")) + list(subject_path.glob("**/*.dcm"))
    if dcm_files:
        modalities.append("DICOM")

    # PAR/REC 검사 (.par + .rec 페어)
    par_files = list(subject_path.glob("*.par")) + list(subject_path.glob("*.PAR"))
    rec_files = list(subject_path.glob("*.rec")) + list(subject_path.glob("*.REC"))
    par_files += list(subject_path.glob("**/*.par")) + list(subject_path.glob("**/*.PAR"))
    rec_files += list(subject_path.glob("**/*.rec")) + list(subject_path.glob("**/*.REC"))

    if par_files and rec_files:
        # 페어 검증: 같은 이름의 .par와 .rec가 존재해야 함
        par_stems = {f.stem.lower() for f in par_files}
        rec_stems = {f.stem.lower() for f in rec_files}
        if par_stems & rec_stems:  # 교집합이 존재하면 유효
            modalities.append("PARREC")

    # NIfTI 검사 (*.nii, *.nii.gz, *.nifti)
    nii_files = (
        list(subject_path.glob("*.nii")) +
        list(subject_path.glob("*.nii.gz")) +
        list(subject_path.glob("*.nifti")) +
        list(subject_path.glob("**/*.nii")) +
        list(subject_path.glob("**/*.nii.gz")) +
        list(subject_path.glob("**/*.nifti"))
    )
    if nii_files:
        modalities.append("NIfTI")

    if not modalities:
        return {
            "valid": False,
            "modalities": [],
            "error": "No valid imaging files found (DICOM, PAR/REC, or NIfTI)"
        }

    return {
        "valid": True,
        "modalities": modalities,
        "error": None
    }


def create_subject_zip(subject_path: Path, output_path: Path) -> Path:
    """
    Subject 폴더를 ZIP으로 압축
    """
    zip_filename = f"{subject_path.name}.zip"
    zip_filepath = output_path / zip_filename

    with zipfile.ZipFile(zip_filepath, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file in subject_path.rglob("*"):
            if file.is_file():
                arcname = file.relative_to(subject_path)
                zipf.write(file, arcname)

    return zip_filepath


def _process_multiple_subjects(task_id: str, event_dict: dict, temp_zip_path: str, temp_dir: str):
    """
    백그라운드에서 여러 Subject 처리 (동기 함수)
    """
    try:
        task_store[task_id]["status"] = "processing"

        user = event_dict.get("user")
        upload_time = event_dict.get("uploadTime")

        # ZIP 압축 해제
        extract_dir = Path(temp_dir) / "extracted"
        extract_dir.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(temp_zip_path, 'r') as zipf:
            zipf.extractall(extract_dir)

        # DCM 파일이 있는 폴더들을 subject로 인식
        subject_folders = set()
        for dcm_file in extract_dir.rglob("*.dcm"):
            # DCM 파일의 부모 폴더를 subject로
            subject_folders.add(dcm_file.parent)

        # PAR/REC 파일도 확인
        for par_file in extract_dir.rglob("*.par"):
            subject_folders.add(par_file.parent)
        for par_file in extract_dir.rglob("*.PAR"):
            subject_folders.add(par_file.parent)

        # NIfTI 파일도 확인
        for nii_file in extract_dir.rglob("*.nii"):
            subject_folders.add(nii_file.parent)
        for nii_file in extract_dir.rglob("*.nii.gz"):
            subject_folders.add(nii_file.parent)

        subject_folders = list(subject_folders)

        if not subject_folders:
            task_store[task_id]["status"] = "failed"
            task_store[task_id]["error"] = "No imaging files (DCM, PAR/REC, NIfTI) found in ZIP file"
            return

        total_subjects = len(subject_folders)
        task_store[task_id]["total"] = total_subjects
        task_store[task_id]["processed"] = 0

        # 각 subject 유효성 검사
        validation_results = {}
        for subject_folder in subject_folders:
            subject_name = subject_folder.name
            validation_results[subject_name] = validate_subject_folder(subject_folder)

        # 유효하지 않은 subject 확인
        invalid_subjects = [
            name for name, result in validation_results.items()
            if not result["valid"]
        ]

        if invalid_subjects:
            errors = {
                name: validation_results[name]["error"]
                for name in invalid_subjects
            }
            task_store[task_id]["status"] = "failed"
            task_store[task_id]["error"] = {
                "message": "Validation failed for some subjects",
                "invalid_subjects": errors
            }
            return

        # 각 subject별로 ZIP 생성 및 저장
        upload_results = []
        event_results = []

        for idx, subject_folder in enumerate(subject_folders):
            subject_name = subject_folder.name

            # uploadTime이 빈 문자열일 경우에만 각 subject마다 고유한 uploadTime 생성
            if not upload_time:
                subject_upload_time = datetime.now().strftime("%y%m%d%H%M%S") + datetime.now().strftime("%f")[:3]
            else:
                subject_upload_time = upload_time

            # Upload 경로 생성
            upload_path = Path(UPLOAD_DIR) / user / subject_name / subject_upload_time
            upload_path.mkdir(parents=True, exist_ok=True)

            # Subject ZIP 생성 및 저장
            subject_zip_path = create_subject_zip(subject_folder, upload_path)

            upload_results.append({
                "subject_id": subject_name,
                "modalities": validation_results[subject_name]["modalities"],
                "filepath": str(subject_zip_path),
                "file_size": subject_zip_path.stat().st_size
            })

            # 각 subject별 Event JSON 생성
            event_path = Path(EVENT_DIR)
            event_path.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            event_filename = f"event_{timestamp}.json"
            event_filepath = event_path / event_filename

            # subject별 event_dict 생성
            subject_event = event_dict.copy()
            subject_event["subjectId"] = subject_name
            subject_event["uploadTime"] = subject_upload_time

            with open(event_filepath, 'w', encoding='utf-8') as f:
                json.dump(subject_event, f, indent=2, ensure_ascii=False)

            event_results.append({
                "subject_id": subject_name,
                "filepath": str(event_filepath),
                "filename": event_filename
            })

            # 진행률 업데이트
            task_store[task_id]["processed"] = idx + 1

        # 완료
        task_store[task_id]["status"] = "completed"
        task_store[task_id]["result"] = {
            "message": f"Successfully processed {total_subjects} subjects",
            "user": user,
            "upload_time": upload_time,
            "subjects": upload_results,
            "events": event_results
        }

    except Exception as e:
        task_store[task_id]["status"] = "failed"
        task_store[task_id]["error"] = str(e)
    finally:
        # 임시 디렉토리 정리
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)


@router.post("/request/multiple")
async def request_multiple(
    event: str = File(...),
    data: UploadFile = File(...)
):
    """
    여러 Subject가 포함된 ZIP 파일 처리 (비동기)
    - 즉시 task_id 반환
    - 백그라운드에서 처리
    - GET /task/{task_id}로 상태 확인

    event JSON 필수 키: user, uploadTime (subjectId는 폴더명에서 추출)
    """
    try:
        # 1. event JSON 파싱
        try:
            event_dict = json.loads(event)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON format in event")

        # 2. 필수 키 추출 (subjectId는 제외)
        user = event_dict.get("user")
        upload_time = event_dict.get("uploadTime", "")

        # uploadTime은 빈 문자열이면 _process_multiple_subjects에서 각 subject마다 생성됨

        if not user:
            raise HTTPException(
                status_code=400,
                detail="Missing required key: user"
            )

        # 3. ZIP 파일 확인
        if not data.filename.endswith('.zip'):
            raise HTTPException(status_code=400, detail="Only ZIP files are allowed")

        # 4. 임시 디렉토리에 ZIP 저장 (청크 단위)
        temp_dir = tempfile.mkdtemp()
        temp_zip_path = Path(temp_dir) / data.filename

        with open(temp_zip_path, "wb") as buffer:
            while chunk := await data.read(CHUNK_SIZE):
                buffer.write(chunk)

        # 5. Task ID 생성 및 상태 초기화
        task_id = str(uuid.uuid4())
        task_store[task_id] = {
            "status": "pending",
            "user": user,
            "upload_time": upload_time,
            "created_at": datetime.now().isoformat(),
            "total": 0,
            "processed": 0,
            "result": None,
            "error": None
        }

        # 6. 백그라운드에서 처리 시작
        loop = asyncio.get_event_loop()
        loop.run_in_executor(
            executor,
            _process_multiple_subjects,
            task_id,
            event_dict,
            str(temp_zip_path),
            temp_dir
        )

        return {
            "status": "accepted",
            "message": "Processing started in background",
            "task_id": task_id,
            "check_status_url": f"/task/{task_id}"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process request: {str(e)}")


@router.get("/task/{task_id}")
async def get_task_status(task_id: str):
    """
    백그라운드 태스크 상태 확인
    """
    if task_id not in task_store:
        raise HTTPException(status_code=404, detail="Task not found")

    task = task_store[task_id]

    response = {
        "task_id": task_id,
        "status": task["status"],
        "user": task["user"],
        "upload_time": task["upload_time"],
        "created_at": task["created_at"],
        "progress": {
            "total": task["total"],
            "processed": task["processed"]
        }
    }

    if task["status"] == "completed":
        response["result"] = task["result"]
    elif task["status"] == "failed":
        response["error"] = task["error"]

    return response


#################################################################
#                   5. 다운로드 (전체 또는 특정 경로)                #
#################################################################
@router.post("/download")
async def download_path(request_body: dict = {}):
    """
    WORKING_DIR 내 파일들을 ZIP으로 압축하여 다운로드
    - path가 없거나 빈 값: WORKING_DIR 전체 다운로드
    - path가 있으면: 해당 경로 하위만 다운로드 (예: "/CNA_lab" 또는 "CNA_lab")
    - 디렉토리 구조를 보존하여 압축
    """
    try:
        relative_path = request_body.get("path", "").strip().lstrip("/")
        working_path = Path(WORKING_DIR).resolve()

        # 대상 경로 결정
        if relative_path:
            # 특정 경로 다운로드
            target_path = (Path(WORKING_DIR) / relative_path).resolve()

            # 경로 traversal 공격 방지
            if not str(target_path).startswith(str(working_path)):
                raise HTTPException(
                    status_code=400,
                    detail="Invalid path: path traversal not allowed"
                )

            if not target_path.exists():
                raise HTTPException(
                    status_code=404,
                    detail=f"Path does not exist: {relative_path}"
                )

            if not target_path.is_dir():
                raise HTTPException(
                    status_code=400,
                    detail=f"Path is not a directory: {relative_path}"
                )

            folder_name = target_path.name
        else:
            # 전체 다운로드
            target_path = working_path
            folder_name = "bids"

            if not target_path.exists():
                raise HTTPException(
                    status_code=404,
                    detail=f"WORKING_DIR does not exist: {WORKING_DIR}"
                )

        # 파일이 하나도 없는 경우 체크
        files = list(target_path.rglob("*"))
        file_count = sum(1 for f in files if f.is_file())

        if file_count == 0:
            raise HTTPException(
                status_code=404,
                detail=f"No files found in: {relative_path or 'WORKING_DIR'}"
            )

        # 메모리에 ZIP 생성
        zip_buffer = io.BytesIO()

        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_path in target_path.rglob("*"):
                arcname = file_path.relative_to(target_path)
                if file_path.is_file():
                    zipf.write(file_path, arcname)
                elif file_path.is_dir():
                    # 빈 폴더도 포함하기 위해 디렉토리 엔트리 추가
                    zipf.write(file_path, str(arcname) + "/")

        zip_buffer.seek(0)

        # 파일명 생성
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{folder_name}_{timestamp}.zip"

        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create download: {str(e)}")
