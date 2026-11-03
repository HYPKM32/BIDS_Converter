# BIDS_Converter

뇌영상 원본(DICOM, NIfTI, PAR/REC)을 받아 **BIDS** 형식으로 변환하고, 변환된 영상에
얼굴 제거·방향 정규화·CIVET 같은 **후처리(전처리) 도구**를 이어서 실행하는 파이프라인입니다.
변환 서비스와 후처리 도구 컨테이너들을 한 저장소에 모아 두었습니다.

- BIDS 버전: 1.10.0
- 도메인: MRI, PET
- 실행 방식: 서비스마다 Docker 컨테이너 하나. 컨테이너끼리는 공유 폴더에 놓인 **JSON 이벤트 파일**로 통신합니다.

---

## 구성

| 폴더 | 컨테이너 | 역할 | GPU |
|---|---|---|---|
| [`bids/`](bids/Readme.md) | `bids` | 업로드 수신, BIDS 변환, 썸네일 생성, 후처리 순서 관리(오케스트레이터), REST API(포트 8896) | — |
| `defacing-defacer/` | `defacing-defacer` | 얼굴 제거 (Keras 등고선 모델, `model_contour4.h5`) | ✓ |
| `defacing-medfacer/` | `defacing-medfacer` | 얼굴 제거 (3D YOLO 기반 MedYOLO). **개발 중**, 아래 [현재 상태](#현재-상태) 참고 | ✓ |
| `canonical/` | `canonical` | 영상 방향 정규화 (기본값 RAS) | ✓ |
| `civet/` | `T1wPreprocess-civet` | T1w 피질 분석 (CIVET 2.1.1, `mcin/civet` 이미지 기반) | — |

도메인별 상세 처리 로직은 [`bids/domain/MRI.md`](bids/domain/MRI.md)와 [`bids/domain/PET.md`](bids/domain/PET.md)에 정리되어 있습니다.

---

## 전체 흐름

```
 클라이언트 / 백엔드
        │  POST /api/interfaces/request/single   (event JSON + ZIP)
        ▼
┌──────────────────────────── bids ────────────────────────────┐
│ upload → event 감시 → source(분류·검증) → raw(dcm2niix, BIDS 명명) │
│        → post(BIDS 체크, 부산물 확인, 썸네일) → export.json         │
│        → flag 처리: 활성화된 도구를 순서대로 하나씩 실행             │
└───────────────────────────────┬──────────────────────────────┘
                                │ export.json을 flag/{process}/{package}/ 로 이동
                                ▼
          ┌──────────────┬──────────────┬──────────────┐
          │ defacer      │ canonical    │ civet  ...   │  각 컨테이너는 자기 event 폴더를 감시하다가
          └──────┬───────┴──────┬───────┴──────┬───────┘  status=pending인 자기 항목을 처리하고
                 └──────────────┴──────────────┘          status를 done/error로 바꿔 돌려놓음
                                │
                                ▼
                   bids가 다음 도구로 넘기거나 종료 → backup/{systemId}/export.json
```

### 컨테이너 간 연결 방식 (flag)

1. 이벤트 JSON의 `flag` 배열에 실행할 도구를 적습니다. `enabled: true`인 항목만 실행됩니다.
2. `bids`는 BIDS 변환을 마친 뒤 각 도구의 입력 조건(`modCond`, 예: `T1w`)에 맞는 파일을 골라
   input/output 경로를 채우고, JSON을 `FLAG_DIR/{process}/{package}/`로 옮깁니다.
3. 이 폴더는 docker-compose의 named volume으로 해당 도구 컨테이너의 event 폴더(`interfaces/event`)에 연결되어 있습니다.
   도구는 `process`·`package`가 자기 것과 같고 `status: pending`인 항목을 찾아 처리합니다.
4. 도구가 `status`를 `done` 또는 `error`로 바꿔 두면, `bids`가 이를 감지해 다음 도구를 실행합니다
   (도구마다 대기 제한 시간 기본 3600초). 앞 도구의 결과물(`drv-*`)은 다음 도구의 입력으로 쓸 수 있습니다.

도구별 인자와 입출력 규칙은 `bids/src/utils/flag/{process}_{package}.yaml`에 정의합니다.
도구 컨테이너가 무엇을 기다리는지는 각 모듈의 `src/config.ini`에 있는 `PROCESS`, `PACKAGE`, `COMMAND` 값으로 정해집니다.

| 컨테이너 | PROCESS | PACKAGE | flag 폴더 |
|---|---|---|---|
| defacing-defacer | `defacing` | `defacer` | `flag/defacing/defacer` |
| canonical | `canonical` | `canonical` | `flag/canonical/canonical` |
| T1wPreprocess-civet | `T1wPreprocess` | `civet` | `flag/T1wPreprocess/civet` |

---

## 실행

### 요구사항
- Docker, Docker Compose
- NVIDIA GPU와 NVIDIA Container Toolkit (defacer, medfacer, canonical)
- 호스트에 데이터 폴더가 미리 있어야 합니다(아래 볼륨 설정 참고)

### 볼륨과 호스트 설정

`docker-compose.yml`에는 연구실 서버 기준 값이 직접 적혀 있습니다. 다른 환경에서 실행할 때는 먼저 이 값들을 바꾸세요.

| 항목 | 현재 값 | 의미 |
|---|---|---|
| 작업 폴더 | `/nasdata3/BIDS` → 컨테이너 `interfaces/working` | 모든 컨테이너가 공유하는 변환·처리 결과 저장 위치 |
| bids 데이터 | `/nasdata4/parknm/bids` → 컨테이너 `data` | bids 컨테이너 전용 데이터 |
| API 바인딩 | `210.117.210.9:8896` | bids API 포트 |
| GPU | `device_ids: ['1']` | GPU 사용 컨테이너가 쓰는 GPU 번호 |
| 백엔드 알림 | `bids/src/config.ini`의 `BACKEND_URL` | 처리 상태를 알릴 상위 백엔드 주소 |

### 빌드와 기동

```bash
docker compose build
docker compose up -d

# 로그 확인
docker compose logs -f bids
```

각 앱의 소스 폴더는 컨테이너에 bind mount되어 있으므로(`./bids` → 컨테이너의 `bids_app` 등) 코드를 고친 뒤에는
이미지를 다시 빌드하지 않고 `docker compose restart <서비스>`만 하면 됩니다.

---

## 요청 예시

`bids` API는 `http://<host>:8896/api` 아래에 있습니다. 전체 목록은 FastAPI 문서 페이지 `http://<host>:8896/docs`에서 볼 수 있습니다.

| 메서드 | 경로 | 설명 |
|---|---|---|
| GET | `/api/interfaces`, `/api/modality`, `/api/flag` | 폴더 상태, modality 매핑, flag 옵션 조회 |
| POST | `/api/interfaces/request/single` | 이벤트 JSON + ZIP 한 건 업로드 |
| POST | `/api/interfaces/request/multiple` | 여러 건 업로드 |
| GET | `/api/interfaces/task/{task_id}` | 작업 상태 조회 |
| POST | `/api/interfaces/download` | 결과 다운로드 |
| GET | `/api/modality/suffixmap` | BIDS suffix 맵 |
| POST | `/api/modality/mapping/...`, `/api/modality/tracer/...` | 프로젝트별 MRI modality / PET tracer 매핑 등록 |

이벤트 JSON 예시:

```json
{
  "user": "user01",
  "systemId": "...",
  "projectCode": "...",
  "projectSeq": "1",
  "orgId": "...",
  "trialIndex": "1",
  "uploadTime": "",
  "subjectId": "sub001",
  "domain": "MRI",
  "bodyPart": "BRAIN",
  "category": "IMAGE",
  "bids": true,
  "public": false,
  "task": { "isFunc": false, "option": "" },
  "flag": [
    { "process": "defacing", "package": "defacer", "enabled": true, "status": "pending",
      "modCond": [{ "process": "bids", "package": "raw", "modality": ["T1w"] }] }
  ]
}
```

- `uploadTime`을 비워 두면 서버 시각으로 채웁니다.
- `bids: false`이면 BIDS 변환을 건너뛰고 flag 처리만 합니다.
- `flag` 항목의 세부 필드(`modCond`, `space`, 옵션 인자)는 `bids/src/process/components/flag.py`와 flag YAML을 기준으로 맞추세요.

---

## 결과물 폴더 구조

```
{작업 폴더}/{orgId}/{domain}/{bodyPart}/{projectCode}/
├── source/        # 원본 (형식별 분류·검증 후)
├── raw/           # BIDS 변환 결과 (sub-*/ses-*/anat|pet/...)
├── derivatives/   # 후처리 결과 (도구별, run별 exe-NN 폴더)
└── state/
```

---

## 새 도구 추가하기

1. 기존 도구 폴더(예: `canonical/`)를 복사해 새 폴더를 만듭니다. 감시·이동·상태 갱신 코드는 그대로 쓸 수 있습니다.
2. `src/config.ini`의 `PROCESS`, `PACKAGE`, `COMMAND`를 새 도구에 맞게 바꾸고, `COMMAND`가 가리키는 CLI를 구현합니다.
3. `bids/src/utils/flag/{process}_{package}.yaml`에 인자와 입출력 규칙을 적습니다.
4. `docker-compose.yml`에서
   - named volume `{process}-{package}_flag`를 추가하고,
   - `bids` 서비스에 `…:/BDSP/interfaces/flag/{process}/{package}`로,
   - 새 서비스에 `…:/BDSP/interfaces/event`로 마운트합니다.

---

## 현재 상태

- **medfacer**: CLI(`medfacer_cli.py`)만 있고, 다른 도구와 달리 이벤트를 감시하는 `app.py`가 아직 없습니다. 그래서 compose에서는 `/bin/bash`로만 뜨고, `bids`의 flag 폴더에도 연결되어 있지 않습니다.
  `src/model_distribution/MedYOLO`는 submodule로 등록되어 있지만 `.gitmodules`가 없어서, 클론하면 빈 폴더로 받아집니다. 가중치 파일(`weight/best.pt`)도 저장소에 포함되어 있지 않습니다.
- **freesurfer**: `T1wPreprocess-freesurfer_flag` 볼륨만 선언되어 있고 서비스는 아직 없습니다.
- **civet**: `bids/src/utils/flag/`에 civet용 YAML이 없습니다.
- `defacing_defacer.yaml`에는 `process: defacer`, `package: defacing`으로 적혀 있는데, defacer 컨테이너의 config는 `PROCESS=defacing`, `PACKAGE=defacer`로 반대입니다. 실제 라우팅은 이벤트 JSON의 값과 config 값을 기준으로 이뤄지니, YAML을 사용할 때는 이 차이를 확인하세요.
- `bids/Readme.md`의 "API 문서" 절은 예전 경로 기준이라 실제 라우트와 다릅니다. 최신 목록은 위 [요청 예시](#요청-예시) 표나 `/docs`를 참고하세요.
- `canonical/`, `civet/`, `defacing-*/` 폴더의 `Readme.md`는 아직 비어 있습니다.
