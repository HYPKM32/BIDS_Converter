# MRI 도메인 처리 로직

MRI 도메인은 의료 영상 데이터(DICOM, NIFTI, PAR/REC)를 BIDS 표준 형식으로 변환하는 3단계 파이프라인으로 구성됩니다.

## 목차
- [개요](#개요)
- [처리 단계](#처리-단계)
  - [Step 1: Source 단계](#step-1-source-단계)
  - [Step 2: Raw 단계](#step-2-raw-단계)
  - [Step 3: Post 단계](#step-3-post-단계)
- [데이터 구조](#데이터-구조)
- [클래스 및 모듈](#클래스-및-모듈)

---

## 개요

### 지원 포맷
- **DICOM**: `.dcm`, `.dicom`, `.ima`
- **PAR/REC**: `.par`, `.rec` (Philips)
- **NIFTI**: `.nii`, `.nii.gz`

### 처리 흐름
```
원본 데이터 (Upload)
    ↓
Step 1: Source (검증 및 분류)
    ↓
Step 2: Raw (BIDS 변환)
    ↓
Step 3: Post (후처리 및 검증)
    ↓
최종 결과 (Export)
```

---

## 처리 단계

## Step 1: Source 단계

**모듈 위치**: `/BDSP/bids_app/src/process/components/domain/mri/source/`

**목적**: 원본 데이터를 포맷별로 분류하고 유효성 검사 수행

### 디렉토리 구조

```
sourcedata/
└── sub-{alias_id}/
    ├── participants.tsv          # BIDS 참가자 목록
    ├── participants.json         # 참가자 메타데이터
    └── ses-{session}/
        └── {DICOM|PARREC|NIFTI}/
            ├── invalid_data/     # 원본 파일들
            │   └── bdsp_file_list.json
            └── valid_data/       # 검증 통과 파일들
                ├── set-{hash1}/  # 세트별 분리
                │   ├── bdsp_file_list.json
                │   └── item_set-xxx_0001.dcm
                └── set-{hash2}/
```

### 처리 흐름

#### 1. 포맷 감지 (`get_file_format`)

**파일**: `source.py:99-131`

```python
def get_file_format(origin_unzip_path):
    """bdsp_file_list.json에서 index 1인 파일의 확장자로 포맷 판단"""
```

**로직**:
- `bdsp_file_list.json`의 `index=1` 파일 확인
- 확장자 기반 분류:
  - `.dcm`, `.dicom`, `.ima` → `DICOM`
  - `.par`, `.rec` → `PARREC`
  - `.nii`, `.nii.gz`, `.nifti` → `NIFTI`

#### 2. Validation (유효성 검사)

**파일**: `validator.py`

##### DicomValidator

```python
class DicomValidator:
    def run(self) -> List[Tuple[str, str]] | None:
        """DICOM 파일들을 Study/Series UID로 그룹핑하여 검증"""
```

**처리 과정**:
1. `bdsp_file_list.json` 읽기
2. 각 DICOM 파일에서 메타데이터 추출
3. `(StudyInstanceUID, SeriesInstanceUID)`로 그룹핑
4. 그룹별로 SHA1 해시 생성 → `set-{hash}`
5. `valid_data/set-{hash}/` 디렉토리로 파일 이동

**반환값**:
```python
[
    ('/path/to/valid_data/set-abc123', 'set-abc123'),
    ('/path/to/valid_data/set-def456', 'set-def456')
]
```

##### ParrecValidator

```python
class ParrecValidator:
    def run(self) -> List[Tuple[str, str]] | None:
        """PAR/REC 파일 쌍을 검증"""
```

**처리 과정**:
1. PAR 파일과 REC 파일 쌍 찾기
2. 최소 유효성 검사:
   - 파일 존재 확인
   - REC 파일 크기 확인
   - PAR 파일 IMAGE INFORMATION 섹션 확인
   - 최소 1개 이상의 이미지 데이터 확인
3. 유효한 쌍만 `valid_data/set-{hash}/`로 이동

##### NiftiValidator

```python
class NiftiValidator:
    def run(self) -> List[Tuple[str, str]] | None:
        """NIfTI 파일 무결성 검사"""
```

**검증 항목**:
1. 파일 존재 확인
2. NIfTI 파일 로드 가능 여부
3. 헤더 정보 유효성
4. 복셀 크기 정보
5. 공간 변환 행렬 (Affine matrix)
6. 데이터 유효성 (NaN, Inf 값 확인)
7. 차원 검사 (최소 3D)
8. 파일 크기 일관성

**검증 결과 예시**:
```python
{
    'valid': True,
    'errors': [],
    'warnings': [],
    'success': [
        '✓ NIfTI 파일 존재 확인',
        '✓ NIfTI 파일 로드 성공',
        '✓ 복셀 크기 정보 추출 성공',
        '✓ 공간 변환 행렬 정상'
    ],
    'info': {
        'shape': (256, 256, 176),
        'data_type': 'float32',
        'voxel_size': (1.0, 1.0, 1.0),
        'compressed': True
    }
}
```

#### 3. Separation (파일 재구성)

**파일**: `separator.py`

##### DicomSeparator

```python
class DicomSeparator(PreWork):
    def run(self, validated_dir, set_id) -> str:
        """DICOM 파일들을 JSON index 기준으로 재명명"""
```

**명명 규칙**: `item_{set_id}_{index:04d}.dcm`

**예시**:
```
원본: IM-0001-0001.dcm
변경: item_set-abc123_0001.dcm
```

##### ParrecSeparator

```python
class ParrecSeparator(PreWork):
    def run(self, validated_dir, set_id) -> str:
        """PAR/REC 파일 쌍을 재명명"""
```

**명명 규칙**:
- PAR: `item_{set_id}_0001.par`
- REC: `item_{set_id}_0001.rec`

**특징**: PAR/REC는 항상 쌍으로 존재하며 둘 다 `0001` 사용

##### NiftiSeparator

```python
class NiftiSeparator(PreWork):
    def run(self, validated_dir, set_id) -> str:
        """NIfTI 파일 재명명 (모달리티 정보 포함)"""
```

**명명 규칙**: `item_{set_id}_{suffix}_0001.nii.gz`

**suffix 추출 로직**:
- 파일명에서 마지막 `_` 뒤의 토큰
- 예: `sub01_T1w.nii.gz` → suffix = `T1w`
- 없으면 기본값 `NIFTI`

**검증**:
- NIfTI는 무조건 1개만 허용
- index가 2 이상이면 에러

#### 4. Source 단계 반환값

```python
source_path = {
    'source_path': '/path/to/sourcedata',
    'subject_path': '/path/to/sourcedata/sub-21CNA000011',
    'session_path': '/path/to/sourcedata/sub-21CNA000011/ses-01',
    'format_path': '/path/to/sourcedata/sub-21CNA000011/ses-01/DICOM',
    'invalid_data_path': '/path/to/.../DICOM/invalid_data',
    'valid_data_path': '/path/to/.../DICOM/valid_data',

    # 멀티 세트 지원
    'validated_sets': [
        {
            'validated_set_dir': '/path/to/valid_data/set-abc123',
            'set_id': 'set-abc123'
        },
        {
            'validated_set_dir': '/path/to/valid_data/set-def456',
            'set_id': 'set-def456'
        }
    ],
    'separated_paths': [
        '/path/to/valid_data/set-abc123',
        '/path/to/valid_data/set-def456'
    ]
}
```

---

## Step 2: Raw 단계

**모듈 위치**: `/BDSP/bids_app/src/process/components/domain/mri/raw/`

**목적**: BIDS 표준 형식으로 데이터 변환

### 디렉토리 구조

```
rawdata/
└── sub-{alias_id}/
    └── ses-{session}/
        ├── anat/
        │   ├── sub-xxx_ses-01_run-01_T1w.nii.gz
        │   ├── sub-xxx_ses-01_run-01_T1w.json
        │   └── sub-xxx_ses-01_run-02_T2w.nii.gz
        ├── func/
        │   ├── sub-xxx_ses-01_task-rest_run-01_bold.nii.gz
        │   ├── sub-xxx_ses-01_task-rest_run-01_bold.json
        │   └── sub-xxx_ses-01_task-rest_run-01_events.tsv
        └── dwi/
            ├── sub-xxx_ses-01_run-01_dwi.nii.gz
            ├── sub-xxx_ses-01_run-01_dwi.json
            ├── sub-xxx_ses-01_run-01_dwi.bval
            └── sub-xxx_ses-01_run-01_dwi.bvec
```

### 처리 흐름

#### 1. Modality Mapping

**파일**: `modality_mapper.py`

각 포맷별로 Mapper 클래스가 메타데이터를 분석하여 모달리티를 결정합니다.

##### DicomMapper

```python
class DicomMapper:
    def __init__(self, global_vars, structured_config, separated_paths):
        self.modality_mapping = self._load_modality_mapping()
```

**처리 과정**:
1. 프로젝트별 매핑 파일 로드
   - 경로: `{dicom_modality}/{systemId}_{projectCode}_{projectSeq}_{orgId}_dicom_modality.json`
2. 각 DICOM 파일의 메타데이터 추출
3. 메타데이터 키 정규화:
   ```python
   # 공백 제거 → 특수문자 제거 → 소문자 변환
   normalized_key = remove_special_chars(remove_all_whitespace(elem.keyword)).lower()
   ```
4. 매핑 JSON 규칙과 비교하여 모달리티 결정

**매핑 파일 예시**:
```json
{
  "T1w": [
    {
      "SeriesDescription": ["t1_mprage_sag", "T1 MPRAGE"],
      "SequenceName": ["*tfl3d1_16ns"]
    }
  ],
  "T2w": [
    {
      "SeriesDescription": ["t2_tse_sag"],
      "SequenceName": ["*tse2d1_15"]
    }
  ]
}
```

**반환값**:
```python
{
    '/path/to/set-abc123': 'T1w',
    '/path/to/set-def456': 'T2w'
}
```

##### ParrecMapper

```python
class ParrecMapper:
    def get_path_mapping(self):
        """PAR 파일 헤더에서 모달리티 판단"""
```

**처리 과정**:
1. 프로젝트별 매핑 파일 로드
   - 경로: `{parrec_modality}/{systemId}_{projectCode}_{projectSeq}_{orgId}_parrec_modality.json`
2. PAR 파일 파싱 (콜론으로 구분된 키-값)
3. 키 정규화 및 매핑 규칙 적용

##### NiftiMapper

```python
class NiftiMapper:
    def get_path_mapping(self):
        """파일명에서 모달리티 추출"""
```

**파일명 파싱**:
```
item_set-abc123_T1w_0001.nii.gz
                 ^^^
            modality (마지막에서 2번째 토큰)
```

**검증**:
- 마지막 토큰이 `0001`인지 확인
- 그렇지 않으면 ValueError

#### 2. BIDS 파일명 생성

**파일**: `name_builder.py`

##### BIDS Entity 순서

BIDS 표준에 따라 다음 순서로 entity를 구성합니다:

```
sub-<label>_ses-<label>_[task-<label>]_[acq-<label>]_[dir-<label>]_run-<index>_<suffix>.nii.gz
```

##### 함수: `create_bids_mapping`

```python
def create_bids_mapping(path_mapping, structured_config, global_vars, raw_path, alias_id):
    """소스 데이터 경로를 BIDS 형식 경로로 매핑"""
```

**처리 과정**:

1. **suffix_map.json 로드**
   ```json
   {
     "anat": {
       "T1w": {"required": ["sub", "ses"], "optional": ["acq", "run"]},
       "T2w": {"required": ["sub", "ses"], "optional": ["acq", "run"]}
     },
     "func": {
       "bold": {"required": ["sub", "ses", "task"], "optional": ["acq", "dir", "run"]}
     },
     "dwi": {
       "dwi": {"required": ["sub", "ses"], "optional": ["acq", "dir", "run"]}
     }
   }
   ```

2. **Data Type 결정**
   - 모달리티 → Data Type 매핑
   - 예: `T1w` → `anat`, `bold` → `func`, `dwi` → `dwi`

3. **Run 번호 할당**
   - 기존 파일 확인: `glob.glob(f"*_{modality}.nii.gz")`
   - 최대 run 번호 + 1
   - 없으면 `01`부터 시작

4. **Entity 구성**

**함수**: `build_bids_filename`

```python
def build_bids_filename(source_folder, modality, entity_rules, alias_id,
                       trial_index, task_info, run_number=None):
    """BIDS 파일명 생성"""
```

**Entity 추가 로직**:

- **sub** (필수): `sub-{alias_id}`
  ```python
  alias_id = f"{public}{projectCode}{projectSeq}{orgId}{subjectId}"
  # 예: 21CNA000011
  ```

- **ses** (필수): `ses-{trial_index}`
  ```python
  session_num = zero_fill(request['trialIndex'])  # 01, 02, ...
  ```

- **task** (func만): `task-{option}`
  ```python
  if 'task' in entity_rules:
      if not task_info['isFunc']:
          raise ValueError("Task entity required but isFunc=False")
      entities.append(f"task-{task_info['option']}")
  ```

- **acq**: `acq-%u`
  ```python
  if 'acq' in entity_rules:
      entities.append("acq-%u")  # dcm2niix가 동적으로 치환
  ```

- **dir**: `dir-{PhaseEncodingDirection}`
  ```python
  if 'dir' in entity_rules:
      phase_encoding_dir = get_phase_encoding_direction(source_folder)
      if phase_encoding_dir:
          entities.append(f"dir-{phase_encoding_dir}")
  ```

- **run** (필수): `run-{number}`
  ```python
  run_number = zero_fill(current_run)  # 01, 02, ...
  entities.append(f"run-{run_number}")
  ```

**최종 파일명 예시**:
```
sub-21CNA000011_ses-01_run-01_T1w.nii.gz
sub-21CNA000011_ses-01_task-rest_acq-%u_run-01_bold.nii.gz
sub-21CNA000011_ses-01_acq-%u_run-01_dwi.nii.gz
```

##### PhaseEncodingDirection 추출

```python
def get_phase_encoding_direction(source_folder):
    """DICOM 또는 PAR 헤더에서 dir entity 값 추출"""
```

**DICOM**:
```python
ds = pydicom.dcmread(dicom_file, stop_before_pixels=True)
if hasattr(ds, 'PhaseEncodingDirection'):
    return ds.PhaseEncodingDirection
```

**PAR/REC**: TODO (구현 필요)

#### 3. BIDS 변환 실행

**파일**: `dcm2nii_parser.py`

##### NIFTI 처리

```python
def process_nifti_files(src_path, raw_path, raw_file_option):
    """NIFTI 파일 직접 복사 또는 압축"""
```

**처리 로직**:
1. `.nii.gz` → 그대로 복사
2. `.nii` → gzip 압축 후 복사
3. Sidecar 파일 동반 복사:
   - `.json` (메타데이터)
   - `.bval` (DWI b-value)
   - `.bvec` (DWI b-vector)

##### DICOM/PARREC 변환

```python
def run_dcm2niix(src_path, raw_path, raw_file_option):
    """dcm2niix를 사용하여 DICOM/PARREC을 NIFTI로 변환"""
```

**dcm2niix 명령어**:
```bash
dcm2niix -f {filename_without_ext} -z y -o {raw_path} {src_path}
```

**파라미터**:
- `-f`: 출력 파일명 형식 (%-포맷 지원)
- `-z y`: gzip 압축 활성화
- `-o`: 출력 디렉토리
- 마지막: 입력 디렉토리

**%-포맷 해석**:
- `acq-%u`: 시퀀스 번호로 자동 치환
- `%t`: 시간
- `%s`: 시리즈 번호

**실제 결과 파일 찾기**:
```python
def _resolve_actual_output(raw_dir, filename_without_ext):
    """%-포맷이 포함된 파일명에서 실제 생성 파일 찾기"""

    # acq-%u → acq-* 패턴 변환
    glob_base = re.sub(r'%[^_]*', '*', filename_without_ext)

    # 매칭되는 파일들 검색
    candidates = list(raw_dir_p.glob(glob_base + '.nii.gz'))

    # 여러 개면 최신 파일 선택
    if len(candidates) > 1:
        candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)

    return candidates[0]
```

**예시**:
```
요청: sub-xxx_ses-01_acq-%u_run-01_T1w.nii.gz
dcm2niix 생성: sub-xxx_ses-01_acq-001_run-01_T1w.nii.gz
반환: /path/to/sub-xxx_ses-01_acq-001_run-01_T1w.nii.gz
```

##### bdsp_file_list.json 생성

변환 완료 후 각 디렉토리에 파일 목록 생성:
```python
bdsp_walk(raw_path)
```

#### 4. Raw 단계 반환값

```python
raw_path = {
    '/source/set-abc123': '/raw/sub-xxx/ses-01/anat/sub-xxx_ses-01_run-01_T1w.nii.gz',
    '/source/set-def456': '/raw/sub-xxx/ses-01/anat/sub-xxx_ses-01_run-02_T2w.nii.gz',
    '/source/set-ghi789': '/raw/sub-xxx/ses-01/func/sub-xxx_ses-01_task-rest_run-01_bold.nii.gz'
}
```

---

## Step 3: Post 단계

**모듈 위치**: `/BDSP/bids_app/src/process/components/domain/mri/post/`

**목적**: BIDS 형식 검증, 부산물 수집, 썸네일 생성

### 3-1. BIDS Checker

**파일**: `bids_checker.py`

```python
def check_modality(raw_path):
    """BIDS 규격에 따른 모달리티 검증"""
```

**검증 항목**:

1. **NIfTI 파일 존재 확인**
   ```python
   if not os.path.exists(nifti_path):
       raise ValueError(f"NIfTI 파일이 존재하지 않습니다: {nifti_path}")
   ```

2. **Data Type 및 Modality 추출**
   ```python
   def _extract_data_type_and_modality(nifti_path):
       # data_type: 파일 경로의 최종 폴더명
       data_type = Path(nifti_path).parent.name  # 'anat', 'func', 'dwi'

       # modality: 파일명의 마지막 언더바 이후 값
       filename = Path(nifti_path).stem.replace('.nii', '')
       modality = filename.split('_')[-1]  # 'T1w', 'bold', 'dwi'

       return data_type, modality
   ```

3. **Sidecar JSON 확인**
   ```python
   json_path = nifti_path.replace('.nii.gz', '.json')
   if os.path.exists(json_path):
       file_result['sidecar_json'] = json_path
   else:
       file_result['warnings'].append(f"Sidecar JSON 없음: {json_path}")
   ```

4. **BidsGuess 키 추출**

   dcm2niix가 자동으로 생성하는 `BidsGuess` 필드 확인:
   ```python
   with open(json_path, 'r') as f:
       json_data = json.load(f)

   if 'BidsGuess' in json_data:
       bids_guess_list = json_data['BidsGuess']
       modality = bids_guess_list[0]  # 첫 번째 값 사용
       file_result['bids_guess'] = modality
   ```

   **BidsGuess 예시**:
   ```json
   {
     "BidsGuess": ["anat", "_T1w"],
     "Manufacturer": "Siemens",
     "SeriesDescription": "t1_mprage_sag"
   }
   ```

5. **폴더 구조 검증**
   ```python
   def _validate_folder_structure(nifti_path, expected_modality):
       """모달리티 폴더가 올바른 위치에 있는지 확인"""

       path_parts = Path(nifti_path).parts

       # 예상 모달리티가 경로에 있는지 확인
       if expected_modality in path_parts:
           modality_index = path_parts.index(expected_modality)

           # 파일의 바로 상위 폴더인지 확인 ([-2]가 마지막 폴더)
           if modality_index == len(path_parts) - 2:
               return {'valid': True, 'warnings': []}
   ```

**반환 구조**:
```python
{
    '/raw/.../sub-xxx_ses-01_run-01_T1w.nii.gz': {
        'nifti_exists': True,
        'sidecar_json': '/raw/.../sub-xxx_ses-01_run-01_T1w.json',
        'bids_guess': 'T1w',
        'data_type': 'anat',
        'modality': 'T1w',
        'folder_structure_valid': True,
        'warnings': []
    }
}
```

### 3-2. Byproduct Checker

**파일**: `byproduct.py`

```python
def check_byproduct(raw_path):
    """BIDS rawdata에서 .nii.gz와 .json 외의 부산물 파일들을 찾아 정리"""
```

**처리 로직**:

1. NIfTI 파일의 base filename 추출
   ```python
   base_filename = nifti_path.stem.replace('.nii', '')
   # 예: sub-xxx_ses-01_run-01_dwi
   ```

2. 같은 디렉토리에서 같은 base로 시작하는 파일 찾기
   ```python
   for file in os.listdir(base_dir):
       if file.startswith(base_filename):
           # .nii.gz와 .json 제외
           if not (file.endswith('.nii.gz') or file.endswith('.json')):
               suffix = Path(file).suffix.lstrip('.')
               byproduct_files[suffix] = file_path
   ```

3. 확장자별로 분류

**부산물 파일 종류**:
- `.bval`: DWI b-value (확산강조영상)
- `.bvec`: DWI b-vector (확산강조영상)
- `.tsv`: 이벤트 파일 (fMRI)
- 기타 dcm2niix가 생성한 파일들

**반환 구조**:
```python
{
    '/raw/.../sub-xxx_ses-01_run-01_dwi.nii.gz': {
        'bval': '/raw/.../sub-xxx_ses-01_run-01_dwi.bval',
        'bvec': '/raw/.../sub-xxx_ses-01_run-01_dwi.bvec'
    },
    '/raw/.../sub-xxx_ses-01_task-rest_run-01_bold.nii.gz': {
        'tsv': '/raw/.../sub-xxx_ses-01_task-rest_run-01_events.tsv'
    }
}
```

### 3-3. Thumbnail Generator

**파일**: `thumbnail.py`

```python
def thumbnail(raw_path):
    """raw_path 딕셔너리를 받아서 각 nii.gz 파일의 썸네일을 생성"""
```

**썸네일 생성 과정**:

#### 1. NIfTI 데이터 로드

```python
img_data = nib.load(nii_path).get_fdata()

# 4D 데이터면 첫 번째 볼륨 선택
if len(img_data.shape) > 3:
    img_data = img_data[:,:,:,1]
```

#### 2. 3방향 중간 슬라이스 추출

```python
# Axial (횡단면) - z축 중간
img1 = img_data[:, :, int(img_data.shape[2]/2)]

# Coronal (관상면) - y축 중간
img2 = img_data[:, int(img_data.shape[1]/2), :]

# Sagittal (시상면) - x축 중간
img3 = img_data[int(img_data.shape[0]/2), :, :]
```

**시각화**:
```
┌─────────┐
│ Axial   │ 144x144
├─────────┤
│ Coronal │ 144x144
├─────────┤
│Sagittal │ 144x144
└─────────┘
   144x432
```

#### 3. 이미지 전처리

```python
# 각 이미지를 144x144로 리사이즈
img1 = cv2.resize(img1, (144, 144))
img2 = cv2.resize(img2, (144, 144))
img3 = cv2.resize(img3, (144, 144))

# 세로로 연결
timg = np.concatenate((img1, img2, img3), axis=0)

# 전치 및 뒤집기
timg = np.transpose(timg)
timg = timg[::-1]

# 0-255 정규화
timg = timg / float(np.max(timg)) * 255
```

#### 4. CLAHE 적용

Contrast Limited Adaptive Histogram Equalization:
```python
clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
timg = clahe.apply(timg.astype('uint8'))
```

**효과**: 국소 대비 향상으로 세부 구조 강조

#### 5. PNG 저장

```python
thumbnail_filename = nifti_path.stem.replace('.nii', '') + '.png'
thumb_path = os.path.join(thumbnail_dir, thumbnail_filename)
cv2.imwrite(thumb_path, timg)
```

**저장 위치**: NIfTI 파일과 같은 디렉토리

**반환 구조**:
```python
{
    '/raw/.../sub-xxx_ses-01_run-01_T1w.nii.gz': '/raw/.../sub-xxx_ses-01_run-01_T1w.png',
    '/raw/.../sub-xxx_ses-01_run-02_T2w.nii.gz': '/raw/.../sub-xxx_ses-01_run-02_T2w.png'
}
```

---

## 데이터 구조

### 최종 통합 결과

**위치**: `main.py:272-287`

모든 후처리 결과를 하나의 `bids_checklist`로 통합:

```python
bids_checklist = {}

for nifti_key in bids_checklist.keys():
    # 1. BIDS Checker 기본 정보
    bids_checklist[nifti_key] = {
        'nifti_exists': True,
        'sidecar_json': '/path/to/file.json',
        'bids_guess': 'T1w',
        'data_type': 'anat',
        'modality': 'T1w',
        'folder_structure_valid': True,
        'warnings': []
    }

    # 2. Byproduct 추가
    if nifti_key in byproduct_path:
        bids_checklist[nifti_key]['byproduct'] = byproduct_path[nifti_key]

    # 3. Thumbnail 추가
    if nifti_key in thumbnail_path:
        bids_checklist[nifti_key]['thumbnail'] = thumbnail_path[nifti_key]

    # 4. Source 매핑 추가
    if nifti_key in raw_to_source:
        bids_checklist[nifti_key]['source'] = raw_to_source[nifti_key]
```

**완전한 예시**:

```python
{
    '/raw/sub-21CNA000011/ses-01/anat/sub-21CNA000011_ses-01_run-01_T1w.nii.gz': {
        # BIDS Checker
        'nifti_exists': True,
        'sidecar_json': '/raw/.../sub-21CNA000011_ses-01_run-01_T1w.json',
        'bids_guess': 'T1w',
        'data_type': 'anat',
        'modality': 'T1w',
        'folder_structure_valid': True,
        'warnings': [],

        # Byproduct (없음)

        # Thumbnail
        'thumbnail': '/raw/.../sub-21CNA000011_ses-01_run-01_T1w.png',

        # Source 역매핑
        'source': '/source/.../DICOM/valid_data/set-abc123'
    },

    '/raw/sub-21CNA000011/ses-01/dwi/sub-21CNA000011_ses-01_run-01_dwi.nii.gz': {
        'nifti_exists': True,
        'sidecar_json': '/raw/.../sub-21CNA000011_ses-01_run-01_dwi.json',
        'bids_guess': 'dwi',
        'data_type': 'dwi',
        'modality': 'dwi',
        'folder_structure_valid': True,
        'warnings': [],

        # Byproduct (DWI 특수 파일)
        'byproduct': {
            'bval': '/raw/.../sub-21CNA000011_ses-01_run-01_dwi.bval',
            'bvec': '/raw/.../sub-21CNA000011_ses-01_run-01_dwi.bvec'
        },

        # Thumbnail
        'thumbnail': '/raw/.../sub-21CNA000011_ses-01_run-01_dwi.png',

        # Source
        'source': '/source/.../DICOM/valid_data/set-def456'
    }
}
```

### Source → Raw 역매핑

```python
# raw_path: {source_path: raw_nifti_path}
# 이를 뒤집어서 raw → source 매핑 생성
raw_to_source = {}
for source_key, raw_key in raw_path.items():
    raw_to_source[raw_key] = source_key
```

**목적**: 최종 BIDS 파일이 어떤 원본 세트에서 왔는지 추적

---

## 클래스 및 모듈

### Source 모듈

| 파일 | 클래스/함수 | 설명 |
|------|------------|------|
| `source.py` | `create_source_path()` | Source 경로 생성 메인 함수 |
| | `get_file_format()` | bdsp_file_list.json에서 포맷 감지 |
| | `copy_files_to_invalid()` | 원본 파일을 invalid_data로 복사 |
| | `make_participants_file()` | participants.tsv/json 생성 |
| `validator.py` | `DicomValidator` | DICOM 파일 유효성 검사 |
| | `ParrecValidator` | PAR/REC 파일 유효성 검사 |
| | `NiftiValidator` | NIfTI 파일 무결성 검사 |
| | `validate_parrec_files()` | PAR/REC 최소 검증 |
| | `validate_nifti_file()` | NIfTI 상세 검증 |
| `separator.py` | `PreWork` | Separator 공통 부모 클래스 |
| | `DicomSeparator` | DICOM 파일 재명명 |
| | `ParrecSeparator` | PAR/REC 파일 재명명 |
| | `NiftiSeparator` | NIfTI 파일 재명명 |

### Raw 모듈

| 파일 | 클래스/함수 | 설명 |
|------|------------|------|
| `raw.py` | `create_raw_path()` | Raw 데이터 생성 메인 함수 |
| `modality_mapper.py` | `DicomMapper` | DICOM 메타데이터 → 모달리티 |
| | `ParrecMapper` | PAR 헤더 → 모달리티 |
| | `NiftiMapper` | 파일명 → 모달리티 |
| `name_builder.py` | `create_bids_mapping()` | BIDS 파일명 매핑 생성 |
| | `build_bids_filename()` | BIDS 파일명 구성 |
| | `get_base_run_number()` | 기존 run 번호 확인 |
| | `find_data_type()` | 모달리티 → data_type |
| | `get_phase_encoding_direction()` | dir entity 값 추출 |
| `dcm2nii_parser.py` | `process_bids_conversion()` | 변환 오케스트레이터 |
| | `run_dcm2niix()` | dcm2niix 실행 |
| | `process_nifti_files()` | NIfTI 직접 처리 |
| | `_resolve_actual_output()` | %-포맷 결과 파일 찾기 |
| | `clean_filename()` | % entity 제거 |

### Post 모듈

| 파일 | 클래스/함수 | 설명 |
|------|------------|------|
| `bids_checker.py` | `check_modality()` | BIDS 규격 검증 메인 함수 |
| | `_extract_data_type_and_modality()` | 경로/파일명에서 추출 |
| | `_validate_folder_structure()` | 폴더 구조 검증 |
| | `_log_validation_summary()` | 검증 결과 요약 |
| `byproduct.py` | `check_byproduct()` | 부산물 파일 수집 |
| `thumbnail.py` | `thumbnail()` | 썸네일 생성 메인 함수 |
| | `create_thumbnail()` | 개별 파일 썸네일 생성 |

---

## 설정 파일

### 1. Modality Mapping JSON

**DICOM**: `{dicom_modality}/{systemId}_{projectCode}_{projectSeq}_{orgId}_dicom_modality.json`

```json
{
  "T1w": [
    {
      "SeriesDescription": ["t1_mprage_sag", "T1 MPRAGE"],
      "SequenceName": ["*tfl3d1_16ns"]
    }
  ],
  "T2w": [
    {
      "SeriesDescription": ["t2_tse_sag"],
      "EchoTime": ["0.1"]
    }
  ],
  "FLAIR": [
    {
      "SeriesDescription": ["t2_flair"],
      "InversionTime": ["2.5"]
    }
  ],
  "bold": [
    {
      "SeriesDescription": ["fMRI_rest", "BOLD_rest"],
      "SequenceName": ["*epfid2d"]
    }
  ],
  "dwi": [
    {
      "SeriesDescription": ["ep2d_diff"],
      "ImageType": ["DIFFUSION"]
    }
  ]
}
```

**PARREC**: `{parrec_modality}/{systemId}_{projectCode}_{projectSeq}_{orgId}_parrec_modality.json`

```json
{
  "T1w": [
    {
      "Technique": ["FFE"],
      "ScanningSequence": ["GR"]
    }
  ]
}
```

### 2. Suffix Map JSON

**위치**: `{suffix_map}/suffix.json`

```json
{
  "anat": {
    "T1w": {
      "required": ["sub", "ses"],
      "optional": ["acq", "run"]
    },
    "T2w": {
      "required": ["sub", "ses"],
      "optional": ["acq", "run"]
    },
    "FLAIR": {
      "required": ["sub", "ses"],
      "optional": ["acq", "run"]
    }
  },
  "func": {
    "bold": {
      "required": ["sub", "ses", "task"],
      "optional": ["acq", "dir", "run"]
    }
  },
  "dwi": {
    "dwi": {
      "required": ["sub", "ses"],
      "optional": ["acq", "dir", "run"]
    }
  },
  "fmap": {
    "epi": {
      "required": ["sub", "ses"],
      "optional": ["acq", "dir", "run"]
    }
  }
}
```

---

## 에러 처리

### 일반적인 에러 케이스

1. **포맷 감지 실패**
   ```python
   if file_format == "UNKNOWN":
       raise ValueError("포맷을 판별할 수 없어 파이프라인을 진행할 수 없습니다.")
   ```

2. **유효성 검사 실패**
   ```python
   if vr is None:
       raise Exception("유효성 검사 실패 또는 유효 파일 없음")
   ```

3. **모달리티 없음**
   ```python
   if len(modalities) > 1:
       raise ValueError(f"Multiple modalities found in {set_path}: {modalities}")
   ```

4. **Task 필수인데 없음**
   ```python
   if 'task' in entity_rules:
       if not task_info['isFunc']:
           raise ValueError("Task entity required but isFunc=False")
   ```

5. **NIfTI 파일 개수 오류**
   ```python
   if len(file_list) > 1:
       raise RuntimeError(f"NIfTI는 파일이 1개만 있어야 합니다")
   ```

6. **dcm2niix 실행 실패**
   ```python
   except subprocess.CalledProcessError as e:
       logger.error("dcm2niix failed: %s", e.stderr)
       raise ValueError(f"dcm2niix conversion failed: {e.stderr}")
   ```

---

## 성능 최적화

### 1. 병렬 처리 가능 지점

- **Source**: 여러 세트를 동시에 validation/separation
- **Raw**: 여러 소스를 동시에 변환 (dcm2niix는 독립적)
- **Post**: 여러 파일을 동시에 썸네일 생성

### 2. 캐싱

- **bdsp_file_list.json**: 파일 목록을 미리 스캔하여 반복 접근 최소화
- **Modality mapping**: 프로젝트별로 한 번만 로드

### 3. 메모리 관리

- **DICOM**: `stop_before_pixels=True`로 픽셀 데이터 제외
- **NIfTI**: 썸네일 생성 시 중간 슬라이스만 로드

---

**Last Updated**: 2026-01-02
