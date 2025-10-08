#/BDSP/bids_app/src/process/components/flag.py

import json
import logging
import os
import re
import shutil
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
    print(f"\n전처리 Flag 발견: {len(flag_list)}개")
    print("전처리 실행 플랜:")
    
    for idx, flag in enumerate(flag_list, 1):
        print(f"  {idx}. {flag.get('process')} - {flag.get('package')} (enabled: {flag.get('enabled')})")
    
    # 5. 첫 번째 프로세스의 ready 상태를 True로 변경
    flag_list[0]['ready'] = True
    logger.info(f"첫 번째 프로세스 '{flag_list[0].get('process')}' ready 상태로 변경")
    
    # 6. 각 프로세스에 derived_data 키 생성하고 빈 배열 할당
    for flag in flag_list:
        flag['derived_data'] = []
        logger.debug(f"프로세스 '{flag.get('process')}'에 derived_data 초기화")
    
    # 7. export_json_path 파일 읽기
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
    
    # 8. export 객체에서 mss와 data 가져오기
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
    
    # 9. 첫 번째 프로세스에 대해 modality 매칭 및 입력 데이터 준비
    first_flag = flag_list[0]
    modality_condition = first_flag.get('modality_condition', [])
    process_name = first_flag.get('process')
    space = first_flag.get('space')
    package = first_flag.get('package')
    
    matched_count = 0
    
    print(f"\n첫 번째 프로세스 '{process_name}' 입력 데이터 매칭 및 경로 생성 중...")
    print(f"  매칭 조건: {modality_condition}")
    
    for data in export_list:
        data_modality = data.get('modality')
        
        # modality가 조건 리스트에 있는지 확인
        if data_modality in modality_condition:
            raw_path = data.get('raw')
            
            if not raw_path:
                logger.warning(f"raw 경로가 없는 데이터: {data_modality}")
                continue
            
            try:
                # BIDS 정보 추출
                bids_info = extract_bids_info(raw_path)
                
                if not all([bids_info['run_num'], bids_info['alias_id'], 
                           bids_info['ses_num'], bids_info['data_type']]):
                    logger.warning(f"BIDS 정보 추출 실패: {raw_path}")
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
                first_flag['derived_data'].append({
                    'input': raw_path,
                    'output_path': str(derived_output_folder_path),
                    'run_num': bids_info['run_num'],
                    'exe_num': exe_num
                })
                
                matched_count += 1
                logger.info(f"매칭 성공: {data_modality} -> run:{bids_info['run_num']}, exe:{exe_num}")
                
            except Exception as e:
                logger.error(f"경로 생성 오류 ({raw_path}): {e}")
                continue
    
    print(f"  매칭 및 경로 생성 완료: {matched_count}개 데이터\n")
    logger.info(f"첫 번째 프로세스에 {matched_count}개 입력 데이터 할당 완료")
    
    if matched_count == 0:
        logger.warning(f"첫 번째 프로세스 '{process_name}'에 매칭되는 데이터가 없음")
        print(f"WARNING: '{process_name}' 프로세스에 처리할 데이터가 없습니다")
        return None
    
    # 10. export_data에 flag_list 업데이트
    print("export JSON 파일 업데이트 중...")
    export_data['flag'] = flag_list
    
    try:
        with open(export_json_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)
        logger.info(f"export JSON 파일 업데이트 완료: {export_json_path}")
        print(f"  업데이트 완료: {export_json_path}")
    except Exception as e:
        logger.error(f"export JSON 파일 저장 오류: {e}")
        print(f"ERROR: JSON 파일 저장 실패: {e}")
        return None
    
    # 11. flag_dir에 JSON 파일 복사
    flag_dir = global_vars.get('flag_dir')
    if not flag_dir:
        logger.error("flag_dir를 찾을 수 없음")
        print("ERROR: flag_dir 경로가 없습니다")
        return None
    
    flag_event_path = Path(flag_dir) / process_name / package
    
    try:
        # 프로세스 이벤트 경로 생성
        os.makedirs(flag_event_path, exist_ok=True)
        
        # 파일명 추출 및 복사
        json_filename = Path(export_json_path).name
        destination_path = flag_event_path / json_filename
        
        shutil.move(export_json_path, destination_path)
        logger.info(f"JSON 파일 이벤팅: {destination_path}")
        print(f" 이벤팅 완료: {destination_path}\n")
        
    except Exception as e:
        logger.error(f"JSON 파일 백업 오류: {e}")
        print(f"ERROR: 파일 백업 실패: {e}")
        return None
    
    print("전처리 준비 완료!\n")
    
    # TODO: 실제 전처리 로직
    
    return None