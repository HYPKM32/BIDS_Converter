# PET 도메인 처리 로직

PET 도메인은 양전자 방출 단층촬영(Positron Emission Tomography) 데이터를 BIDS 표준 형식으로 변환하는 파이프라인입니다.

## 목차
- [개요](#개요)
- [MRI와의 차이점](#mri와의-차이점)
- [처리 단계](#처리-단계)
  - [Step 1: Source 단계](#step-1-source-단계)
  - [Step 2: Raw 단계](#step-2-raw-단계)
  - [Step 3: Post 단계](#step-3-post-단계)
- [데이터 구조](#데이터-구조)
- [설정 파일](#설정-파일)

---

## 개요

### 지원 포맷
- **DICOM만 지원**: `.dcm`, `.dicom`, `.ima`
- PARREC, NIFTI는 지원하지 않음

### 처리 흐름
```
DICOM 데이터 (Upload)
    ↓
Step 1: Source (검증 및 분류) - DICOM만
    ↓
Step 2: Raw (BIDS 변환) - Tracer 매핑
    ↓
Step 3: Post (후처리 및 검증) - MRI 재사용
    ↓
최종 결과 (Export)
```

---

## MRI와의 차이점

| 항목 | MRI | PET |
|------|-----|-----|
| **지원 포맷** | DICOM, PARREC, NIFTI | DICOM만 |
| **Modality 매핑** | `dicom_modality.json` | 없음 (항상 `pet`) |
| **Tracer 매핑** | 없음 | `dicom_tracer.json` (필수) |
| **필수 entity** | `sub`, `ses` | `sub`, `ses`, `trc` |
| **선택 entity** | `task`, `acq`, `dir`, `run` | `acq`, `rec`, `run` |
| **Data type** | `anat`, `func`, `dwi` 등 | `pet` 고정 |
| **Suffix** | `T1w`, `T2w`, `bold` 등 | `pet` 고정 |
| **Validator** | 3개 (Dicom, Parrec, Nifti) | 1개 (Dicom만) |
| **Separator** | 3개 (Dicom, Parrec, Nifti) | 1개 (Dicom만) |
| **Mapper** | DicomMapper, ParrecMapper, NiftiMapper | DicomTracerMapper만 |

---

## 처리 단계

## Step 1: Source 단계

**모듈 위치**: `/BDSP/bids_app/src/process/components/domain/pet/source/`

**목적**: DICOM 데이터를 검증하고 분류

### 디렉토리 구조

```
sourcedata/
└── sub-{alias_id}/
    ├── participants.tsv
    ├── participants.json
    └── ses-{session}/
        └── DICOM/  # PET은 DICOM만 지원
            ├── invalid_data/
            │   └── bdsp_file_list.json
            └── valid_data/
                └── set-{hash}/
                    ├── bdsp_file_list.json
                    └── item_set-xxx_0001.dcm
```

### 주요 함수

#### `create_source_path()`

**파일**: `source.py`

```python
def create_source_path(structured_config, mss_path, origin_unzip_path):
    """PET Source 경로를 생성하고 반환"""
```

**처리 과정**:
1. 포맷 감지 (`get_file_format()`)
   - DICOM이 아니면 에러 발생
2. DicomValidator 실행
3. DicomSeparator 실행
4. 결과 반환

**반환값**:
```python
{
    'source_path': '/path/to/sourcedata',
    'subject_path': '/path/to/sub-xxx',
    'session_path': '/path/to/ses-01',
    'format_path': '/path/to/DICOM',
    'invalid_data_path': '/path/to/invalid_data',
    'valid_data_path': '/path/to/valid_data',
    'validated_sets': [{'validated_set_dir': '...', 'set_id': 'set-xxx'}],
    'separated_paths': ['/path/to/set-xxx']
}
```

### Validator & Separator

PET은 MRI의 DicomValidator와 DicomSeparator를 그대로 재사용합니다.

**DicomValidator**: StudyUID + SeriesUID로 그룹핑
**DicomSeparator**: `item_{set_id}_{index:04d}.dcm` 형식으로 재명명

---

## Step 2: Raw 단계

**모듈 위치**: `/BDSP/bids_app/src/process/components/domain/pet/raw/`

**목적**: BIDS 표준 형식으로 변환 (Tracer 정보 포함)

### 디렉토리 구조

```
rawdata/
└── sub-{alias_id}/
    └── ses-{session}/
        └── pet/  # data_type 고정
            ├── sub-xxx_ses-01_trc-18FFDG_run-01_pet.nii.gz
            ├── sub-xxx_ses-01_trc-18FFDG_run-01_pet.json
            ├── sub-xxx_ses-01_trc-11CPIB_acq-%u_run-01_pet.nii.gz
            └── sub-xxx_ses-01_trc-11CPIB_acq-001_run-01_pet.json
```

### 핵심: Tracer 매핑

#### DicomTracerMapper

**파일**: `tracer_mapper.py`

```python
class DicomTracerMapper:
    def __init__(self, global_vars, structured_config, separated_paths):
        self.tracer_mapping = self._load_tracer_mapping()
```

**처리 과정**:

1. **Tracer 매핑 파일 로드**
   ```python
   def _load_tracer_mapping(self):
       filename = f"{systemId}_{projectCode}_{projectSeq}_{orgId}_dicom_tracer.json"
       mapping_path = os.path.join(global_vars['dicom_modality'], filename)
   ```

2. **DICOM 메타데이터 추출 (태그 번호 + keyword 이중 저장)**
   ```python
   def _get_dicom_metadata(self, dicom_path):
       """DICOM 파일에서 모든 메타데이터 추출 (태그와 keyword 모두 저장)"""
       ds = pydicom.dcmread(dicom_path, stop_before_pixels=True)
       metadata = {}

       for elem in ds:
           if elem.value:
               # 원본 값
               original_value = str(elem.value)
               # 정규화된 값: 공백 제거 → 특수문자 제거 → 소문자 변환
               normalized_value = remove_special_chars(remove_all_whitespace(original_value)).lower()

               # 1. 태그 번호로 저장 (예: "0008,103e" -> "0008103e")
               tag_str = f"{elem.tag.group:04x},{elem.tag.element:04x}"
               normalized_tag = remove_special_chars(remove_all_whitespace(tag_str)).lower()
               metadata[normalized_tag] = normalized_value

               # 2. keyword로도 저장 (예: "SeriesDescription" -> "seriesdescription")
               if hasattr(elem, 'keyword') and elem.keyword:
                   normalized_keyword = remove_special_chars(remove_all_whitespace(elem.keyword)).lower()
                   metadata[normalized_keyword] = normalized_value

       return metadata
   ```

   **정규화 규칙**:
   - **키 정규화**: 공백 제거 → 특수문자 제거 → 소문자 변환
   - **값 정규화**: 공백 제거 → 특수문자 제거 → 소문자 변환
   - **이중 저장**: DICOM 태그를 태그 번호("0008103e")와 keyword("seriesdescription") 두 가지 키로 저장
   - **예시**:
     - 태그 `0008,103e` (SeriesDescription) = "ADNI Brain PET: Raw AV45"
     - → `metadata["0008103e"] = "adnibrainpetrawav45"`
     - → `metadata["seriesdescription"] = "adnibrainpetrawav45"`

3. **Tracer 판단 (우선순위: JSON 인덱스가 높을수록 우선)**
   ```python
   def _determine_tracer(self, dicom_metadata):
       """DICOM 메타데이터를 기반으로 tracer 판단 (인덱스가 높은 것이 우선순위)"""
       # JSON 파일에서 아래에 있는 tracer가 우선순위를 갖도록 역순으로 순회
       for tracer, rules in reversed(list(self.tracer_mapping.items())):
           # 각 rule도 역순으로 순회 (리스트 내 인덱스가 높은 것이 우선)
           for rule in reversed(rules):
               # JSON의 각 키에 대해 확인
               for json_key, expected_values in rule.items():
                   # JSON 키를 정규화: 공백 제거 → 특수문자 제거 → 소문자 변환
                   normalized_key = remove_special_chars(remove_all_whitespace(json_key)).lower()

                   # 메타데이터에 해당 키가 있는지 확인
                   if normalized_key in dicom_metadata:
                       dicom_value = dicom_metadata[normalized_key]

                       # expected_values도 정규화하여 비교
                       for expected_value in expected_values:
                           # 공백 제거 → 특수문자 제거 → 소문자 변환
                           normalized_expected = remove_special_chars(
                               remove_all_whitespace(str(expected_value))
                           ).lower()

                           if dicom_value == normalized_expected:
                               logger.info(f"✓ Tracer matched: {tracer} (key: {json_key}, value: {expected_value})")
                               return tracer

       logger.warning("No tracer matched, returning 'unknown'")
       return 'unknown'
   ```

   **정규화 비교 예시**:
   - JSON expected value: `"ADNI Brain PET: Raw AV45"`
   - → 정규화: `"adnibrainpetrawav45"`
   - DICOM value: `"ADNI Brain PET: Raw AV45"`
   - → 정규화: `"adnibrainpetrawav45"`
   - → 매칭 성공! ✓

   **우선순위 규칙**:
   - JSON 파일에서 **아래에 있는 tracer일수록 우선순위가 높음**
   - 여러 tracer와 매칭되는 경우, **인덱스가 가장 높은 것**이 선택됨
   - 예: DICOM 헤더가 `18FFDG`와 `18FAV45` 모두 매칭 → JSON에서 더 아래에 있는 것 선택

**Tracer 매핑 JSON 예시 (DICOM 태그 번호 또는 keyword 사용 가능)**:
```json
{
  "18FFDG": [
    {
      "RadiopharmaceuticalInformationSequence": ["18F-FDG", "FDG"],
      "Radiopharmaceutical": ["18F-FDG", "Fluorodeoxyglucose F 18"]
    }
  ],
  "11CPIB": [
    {
      "0018,0031": ["11C-PIB", "PIB"],
      "Radiopharmaceutical": ["11C-PIB", "Pittsburgh Compound B"]
    }
  ],
  "18FAV45": [
    {
      "0008,103e": ["ADNI Brain PET: Raw AV45"],
      "Radiopharmaceutical": ["Florbetapir", "AV-45"]
    }
  ]
}
```

**키 형식 지원**:
- **DICOM keyword**: `"SeriesDescription"`, `"Radiopharmaceutical"`
- **DICOM 태그 번호**: `"0008,103e"`, `"0018,0031"`
- 두 형식 모두 사용 가능하며, 내부적으로 정규화되어 매칭됨

**매칭 로직 예시**:
- DICOM 헤더의 `0008,103e` (SeriesDescription) = `"ADNI Brain PET: Raw AV45"`
- → 키 정규화: `"0008,103e"` → `"0008103e"`
- → 값 정규화: `"ADNI Brain PET: Raw AV45"` → `"adnibrainpetrawav45"`
- → JSON expected value 정규화: `"ADNI Brain PET: Raw AV45"` → `"adnibrainpetrawav45"`
- → 매칭 성공! ✓
- → tracer = `"18FAV45"`
- → BIDS entity: `trc-18FAV45`

**반환값**:
```python
{
    '/path/to/set-abc123': '18FFDG',
    '/path/to/set-def456': '11CPIB'
}
```

### BIDS 파일명 생성

#### `build_bids_filename()`

**파일**: `name_builder.py`

```python
def build_bids_filename(tracer, entity_rules, alias_id, trial_index, run_number=None):
    """PET BIDS 파일명 생성"""
```

**Entity 구성 순서**:

1. **sub** (필수): `sub-{alias_id}`
2. **ses** (필수): `ses-{trial_index}`
3. **trc** (필수): `trc-{tracer}`  ← PET의 핵심!
4. **acq** (선택): `acq-%u` (dcm2niix가 동적 치환)
5. **rec** (선택): 사용하지 않음
6. **run** (필수): `run-{run_number}`
7. **suffix** (필수): `pet` 고정

**최종 파일명 예시**:
```
sub-21CNA000011_ses-01_trc-18FFDG_run-01_pet.nii.gz
sub-21CNA000011_ses-01_trc-11CPIB_acq-%u_run-01_pet.nii.gz
```

**dcm2niix 처리 후**:
```
sub-21CNA000011_ses-01_trc-11CPIB_acq-001_run-01_pet.nii.gz
```

### Run 번호 관리

```python
def get_base_run_number(tracer, alias_id, trial_index, raw_path, data_type):
    """기존 파일들을 확인하여 시작 run 번호를 결정"""

    # 패턴: sub-*_ses-*_trc-{tracer}_*_pet.nii.gz
    pattern = os.path.join(target_dir, f"*_trc-{tracer}_*_pet.nii.gz")
    existing_files = glob.glob(pattern)

    # 최대 run 번호 + 1
    return max(run_numbers) + 1 if run_numbers else 1
```

**특징**:
- Tracer별로 독립적인 run 번호 관리
- `18FFDG`와 `11CPIB`는 각각 run-01부터 시작 가능

### dcm2niix 변환

**파일**: `dcm2nii_parser.py` (MRI와 동일)

```bash
dcm2niix -f sub-xxx_ses-01_trc-18FFDG_run-01_pet -z y -o {output_dir} {input_dir}
```

**반환값**:
```python
{
    '/source/set-abc123': '/raw/.../sub-xxx_ses-01_trc-18FFDG_run-01_pet.nii.gz',
    '/source/set-def456': '/raw/.../sub-xxx_ses-01_trc-11CPIB_run-01_pet.nii.gz'
}
```

---

## Step 3: Post 단계

**모듈 위치**: `/BDSP/bids_app/src/process/components/domain/pet/post/`

**특징**: bids_checker는 PET 전용, byproduct와 thumbnail은 MRI 재사용

```python
# /BDSP/bids_app/src/process/components/domain/pet/post/__init__.py
from process.components.domain.pet.post import bids_checker  # PET 전용
from process.components.domain.mri.post import byproduct     # MRI 재사용
from process.components.domain.mri.post import thumbnail     # MRI 재사용
```

**PET 전용 bids_checker의 차이점**:
- `_extract_data_type_and_modality()` 함수가 항상 `('pet', 'pet')`을 반환
- MRI는 파일 경로에서 data_type을 추출하지만, PET은 고정값 사용
- 폴더 구조 검증 시 `pet/` 폴더 존재 여부 확인

### 후처리 단계

1. **BIDS Checker**: NIfTI 파일 검증, Sidecar JSON 확인
2. **Byproduct Checker**: 부산물 파일 수집
3. **Thumbnail Generator**: 썸네일 생성 (Axial, Coronal, Sagittal)

**최종 통합 결과**:
```python
{
    '/raw/.../sub-xxx_ses-01_trc-18FFDG_run-01_pet.nii.gz': {
        # BIDS Checker
        'nifti_exists': True,
        'sidecar_json': '/raw/.../sub-xxx_ses-01_trc-18FFDG_run-01_pet.json',
        'bids_guess': 'pet',
        'data_type': 'pet',
        'modality': 'pet',
        'folder_structure_valid': True,
        'warnings': [],

        # Thumbnail
        'thumbnail': '/raw/.../sub-xxx_ses-01_trc-18FFDG_run-01_pet.png',

        # Source 역매핑
        'source': '/source/.../DICOM/valid_data/set-abc123'
    }
}
```

---

## 데이터 구조

### 전체 파이프라인 흐름

```
1. Upload
   /BDSP/interfaces/upload/{systemId}/{원본.zip}

2. Origin (unzip)
   /BDSP/interfaces/working/{orgId}/pet/BRAIN/{projectCode}/origin/
   ├── zip/
   └── unzip/
       └── bdsp_file_list.json

3. Source (validation & separation)
   /BDSP/interfaces/working/{orgId}/pet/BRAIN/{projectCode}/sourcedata/
   └── sub-{alias_id}/
       ├── participants.tsv
       ├── participants.json
       └── ses-{session}/
           └── DICOM/
               ├── invalid_data/
               └── valid_data/
                   └── set-{hash}/
                       └── item_set-xxx_0001.dcm

4. Raw (BIDS conversion)
   /BDSP/interfaces/working/{orgId}/pet/BRAIN/{projectCode}/rawdata/
   └── sub-{alias_id}/
       └── ses-{session}/
           └── pet/
               ├── sub-xxx_ses-01_trc-18FFDG_run-01_pet.nii.gz
               ├── sub-xxx_ses-01_trc-18FFDG_run-01_pet.json
               └── sub-xxx_ses-01_trc-18FFDG_run-01_pet.png

5. Export
   /BDSP/interfaces/backup/{systemId}/export.json
```

---

## 설정 파일

### 1. Tracer Mapping JSON

**위치**: `/BDSP/bids_app/src/utils/modality_json/dicom/{systemId}_{projectCode}_{projectSeq}_{orgId}_dicom_tracer.json`

**구조**:
```json
{
  "{tracer_value}": [
    {
      "{DICOM_header_key}": ["{expected_value1}", "{expected_value2}"]
    }
  ]
}
```

**예시**:
```json
{
  "18FFDG": [
    {
      "RadiopharmaceuticalInformationSequence": ["18F-FDG", "FDG", "Fluorodeoxyglucose"],
      "Radiopharmaceutical": ["18F-FDG", "FDG"]
    }
  ],
  "11CPIB": [
    {
      "RadiopharmaceuticalInformationSequence": ["11C-PIB", "PIB", "Pittsburgh Compound B"],
      "Radiopharmaceutical": ["11C-PIB", "PIB"]
    }
  ],
  "18FAV45": [
    {
      "RadiopharmaceuticalInformationSequence": ["18F-AV45", "AV-45", "Florbetapir"],
      "Radiopharmaceutical": ["Florbetapir", "18F-AV45"]
    }
  ],
  "18FAV1451": [
    {
      "RadiopharmaceuticalInformationSequence": ["18F-AV1451", "Flortaucipir"],
      "Radiopharmaceutical": ["Flortaucipir", "18F-AV1451", "T807"]
    }
  ],
  "18FMK6240": [
    {
      "RadiopharmaceuticalInformationSequence": ["18F-MK6240"],
      "Radiopharmaceutical": ["18F-MK6240"]
    }
  ]
}
```

**매칭 로직**:
1. DICOM 헤더에서 모든 태그 추출 (태그 번호 + keyword 이중 저장)
2. **키 정규화**: 공백 제거 → 특수문자 제거 → 소문자 변환
   - 예: `"0008,103e"` → `"0008103e"`
   - 예: `"SeriesDescription"` → `"seriesdescription"`
3. **값 정규화**: 공백 제거 → 특수문자 제거 → 소문자 변환
   - 예: `"ADNI Brain PET: Raw AV45"` → `"adnibrainpetrawav45"`
   - 예: `"Fluorodeoxyglucose F^18^"` → `"fluorodeoxyglucose f18"`
4. JSON의 각 tracer를 **역순으로** 순회 (아래에 있는 tracer부터 확인)
5. 각 tracer의 rule도 **역순으로** 순회
6. JSON 키를 정규화하여 메타데이터에서 검색
7. JSON expected_values도 정규화하여 DICOM 값과 비교
8. 매칭되면 즉시 해당 tracer 반환
9. 매칭되는 것이 없으면 `'unknown'`

**우선순위 예시**:
```json
{
  "18FFDG": [...],      // 인덱스 0 - 마지막에 확인
  "11CPIB": [...],      // 인덱스 1
  "18FAV45": [...],     // 인덱스 2
  "18FFBB": [...],      // 인덱스 3
  "18FNAV4694": [...]   // 인덱스 4 - 가장 먼저 확인 (최우선순위)
}
```

실제 순회 순서: `18FNAV4694` → `18FFBB` → `18FAV45` → `11CPIB` → `18FFDG`

### 2. Suffix Map JSON

**위치**: `/BDSP/bids_app/src/utils/modality_json/suffix.json`

**PET 부분**:
```json
{
  "pet": {
    "pet": {
      "required": ["sub", "ses", "trc"],
      "optional": ["acq", "rec", "run"]
    }
  }
}
```

**의미**:
- **data_type**: `"pet"` (폴더명)
- **suffix**: `"pet"` (파일명 마지막 토큰)
- **required**: `sub`, `ses`, `trc` (tracer 필수!)
- **optional**: `acq`, `rec`, `run`
- **실제 사용**: `sub`, `ses`, `trc`, `acq` (선택), `run`

---

## 클래스 및 모듈

### Source 모듈

| 파일 | 클래스/함수 | 설명 |
|------|------------|------|
| `source.py` | `create_source_path()` | PET Source 경로 생성 메인 함수 |
| | `get_file_format()` | 포맷 감지 (DICOM만 허용) |
| | `copy_files_to_invalid()` | 원본 파일을 invalid_data로 복사 |
| | `make_participants_file()` | participants.tsv/json 생성 |
| `validator.py` | `DicomValidator` | DICOM 파일 유효성 검사 (MRI 재사용) |
| `separator.py` | `DicomSeparator` | DICOM 파일 재명명 (MRI 재사용) |

### Raw 모듈

| 파일 | 클래스/함수 | 설명 |
|------|------------|------|
| `raw.py` | `create_raw_path()` | PET Raw 데이터 생성 메인 함수 |
| `tracer_mapper.py` | `DicomTracerMapper` | DICOM 메타데이터 → tracer |
| | `_load_tracer_mapping()` | Tracer JSON 파일 로드 |
| | `_get_dicom_metadata()` | DICOM 메타데이터 추출 |
| | `_determine_tracer()` | Tracer 판단 로직 |
| | `get_path_mapping()` | 경로 → tracer 매핑 |
| `name_builder.py` | `create_bids_mapping()` | BIDS 파일명 매핑 생성 |
| | `build_bids_filename()` | PET BIDS 파일명 구성 |
| | `get_base_run_number()` | Tracer별 run 번호 확인 |
| `dcm2nii_parser.py` | `process_bids_conversion()` | 변환 오케스트레이터 (MRI 재사용) |
| | `run_dcm2niix()` | dcm2niix 실행 (MRI 재사용) |

### Post 모듈

| 파일 | 설명 |
|------|------|
| `__init__.py` | Post 모듈 import 정의 |
| `bids_checker.py` | PET 전용 BIDS 검증 (data_type='pet', modality='pet' 고정) |
| `byproduct` | MRI의 byproduct 재사용 |
| `thumbnail` | MRI의 thumbnail 재사용 |

---

## 에러 처리

### PET 특화 에러

1. **DICOM이 아닌 포맷**
   ```python
   if file_format != "DICOM":
       raise ValueError(f"PET 도메인은 DICOM만 지원합니다. 현재 포맷: {file_format}")
   ```

2. **Tracer 매핑 파일 없음**
   ```python
   except FileNotFoundError:
       logger.error(f"DICOM tracer mapping file not found: {mapping_path}")
       return {}
   ```

3. **여러 Tracer 혼재**
   ```python
   if len(tracers) > 1:
       raise ValueError(f"Multiple tracers found in {set_path}: {tracers}")
   ```

4. **Unknown Tracer**
   ```python
   if tracer == 'unknown':
       logger.warning(f"Unknown tracer detected in {set_path}")
       # 처리 계속 진행 (unknown으로 저장)
   ```

---

## 확장 가이드

### 새로운 Tracer 추가

1. **Tracer JSON 파일 업데이트**
   ```json
   {
     "18FFBB": [
       {
         "RadiopharmaceuticalInformationSequence": ["18F-FBB", "Florbetaben"],
         "Radiopharmaceutical": ["18F-FBB"]
       }
     ]
   }
   ```

2. **자동으로 인식됨** (코드 수정 불필요)

### PARREC 또는 NIFTI 지원 추가 (향후)

현재 PET은 DICOM만 지원하지만, 필요시 다음과 같이 확장 가능:

1. **source.py** 수정
   ```python
   _VALIDATOR_CLASS = {
       "DICOM": "DicomValidator",
       "PARREC": "ParrecValidator",  # 추가
   }
   ```

2. **validator.py** 확장
   - MRI의 ParrecValidator 복사 및 PET 특화

3. **tracer_mapper.py** 확장
   - ParrecTracerMapper 클래스 추가

---

## 성능 최적화

### 1. Tracer 매핑 캐싱
```python
# 프로젝트당 한 번만 로드
self.tracer_mapping = self._load_tracer_mapping()
```

### 2. DICOM 메타데이터 최소 읽기
```python
# 픽셀 데이터 제외
ds = pydicom.dcmread(dicom_path, stop_before_pixels=True)
```

### 3. 병렬 처리 가능 지점
- 여러 세트를 동시에 변환 (dcm2niix는 독립적)
- 여러 파일을 동시에 썸네일 생성

---

**Last Updated**: 2026-01-02
