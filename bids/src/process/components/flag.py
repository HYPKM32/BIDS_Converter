import json
import logging
import os
import re
import shutil
import time
from pathlib import Path

logger = logging.getLogger(__name__)

def extract_bids_info(filepath):
    """BIDS 파일 경로에서 필요한 정보 추출
    
    Args:
        filepath: 파일 전체 경로
        
    Returns:
        dict: {
            'basename': 파일명,
            'run_num': run 번호,
            'alias_id': subject ID,
            'ses_num': session 번호,
            'data_type': 데이터 타입 (anat, func 등)
        }
    """
    path_obj = Path(filepath)
    basename = path_obj.name
    data_type = path_obj.parent.name
    
    # 정규표현식으로 한 번에 추출
    run_match = re.search(r'run-(\d+)_', basename)
    sub_match = re.search(r'sub-([^_]+)_', basename)
    ses_match = re.search(r'ses-([^_]+)_', basename)
    
    return {
        'basename': basename,
        'run_num': run_match.group(1) if run_match else None,
        'alias_id': sub_match.group(1) if sub_match else None,
        'ses_num': ses_match.group(1) if ses_match else None,
        'data_type': data_type
    }


def get_next_exe_num(derivatives_run_path):
    """derivatives_run_path에서 다음 exe 번호 결정
    
    Args:
        derivatives_run_path: derivatives run 경로
        
    Returns:
        str: 2자리 제로필링된 exe 번호
    """
    path_obj = Path(derivatives_run_path)
    
    if not path_obj.exists():
        return "01"
    
    # exe-* 폴더 찾기
    exe_folders = list(path_obj.glob("exe-*"))
    
    if not exe_folders:
        return "01"
    
    # 숫자 추출 및 최댓값 찾기
    exe_nums = []
    for folder in exe_folders:
        match = re.search(r'exe-(\d+)', folder.name)
        if match:
            exe_nums.append(int(match.group(1)))
    
    if not exe_nums:
        return "01"
    
    next_num = max(exe_nums) + 1
    return f"{next_num:02d}"


def get_input_paths_from_bids(modality_condition, export_list):
    """process가 'bids'인 경우 export data에서 input 경로 가져오기
    
    Args:
        modality_condition: modality 조건 객체
        export_list: export.data 리스트
        
    Returns:
        list: 매칭된 경로 리스트
    """
    package = modality_condition.get('package')  # 'raw', 'source', 'sidecar' 등
    modality_list = modality_condition.get('modality', [])
    
    matched_paths = []
    
    for data in export_list:
        data_modality = data.get('modality')
        
        # modality가 조건 리스트에 있는지 확인
        if data_modality in modality_list:
            # package 키에 해당하는 경로 가져오기
            path = data.get(package)
            
            if path:
                matched_paths.append(path)
                logger.debug(f"BIDS 매칭: {data_modality} -> {package}: {path}")
    
    return matched_paths


def get_input_paths_from_derivatives(modality_condition, flag_list):
    """process가 'bids'가 아닌 경우 이전 프로세스의 outputs에서 input 경로 가져오기
    
    Args:
        modality_condition: modality 조건 객체
        flag_list: 전체 flag 리스트
        
    Returns:
        list: 매칭된 경로 리스트
    """
    target_process = modality_condition.get('process')
    target_package = modality_condition.get('package')
    modality_list = modality_condition.get('modality', [])
    
    matched_paths = []
    
    # flag_list에서 해당 process와 package를 가진 프로세스 찾기
    for flag in flag_list:
        if flag.get('process') == target_process and flag.get('package') == target_package:
            # derived_data에서 outputs 확인
            for derived in flag.get('derived_data', []):
                outputs = derived.get('outputs', {})
                
                # modality_list에 있는 키의 값을 가져오기
                for modality_key in modality_list:
                    if modality_key in outputs:
                        path = outputs[modality_key]
                        matched_paths.append(path)
                        logger.debug(f"Derivatives 매칭: {target_process}/{target_package} -> {modality_key}: {path}")
            
            break  # 해당 프로세스를 찾았으므로 종료
    
    return matched_paths


def get_input_paths(modality_conditions, export_list, flag_list):
    """modality_condition에 따라 input 경로 가져오기
    
    Args:
        modality_conditions: modality 조건 리스트 (단일 객체 또는 리스트)
        export_list: export.data 리스트
        flag_list: 전체 flag 리스트
        
    Returns:
        list: 매칭된 경로 리스트
    """
    # modality_conditions가 단일 객체인 경우 리스트로 변환
    if isinstance(modality_conditions, dict):
        modality_conditions = [modality_conditions]
    
    all_paths = []
    
    for condition in modality_conditions:
        process = condition.get('process')
        
        if process == 'bids':
            # export.data에서 가져오기
            paths = get_input_paths_from_bids(condition, export_list)
            all_paths.extend(paths)
        else:
            # 이전 프로세스의 outputs에서 가져오기
            paths = get_input_paths_from_derivatives(condition, flag_list)
            all_paths.extend(paths)
    
    return all_paths


def prepare_process_data(flag, export_list, flag_list, derivatives_path):
    """프로세스의 input/output 경로를 준비
    
    Args:
        flag: 처리할 flag 객체
        export_list: export.data 리스트
        flag_list: 전체 flag 리스트
        derivatives_path: derivatives 기본 경로
        
    Returns:
        int: 매칭된 데이터 개수
    """
    modality_conditions = flag.get('modality_condition', [])
    process_name = flag.get('process')
    space = flag.get('space')
    package = flag.get('package')
    
    print(f"\n프로세스 '{process_name}' 입력 데이터 매칭 및 경로 생성 중...")
    print(f"  매칭 조건: {modality_conditions}")
    
    # modality_condition에 따라 input 경로 가져오기
    input_paths = get_input_paths(modality_conditions, export_list, flag_list)
    
    if not input_paths:
        logger.warning(f"프로세스 '{process_name}'에 매칭되는 데이터가 없음")
        print(f"WARNING: '{process_name}' 프로세스에 처리할 데이터가 없습니다")
        return 0
    
    matched_count = 0
    
    for input_path in input_paths:
        try:
            # BIDS 정보 추출
            bids_info = extract_bids_info(input_path)
            
            if not all([bids_info['run_num'], bids_info['alias_id'], 
                       bids_info['ses_num'], bids_info['data_type']]):
                logger.warning(f"BIDS 정보 추출 실패: {input_path}")
                continue
            
            # 폴더명 생성
            subject_folder = f"sub-{bids_info['alias_id']}"
            ses_folder = f"ses-{bids_info['ses_num']}"
            run_folder = f"run-{bids_info['run_num']}"
            
            # derivatives_run_path 생성
            derivatives_run_path = (derivatives_path / process_name / space / 
                                   package / subject_folder / ses_folder / run_folder)
            
            # exe_num 결정
            exe_num = get_next_exe_num(derivatives_run_path)
            exe_folder = f"exe-{exe_num}"
            
            # 최종 출력 경로 생성
            derived_output_folder_path = derivatives_run_path / exe_folder / bids_info['data_type']
            
            # 경로 생성
            os.makedirs(derived_output_folder_path, exist_ok=True)
            logger.debug(f"출력 경로 생성: {derived_output_folder_path}")
            
            # derived_data에 추가
            flag['derived_data'].append({
                'input': input_path,
                'output_path': str(derived_output_folder_path),
                'run_num': bids_info['run_num'],
                'exe_num': exe_num
            })
            
            matched_count += 1
            logger.info(f"매칭 성공: {input_path} -> run:{bids_info['run_num']}, exe:{exe_num}")
            
        except Exception as e:
            logger.error(f"경로 생성 오류 ({input_path}): {e}")
            continue
    
    print(f"  매칭 및 경로 생성 완료: {matched_count}개 데이터\n")
    logger.info(f"프로세스 '{process_name}'에 {matched_count}개 입력 데이터 할당 완료")
    
    return matched_count


def wait_for_process_completion(json_file_path, process_name, timeout=3600, check_interval=5):
    """프로세스 완료를 기다림
    
    Args:
        json_file_path: 모니터링할 JSON 파일 경로
        process_name: 프로세스 이름
        timeout: 최대 대기 시간 (초)
        check_interval: 체크 간격 (초)
        
    Returns:
        dict: 완료된 JSON 데이터, 실패 시 None
    """
    print(f"\n'{process_name}' 프로세스 완료 대기 중...")
    print(f"  모니터링 파일: {json_file_path}")
    
    elapsed_time = 0
    
    while elapsed_time < timeout:
        try:
            # 파일이 존재하는지 확인
            if not Path(json_file_path).exists():
                logger.debug(f"파일 대기 중: {json_file_path}")
                time.sleep(check_interval)
                elapsed_time += check_interval
                continue
            
            # JSON 파일 읽기
            with open(json_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # flag 리스트에서 해당 프로세스 찾기
            flag_list = data.get('flag', [])
            
            for flag in flag_list:
                if flag.get('process') == process_name:
                    status = flag.get('status')
                    
                    if status == 'done':
                        print(f"  ✓ 프로세스 완료 확인!")
                        logger.info(f"프로세스 '{process_name}' 완료")
                        return data
                    else:
                        logger.debug(f"프로세스 '{process_name}' 상태: {status}")
            
            # 아직 완료되지 않음
            time.sleep(check_interval)
            elapsed_time += check_interval
            
            # 진행 상황 출력 (30초마다)
            if elapsed_time % 30 == 0:
                print(f"  대기 중... ({elapsed_time}초 경과)")
        
        except json.JSONDecodeError as e:
            logger.warning(f"JSON 파싱 오류 (재시도): {e}")
            time.sleep(check_interval)
            elapsed_time += check_interval
        except Exception as e:
            logger.error(f"파일 읽기 오류: {e}")
            time.sleep(check_interval)
            elapsed_time += check_interval
    
    # 타임아웃
    logger.error(f"프로세스 '{process_name}' 타임아웃 ({timeout}초)")
    print(f"  ✗ 타임아웃: 프로세스가 {timeout}초 내에 완료되지 않았습니다")
    return None


def process_flags(flag_list, global_vars, export_json_path):
    """Flag 처리 메인 함수"""
    
    # 1. flag_list가 비어있으면 None 반환
    if not flag_list or len(flag_list) == 0:
        logger.info("Flag 리스트가 비어있음")
        print("Flag 없음 - 전처리 건너뛰기")
        return None
    
    # 2. enabled=False인 프로세스 삭제
    flag_list = [flag for flag in flag_list if flag.get('enabled', False)]
    logger.info(f"enabled=True인 flag만 필터링 완료: {len(flag_list)}개")
    
    # 3. 모든 프로세스의 enabled가 False라면 None 반환
    if len(flag_list) == 0:
        logger.info("활성화된 Flag가 없음")
        print("활성화된 Flag 없음 - 전처리 건너뛰기")
        return None
    
    # 4. flag가 있으면 플랜 출력
    print(f"\n{'='*60}")
    print(f"전처리 파이프라인 시작")
    print(f"{'='*60}")
    print(f"\n전처리 Flag 발견: {len(flag_list)}개")
    print("전처리 실행 플랜:")
    
    for idx, flag in enumerate(flag_list, 1):
        print(f"  {idx}. {flag.get('process')} - {flag.get('package')} (enabled: {flag.get('enabled')})")
    
    # 5. 각 프로세스에 derived_data 키 생성하고 빈 배열 할당
    for flag in flag_list:
        if 'derived_data' not in flag:
            flag['derived_data'] = []
            logger.debug(f"프로세스 '{flag.get('process')}'에 derived_data 초기화")
    
    # 6. export_json_path 파일 읽기
    print("\n처리 대상 데이터 분석 중...")
    try:
        with open(export_json_path, 'r', encoding='utf-8') as f:
            export_data = json.load(f)
        
        logger.info(f"export JSON 파일 로드 완료: {export_json_path}")
        
    except FileNotFoundError:
        logger.error(f"export JSON 파일을 찾을 수 없음: {export_json_path}")
        print(f"ERROR: 파일을 찾을 수 없습니다: {export_json_path}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"JSON 파싱 오류: {e}")
        print(f"ERROR: JSON 파일 형식이 올바르지 않습니다")
        return None
    except Exception as e:
        logger.error(f"예상치 못한 오류: {e}")
        print(f"ERROR: {e}")
        return None
    
    # 7. export 객체에서 mss와 data 가져오기
    export_obj = export_data.get('export', {})
    if not export_obj:
        logger.error("export 객체를 찾을 수 없음")
        print("ERROR: export 데이터가 없습니다")
        return None
    
    mss_path = export_obj.get('mss')
    if not mss_path:
        logger.error("mss 경로를 찾을 수 없음")
        print("ERROR: mss 경로가 없습니다")
        return None
    
    export_list = export_obj.get('data', [])
    if not export_list:
        logger.error("export data 리스트가 비어있음")
        print("ERROR: 처리할 데이터가 없습니다")
        return None
    
    logger.info(f"export 데이터 로드 완료: {len(export_list)}개 항목")
    print(f"분석 완료: {len(export_list)}개 데이터 발견")
    
    derivatives_path = Path(mss_path) / 'derivatives'
    logger.info(f"derivatives 경로: {derivatives_path}")
    
    flag_dir = global_vars.get('flag_dir')
    if not flag_dir:
        logger.error("flag_dir를 찾을 수 없음")
        print("ERROR: flag_dir 경로가 없습니다")
        return None
    
    # 8. 각 프로세스를 순차적으로 처리
    current_json_data = export_data
    current_json_path = export_json_path
    
    for idx, flag in enumerate(flag_list):
        process_name = flag.get('process')
        package = flag.get('package')
        
        print(f"\n{'='*60}")
        print(f"[{idx + 1}/{len(flag_list)}] 프로세스: {process_name} ({package})")
        print(f"{'='*60}")
        
        # 8-1. ready 상태 설정
        flag['ready'] = True
        logger.info(f"프로세스 '{process_name}' ready 상태로 변경")
        
        # 8-2. 현재 flag_list를 JSON에 업데이트
        current_json_data['flag'] = flag_list
        
        # 8-3. input/output 경로 준비
        matched_count = prepare_process_data(
            flag, 
            export_list, 
            flag_list, 
            derivatives_path
        )
        
        if matched_count == 0:
            logger.warning(f"프로세스 '{process_name}'에 처리할 데이터가 없음 - 건너뛰기")
            print(f"WARNING: '{process_name}' 프로세스에 처리할 데이터가 없습니다 - 건너뛰기")
            continue
        
        # 8-4. JSON 파일 업데이트 및 저장
        print(f"\nJSON 파일 업데이트 중...")
        current_json_data['flag'] = flag_list
        
        try:
            with open(current_json_path, 'w', encoding='utf-8') as f:
                json.dump(current_json_data, f, ensure_ascii=False, indent=2)
            logger.info(f"JSON 파일 업데이트 완료: {current_json_path}")
            print(f"  업데이트 완료: {current_json_path}")
        except Exception as e:
            logger.error(f"JSON 파일 저장 오류: {e}")
            print(f"ERROR: JSON 파일 저장 실패: {e}")
            return None
        
        # 8-5. flag 디렉토리로 이동 (이벤팅)
        flag_event_path = Path(flag_dir) / process_name / package
        
        try:
            # 프로세스 이벤트 경로 생성
            os.makedirs(flag_event_path, exist_ok=True)
            
            # 파일명 추출 및 이동
            json_filename = Path(current_json_path).name
            destination_path = flag_event_path / json_filename
            
            shutil.move(current_json_path, destination_path)
            logger.info(f"JSON 파일 이벤팅: {destination_path}")
            print(f"\n이벤팅 완료: {destination_path}")
            
            # 다음 프로세스를 위해 현재 경로 업데이트
            current_json_path = str(destination_path)
            
        except Exception as e:
            logger.error(f"JSON 파일 이동 오류: {e}")
            print(f"ERROR: 파일 이동 실패: {e}")
            return None
        
        # 8-6. 프로세스 완료 대기
        completed_data = wait_for_process_completion(
            current_json_path, 
            process_name,
            timeout=86400,  # 24시간
            check_interval=5  # 5초마다 체크
        )
        
        if completed_data is None:
            logger.error(f"프로세스 '{process_name}' 완료 실패")
            print(f"\nERROR: 프로세스 '{process_name}'이(가) 완료되지 않았습니다")
            return None
        
        # 완료된 데이터로 업데이트
        current_json_data = completed_data
        flag_list = completed_data.get('flag', [])
        
        # 8-7. 다음 프로세스로 파일 이동 또는 working_dir로 이동
        if idx < len(flag_list) - 1:
            # 다음 프로세스가 있는 경우
            next_flag = flag_list[idx + 1]
            next_process_name = next_flag.get('process')
            next_package = next_flag.get('package')
            
            print(f"\n다음 프로세스 '{next_process_name}'로 파일 이동 중...")
            
            next_flag_event_path = Path(flag_dir) / next_process_name / next_package
            
            try:
                # 다음 프로세스 이벤트 경로 생성
                os.makedirs(next_flag_event_path, exist_ok=True)
                
                # 파일명 유지하고 이동
                json_filename = Path(current_json_path).name
                next_destination_path = next_flag_event_path / json_filename
                
                shutil.move(current_json_path, next_destination_path)
                logger.info(f"다음 프로세스로 이동: {next_destination_path}")
                print(f"  이동 완료: {next_destination_path}")
                
                # 다음 프로세스를 위해 현재 경로 업데이트
                current_json_path = str(next_destination_path)
                
            except Exception as e:
                logger.error(f"다음 프로세스로 파일 이동 오류: {e}")
                print(f"ERROR: 파일 이동 실패: {e}")
                return None
            
            print(f"\n다음 프로세스로 진행...")
        else:
            # 마지막 프로세스 완료 - working_dir로 이동
            print(f"\n마지막 프로세스 완료 - working_dir로 최종 이동 중...")
            
            working_dir = global_vars.get('working_dir')
            if not working_dir:
                logger.error("working_dir를 찾을 수 없음")
                print("ERROR: working_dir 경로가 없습니다")
                return None
            
            try:
                # working_dir 생성
                os.makedirs(working_dir, exist_ok=True)
                
                # 파일명 유지하고 최종 이동
                json_filename = Path(current_json_path).name
                final_destination_path = Path(working_dir) / json_filename
                
                shutil.move(current_json_path, final_destination_path)
                logger.info(f"최종 파일 이동: {final_destination_path}")
                print(f"  최종 이동 완료: {final_destination_path}")
                
                # 최종 경로 업데이트
                current_json_path = str(final_destination_path)
                
            except Exception as e:
                logger.error(f"working_dir로 파일 이동 오류: {e}")
                print(f"ERROR: 최종 파일 이동 실패: {e}")
                return None
    
    print(f"\n{'='*60}")
    print(f"전처리 파이프라인 완료!")
    print(f"{'='*60}\n")
    logger.info("모든 프로세스 처리 완료")
    
    return current_json_data