# BDSP (Brain Data Standard Pipeline)

BIDS (Brain Imaging Data Structure) 형식으로 의료 영상 데이터를 자동 변환하고 처리하는 파이프라인 시스템

## 목차
- [프로젝트 개요](#프로젝트-개요)
- [시스템 아키텍처](#시스템-아키텍처)
- [설치 및 실행](#설치-및-실행)
- [설정 파일](#설정-파일)
- [데이터 처리 흐름](#데이터-처리-흐름)
- [디렉토리 구조](#디렉토리-구조)
- [API 문서](#api-문서)
- [지원 형식](#지원-형식)

---

## 프로젝트 개요

BDSP는 다양한 형식의 의료 영상 데이터(DICOM, NIFTI, PAR/REC)를 BIDS 표준 형식으로 자동 변환하는 시스템입니다.

### 주요 기능
- **자동 파일 감시**: JSON 설정 파일 기반 자동 처리
- **Multi-domain 지원**: MRI, CT, PET, DATA 도메인
- **BIDS 변환**: dcm2niix를 활용한 표준 형식 변환
- **썸네일 생성**: 자동 미리보기 이미지 생성
- **전처리 파이프라인**: Flag 기반 후처리 작업
- **REST API**: 실시간 상태 조회 및 제어
- **에러 핸들링**: 실패 파일 자동 관리 및 로깅

---

## 시스템 아키�ecture

```
┌─────────────────────────────────────────────────────────────┐
│                     BDSP Application                         │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   API Server │  │   Watchers   │  │ File Monitor │      │
│  │  (FastAPI)   │  │  (5 types)   │  │ (ThreadPool) │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│         │                  │                   │             │
│         └──────────────────┴───────────────────┘             │
│                           │                                  │
│                  ┌────────▼────────┐                        │
│                  │  Process Main   │                        │
│                  └────────┬────────┘                        │
│                           │                                  │
│         ┌─────────────────┼─────────────────┐               │
│         │                 │                 │               │
│    ┌────▼────┐      ┌────▼────┐      ┌────▼────┐          │
│    │   MSS   │      │ Origin  │      │ Domain  │          │
│    │Structure│      │   Path  │      │ Handler │          │
│    └─────────┘      └─────────┘      └────┬────┘          │
│                                            │               │
│                        ┌───────────────────┼───────────┐   │
│                        │                   │           │   │
│                   ┌────▼────┐        ┌────▼────┐ ┌────▼──┐│
│                   │   MRI   │        │   PET   │ │   CT  ││
│                   │ Module  │        │ Module  │ │Module ││
│                   └────┬────┘        └─────────┘ └───────┘│
│                        │                                   │
│            ┌───────────┼───────────┐                       │
│            │           │           │                       │
│       ┌────▼────┐ ┌───▼────┐ ┌────▼────┐                 │
│       │ Source  │ │  Raw   │ │  Post   │                 │
│       │ (분류)   │ │(BIDS변환)│ │(후처리) │                 │
│       └─────────┘ └────────┘ └─────────┘                 │
│                                                             │
│                  ┌──────────────┐                          │
│                  │Export & Flag │                          │
│                  └──────────────┘                          │
└─────────────────────────────────────────────────────────────┘
```

---

## 설치 및 실행

### 요구사항
- Python 3.8+
- dcm2niix (DICOM to NIFTI 변환 도구)
- 필요한 Python 패키지 (requirements.txt 참조)

### 설치

```bash
# 프로젝트 클론
cd /BDSP/bids_app

# 의존성 설치 (requirements.txt가 있는 경우)
pip install -r requirements.txt

# dcm2niix 설치 확인
dcm2niix -v
```

### 실행

```bash
# 메인 애플리케이션 실행
cd /BDSP/bids_app/src
python app.py
```

실행 시 자동으로:
- FastAPI 서버 시작 (기본 포트: 8896)
- 5개의 Watcher 시작
- JSON 파일 모니터링 시작

---

## 설정 파일

### config.ini 위치
`/BDSP/bids_app/src/config.ini`

### 주요 설정

```ini
[DEFAULT]
MAX_WORKERS = 1                              # 동시 처리 작업 수
EVENT_DIR = /BDSP/interfaces/event           # 처리 대기 JSON 파일
WORKING_DIR = /BDSP/interfaces/working       # 처리 중인 파일
UPLOAD_DIR = /BDSP/interfaces/upload         # 업로드된 원본 데이터
BACKUP_DIR = /BDSP/interfaces/backup         # 완료된 파일
ERROR_DIR = /BDSP/interfaces/error           # 에러 발생 파일
LOG_FILENAME = /BDSP/bids_app/logs/bids_app.log
MAGNETIC_STRENGTH_FIELD = 3                  # 자기장 세기 (Tesla)

[MODALITY]
DICOM_MODALITY = /BDSP/bids_app/src/utils/modality_json/dicom
NIFTI_MODALITY = /BDSP/bids_app/src/utils/modality_json/nifti
PARREC_MODALITY = /BDSP/bids_app/src/utils/modality_json/parrec
SUFFIX_MAP = /BDSP/bids_app/src/utils/modality_json/suffix.json

[FLAG]
FLAG_DIR = /BDSP/interfaces/flag
FLAG_OPTION = /BDSP/bids_app/src/utils/flag

[API]
BACKEND_URL = http://210.117.210.9:5000/api/analysis/bids/watch
```

---

## 데이터 처리 흐름

### JSON 설정 파일 구조

```json
{
  "user": "사용자ID",
  "systemId": "시스템ID",
  "projectCode": "프로젝트코드",
  "projectSeq": "프로젝트시퀀스",
  "orgId": "기관ID",
  "trialIndex": "시험번호",
  "uploadTime": "업로드시간",
  "subjectId": "피험자ID",
  "domain": "MRI",
  "bodyPart": "BRAIN",
  "category": "IMAGE",
  "bids": true,
  "public": false,
  "task": {
    "isFunc": false,
    "option": ""
  },
  "flag": []
}
```

### 처리 단계

#### **Step 0: 설정 검증 및 초기화**
- JSON 파일 로드
- 필수 필드 검증: `user`, `systemId`, `projectCode`, `projectSeq`, `orgId`, `trialIndex`, `uploadTime`, `subjectId`
- 선택 필드 기본값 설정
- 공백 제거 및 정규화

#### **Step 1: MSS 구조 생성**
```
/BDSP/interfaces/working/{orgId}/{domain}/{bodyPart}/{projectCode}/
├── source/
├── raw/
├── derivatives/
└── state/
```

#### **Step 2: Origin 경로 생성**
```
origin/
├── zip/        # 원본 압축 파일
└── unzip/      # 압축 해제된 파일
```

#### **Step 3: Source 처리 (Domain별)**
- DICOM, NIFTI, PAR/REC 파일 분류
- 검증 및 시리즈 분리

#### **Step 4: Raw 변환**
- dcm2niix를 사용한 BIDS 형식 변환
- BIDS 명명 규칙 적용
- 메타데이터 생성

#### **Step 5: 후처리**
- **5-1**: BIDS Modality Checker
- **5-2**: Byproduct 확인 (JSON, TSV 파일)
- **5-3**: Thumbnail 생성

#### **Step 6: Export JSON 생성**
- 모든 처리 결과를 JSON으로 저장
- 파일 경로, 메타데이터 포함

#### **Step 7: Flag 처리**
- 전처리 파이프라인 실행 (선택적)

#### **Step 8: Backup**
- Export JSON을 backup 디렉토리로 이동
- `{backup_dir}/{systemId}/export.json`

### bids=false 모드
`bids: false`로 설정하면 Step 1-6을 건너뛰고 Step 7(Flag 처리)만 수행

---

## 디렉토리 구조

### 애플리케이션 구조
```
/BDSP/bids_app/
├── src/
│   ├── app.py                          # 메인 진입점
│   ├── globals.py                      # 전역 설정
│   ├── config.ini                      # 설정 파일
│   │
│   ├── process/
│   │   ├── main.py                     # 핵심 처리 로직
│   │   └── components/
│   │       ├── mss.py                  # MSS 구조 생성
│   │       ├── origin.py               # Origin 경로 관리
│   │       ├── export.py               # Export JSON 생성
│   │       ├── flag.py                 # Flag 처리
│   │       └── domain/
│   │           ├── mri/
│   │           │   ├── source/         # DICOM/NIFTI/PAR 분류
│   │           │   │   ├── source.py
│   │           │   │   ├── separator.py
│   │           │   │   └── validator.py
│   │           │   ├── raw/            # BIDS 변환
│   │           │   │   ├── raw.py
│   │           │   │   ├── dcm2nii_parser.py
│   │           │   │   ├── modality_mapper.py
│   │           │   │   └── name_builder.py
│   │           │   └── post/           # 후처리
│   │           │       ├── bids_checker.py
│   │           │       ├── byproduct.py
│   │           │       └── thumbnail.py
│   │           └── pet/                # PET 도메인
│   │
│   ├── services/
│   │   ├── watch/                      # 파일 감시 서비스
│   │   │   ├── uploadWatcher.py
│   │   │   ├── workingWatcher.py
│   │   │   ├── backupWatcher.py
│   │   │   ├── errorWatcher.py
│   │   │   └── flagWatcher.py
│   │   └── api/                        # REST API
│   │       ├── baseRoutes.py
│   │       ├── modalityRoutes.py
│   │       └── interfacesRoutes.py
│   │
│   └── utils/
│       ├── common.py                   # 공통 유틸리티
│       └── modality_json/              # Modality 설정 파일
│
└── logs/                               # 로그 파일
```

### 데이터 디렉토리 구조
```
/BDSP/interfaces/
├── event/          # JSON 파일 투입 (처리 시작)
├── working/        # 처리 중인 데이터
│   └── {orgId}/
│       └── {domain}/
│           └── {bodyPart}/
│               └── {projectCode}/
│                   ├── source/
│                   ├── raw/
│                   ├── derivatives/
│                   └── state/
├── upload/         # 원본 데이터 업로드
├── backup/         # 완료된 export.json
│   └── {systemId}/
├── error/          # 에러 발생 파일
└── flag/           # Flag 처리용
```

---

## API 문서

### 서버 정보
- **포트**: 8896 (환경변수 PORT로 변경 가능)
- **호스트**: 0.0.0.0

### 주요 엔드포인트

#### Base Routes
```
GET  /health              # 서버 상태 확인
GET  /status              # 처리 상태 조회
```

#### Modality Routes
```
GET  /modality/list       # 지원 Modality 목록
GET  /modality/{type}     # 특정 Modality 정보
```

#### Interface Routes
```
GET  /interfaces/stats    # 디렉토리별 통계
POST /interfaces/process  # 수동 처리 트리거
```

---

## 지원 형식

### Input 형식
- **DICOM** (.dcm, .IMA)
- **NIFTI** (.nii, .nii.gz)
- **PAR/REC** (.par, .rec)

### Output 형식
- **BIDS NIFTI** (.nii.gz)
- **JSON 메타데이터** (.json)
- **Thumbnail** (.png)
- **TSV 파일** (.tsv)

### 지원 도메인
- **MRI** (Magnetic Resonance Imaging)
- **CT** (Computed Tomography)
- **PET** (Positron Emission Tomography)
- **DATA** (일반 데이터)

### 지원 Body Part
- BRAIN (기본값)
- (확장 가능)

---

## 개발 가이드

### 새로운 Domain 추가

1. `/BDSP/bids_app/src/process/components/domain/` 에 새 디렉토리 생성
2. `source/`, `raw/`, `post/` 모듈 구현
3. `main.py`의 domain 분기에 추가

### 새로운 Flag 추가

1. `/BDSP/bids_app/src/utils/flag/` 에 처리 스크립트 추가
2. `flag.py`에서 처리 로직 구현

### 로그 확인

```bash
tail -f /BDSP/bids_app/logs/bids_app.log
```

---

## 트러블슈팅

### 자주 발생하는 문제

**1. JSON 파일이 처리되지 않음**
- EVENT_DIR 경로 확인
- JSON 형식 검증 (필수 필드 확인)
- 로그 파일 확인

**2. DICOM 변환 실패**
- dcm2niix 설치 확인
- DICOM 파일 무결성 확인
- DICOM_MODALITY 경로 확인

**3. 권한 에러**
- 디렉토리 쓰기 권한 확인
- 소유자/그룹 확인

**4. API 서버 연결 실패**
- 포트 8896 사용 여부 확인
- 방화벽 설정 확인

---

## 라이선스

(라이선스 정보 추가)

## 연락처

(담당자 정보 추가)

---

**Last Updated**: 2026-01-02
