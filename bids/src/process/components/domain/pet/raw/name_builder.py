import json
import os
import glob
import logging
from utils.common import zero_fill

logger = logging.getLogger(__name__)

def create_bids_mapping(path_mapping, structured_config, global_vars, raw_path, alias_id):
    """
    PET 소스 데이터 경로를 BIDS 형식 경로로 매핑하는 함수

    Args:
        path_mapping (dict): 소스 폴더 경로와 tracer 매핑
        structured_config (dict): 프로젝트 설정 정보
        global_vars (dict): 전역 변수 (suffix_map 경로 포함)
        raw_path (str): BIDS rawdata 기본 경로
        alias_id (str): Subject alias ID

    Returns:
        dict: 소스 폴더 경로와 BIDS 형식 파일 경로 매핑
    """

    # 1. suffix_map JSON 파일 로드
    try:
        with open(global_vars['suffix_map'], 'r') as f:
            suffix_rules = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.error(f"Failed to load suffix_map: {e}")
        raise

    # 2. 기본 정보 추출
    request_info = structured_config['request']
    subject_id = request_info['subjectId']
    trial_index = zero_fill(request_info['trialIndex'])

    # 3. 결과 매핑 딕셔너리
    bids_mapping = {}

    # 4. PET은 data_type='pet', suffix='pet' 고정
    data_type = 'pet'
    suffix = 'pet'

    # 5. suffix_map에서 PET 규칙 확인
    if data_type not in suffix_rules or suffix not in suffix_rules[data_type]:
        logger.error(f"PET suffix rule not found in suffix_map")
        raise ValueError(f"PET suffix rule not found in suffix_map")

    entity_rules = suffix_rules[data_type][suffix]

    # 6. tracer별 run 카운터 초기화 (중복 방지용)
    tracer_run_counter = {}

    # 7. 각 소스 폴더에 대해 BIDS 파일명 생성
    for source_folder, tracer in path_mapping.items():

        # tracer별 키 생성 (같은 subject, session, tracer 조합)
        tracer_key = f"{subject_id}_{trial_index}_{tracer}"

        # 기존 run 번호 확인 (해당 tracer 키가 처음 등장할 때만)
        if tracer_key not in tracer_run_counter:
            base_run = get_base_run_number(
                tracer,
                alias_id,
                trial_index,
                raw_path,
                data_type
            )
            tracer_run_counter[tracer_key] = base_run
            logger.info(f"Initialized run counter for {tracer_key}: starting from {base_run}")

        # 현재 run 번호 사용
        current_run = tracer_run_counter[tracer_key]
        current_run_str = zero_fill(current_run)

        logger.info(f"Assigning run-{current_run_str} to tracer {tracer} at {source_folder}")

        # BIDS 파일명 생성 (run 번호 직접 전달)
        bids_filename = build_bids_filename(
            tracer,
            entity_rules,
            alias_id,
            trial_index,
            run_number=current_run_str
        )

        # 다음 run 번호로 증가
        tracer_run_counter[tracer_key] += 1

        # 최종 BIDS 경로 생성
        bids_path = os.path.join(
            raw_path,
            f"{alias_id}",
            f"ses-{trial_index}",
            data_type,
            bids_filename
        )

        bids_mapping[source_folder] = bids_path

    return bids_mapping


def get_base_run_number(tracer, alias_id, trial_index, raw_path, data_type):
    """
    기존 파일들을 확인하여 시작 run 번호를 결정
    이미 파일이 있으면 max(run) + 1, 없으면 1부터 시작
    """
    # 대상 폴더 경로
    target_dir = os.path.join(
        raw_path,
        f"{alias_id}",
        f"ses-{trial_index}",
        data_type
    )

    # 폴더가 존재하지 않으면 run-01부터 시작
    if not os.path.exists(target_dir):
        logger.debug(f"Directory not found: {target_dir}, starting from run-01")
        return 1

    # 해당 tracer의 기존 파일들 찾기
    # 패턴: sub-*_ses-*_trc-{tracer}_*_pet.nii.gz
    pattern = os.path.join(target_dir, f"*_trc-{tracer}_*_pet.nii.gz")
    existing_files = glob.glob(pattern)

    if not existing_files:
        logger.debug(f"No existing {tracer} files found, starting from run-01")
        return 1

    # run 번호 추출
    run_numbers = []
    for file_path in existing_files:
        filename = os.path.basename(file_path)
        # run-XX 패턴 찾기
        parts = filename.split('_')
        for part in parts:
            if part.startswith('run-'):
                try:
                    run_num = int(part.split('-')[1])
                    run_numbers.append(run_num)
                    break
                except (ValueError, IndexError):
                    continue

    # 다음 run 번호 계산
    if run_numbers:
        next_run = max(run_numbers) + 1
        logger.debug(f"Found existing runs: {run_numbers}, next run: {next_run}")
        return next_run
    else:
        logger.debug(f"No valid run numbers found, starting from run-01")
        return 1


def build_bids_filename(tracer, entity_rules, alias_id, trial_index, run_number=None):
    """
    PET BIDS 파일명 생성

    Args:
        tracer: Tracer 값 (예: 18FFDG, 11CPIB)
        entity_rules: BIDS 엔티티 규칙
        alias_id: Subject alias ID
        trial_index: 세션 번호
        run_number: run 번호 (외부에서 전달, 없으면 계산하지 않음)

    Returns:
        str: BIDS 파일명 (예: sub-xxx_ses-01_trc-18FFDG_run-01_pet.nii.gz)
    """
    tracer = str(tracer).strip()

    # 기본 엔티티들
    entities = []

    # 1. subject (무조건 포함)
    entities.append(f"{alias_id}")

    # 2. session (무조건 포함)
    entities.append(f"ses-{trial_index}")

    # 3. trc (tracer, 무조건 포함)
    entities.append(f"trc-{tracer}")

    # 4. acq (해당하는 경우만)
    if 'acq' in entity_rules:
        entities.append("acq-%u")

    # 5. rec는 사용하지 않음 (optional이므로 생략)

    # 6. run (외부에서 전달받은 번호 사용)
    if run_number is None:
        logger.warning(f"run_number not provided for tracer {tracer}, using '01' as default")
        run_number = "01"
    entities.append(f"run-{run_number}")

    # 7. suffix (항상 'pet')
    entities.append('pet')

    # 최종 파일명 생성 (확장자는 .nii.gz로 가정)
    filename = "_".join(entities) + ".nii.gz"

    return filename
