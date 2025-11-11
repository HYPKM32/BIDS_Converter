#/BDSP/civet_app/src/process/components/pcli.py
import os
import logging
import subprocess
import shutil
from concurrent.futures import ProcessPoolExecutor, as_completed

logger = logging.getLogger(__name__)


def collect_directory_structure(directory_path, base_name):
    """
    디렉토리의 전체 구조를 '폴더/하위폴더/파일명' 형식으로 수집
    
    Args:
        directory_path (str): 탐색할 디렉토리 경로
        base_name (str): 기준 디렉토리 이름 (상대 경로 시작점)
        
    Returns:
        list: 모든 파일의 상대 경로 리스트
              예: ["logs/file1.txt", "logs/subfolder/file2.txt", ...]
    """
    items = []
    
    for root, dirs, files in os.walk(directory_path):
        # 현재 디렉토리의 상대 경로 계산
        rel_root = os.path.relpath(root, directory_path)
        
        # 최상위 디렉토리인 경우
        if rel_root == '.':
            prefix = base_name
        else:
            prefix = os.path.join(base_name, rel_root)
        
        # 모든 파일 추가
        for file in files:
            file_path = os.path.join(prefix, file)
            items.append(file_path)
    
    return items


def run_single_command(command_list, index, derived_data, civet_work_mapping):
    """
    단일 CIVET 커맨드 실행 및 결과 처리
    
    Args:
        command_list (list): 실행할 커맨드 토큰 리스트
        index (int): 커맨드 인덱스
        derived_data (dict): 해당 커맨드의 derived_data
        civet_work_mapping (dict): 작업 디렉토리 매핑 정보
        
    Returns:
        dict: 실행 결과
    """
    output_path = derived_data.get('output_path', '')
    mapping = civet_work_mapping.get(output_path, {})
    tmp_dir = mapping.get('tmp_dir', '')
    working_name = mapping.get('working_name', '')
    
    result = {
        "index": index,
        "command": ' '.join(command_list),
        "success": False,
        "tmp_dir": tmp_dir,
        "working_name": working_name,
        "output_path": output_path,
        "moved": False,
        "tmp_cleaned": False,
        "exit_code": None,
        "stdout": "",
        "stderr": "",
        "error": None,
        "moved_items": [],
        "derived_data": derived_data
    }
    
    try:
        logger.info(f"[{index}] Executing command: {' '.join(command_list)}")
        
        # subprocess 실행
        proc_result = subprocess.run(
            command_list,
            capture_output=True,
            text=True,
            check=False  # 실패해도 예외 발생 안함
        )
        
        result["exit_code"] = proc_result.returncode
        result["stdout"] = proc_result.stdout
        result["stderr"] = proc_result.stderr
        
        # 실패 체크
        if proc_result.returncode != 0:
            result["error"] = f"Command failed with exit code {proc_result.returncode}"
            logger.error(f"[{index}] Command failed with exit code {proc_result.returncode}")
            logger.error(f"[{index}] stderr: {proc_result.stderr}")
            return result
        
        logger.info(f"[{index}] Command completed successfully")
        
        # CIVET 출력 디렉토리 확인
        civet_output_dir = os.path.join(tmp_dir, working_name)
        
        if not os.path.exists(civet_output_dir):
            result["error"] = f"CIVET output directory not found: {civet_output_dir}"
            logger.error(f"[{index}] {result['error']}")
            return result
        
        logger.info(f"[{index}] Found CIVET output: {civet_output_dir}")
        
        # output_path 디렉토리 생성
        os.makedirs(output_path, exist_ok=True)
        
        # working_name 하위 내용물만 output_path로 복사
        logger.info(f"[{index}] Moving files from {civet_output_dir} to {output_path}")
        
        moved_items = []
        
        for item in os.listdir(civet_output_dir):
            source_item = os.path.join(civet_output_dir, item)
            dest_item = os.path.join(output_path, item)
            
            try:
                if os.path.isdir(source_item):
                    # 디렉토리인 경우: 전체 트리 구조 수집
                    shutil.copytree(source_item, dest_item, dirs_exist_ok=True)
                    
                    # 디렉토리 하위의 모든 파일 목록 수집
                    dir_structure = collect_directory_structure(source_item, item)
                    moved_items.extend(dir_structure)
                    
                    logger.debug(f"[{index}]   Moved directory: {item} ({len(dir_structure)} items)")
                else:
                    # 파일인 경우: 직접 복사
                    shutil.copy2(source_item, dest_item)
                    moved_items.append(item)
                    logger.debug(f"[{index}]   Moved file: {item}")
                
            except Exception as e:
                logger.warning(f"[{index}]   Failed to move {item}: {e}")
        
        result["moved"] = True
        result["moved_items"] = moved_items
        logger.info(f"[{index}] Moved {len(moved_items)} items to {output_path}")
        
        # tmp 디렉토리 삭제
        try:
            shutil.rmtree(tmp_dir)
            result["tmp_cleaned"] = True
            logger.info(f"[{index}] Cleaned tmp directory: {tmp_dir}")
        except Exception as e:
            logger.warning(f"[{index}] Failed to clean tmp directory {tmp_dir}: {e}")
        
        result["success"] = True
        return result
        
    except Exception as e:
        result["error"] = str(e)
        logger.error(f"[{index}] Unexpected error: {e}", exc_info=True)
        return result


def execute_commands(command_list, derived_data_list, civet_work_mapping, workers):
    """
    CIVET 커맨드들을 병렬로 실행하고 결과 처리
    
    Args:
        command_list (list): 실행할 커맨드 리스트
        derived_data_list (list): 각 커맨드의 derived_data
        civet_work_mapping (dict): {output_path: {"tmp_dir": ..., "working_name": ...}}
        workers (int): 최대 동시 실행 노드 수
        
    Returns:
        list: execution_results
        
    Raises:
        RuntimeError: 하나라도 실패한 경우
        ValueError: 입력 리스트 길이 불일치
    """
    # 입력 검증
    if len(command_list) != len(derived_data_list):
        raise ValueError(
            f"command_list and derived_data_list length mismatch: "
            f"{len(command_list)} vs {len(derived_data_list)}"
        )
    
    total_commands = len(command_list)
    logger.info(f"Starting parallel execution of {total_commands} commands with {workers} workers")
    
    execution_results = [None] * total_commands  # 인덱스 순서 유지
    
    # 병렬 실행
    with ProcessPoolExecutor(max_workers=workers) as executor:
        # 모든 커맨드를 executor에 제출
        future_to_index = {}
        
        for idx, (cmd, derived_data) in enumerate(zip(command_list, derived_data_list)):
            future = executor.submit(
                run_single_command,
                cmd,
                idx,
                derived_data,
                civet_work_mapping
            )
            future_to_index[future] = idx
        
        logger.info(f"Submitted {len(future_to_index)} commands to executor")
        
        # 완료되는 대로 결과 수집
        completed = 0
        for future in as_completed(future_to_index):
            idx = future_to_index[future]
            
            try:
                result = future.result()
                execution_results[idx] = result
                completed += 1
                
                if result["success"]:
                    logger.info(
                        f"[{idx}] Completed successfully "
                        f"({completed}/{total_commands})"
                    )
                else:
                    logger.error(
                        f"[{idx}] Failed: {result['error']} "
                        f"({completed}/{total_commands})"
                    )
                    
            except Exception as e:
                logger.error(f"[{idx}] Exception during execution: {e}", exc_info=True)
                # 예외 발생 시 실패 결과 기록
                execution_results[idx] = {
                    "index": idx,
                    "command": ' '.join(command_list[idx]) if idx < len(command_list) else "unknown",
                    "success": False,
                    "error": str(e),
                    "exit_code": None,
                    "moved": False,
                    "tmp_cleaned": False,
                    "moved_items": []
                }
                completed += 1
    
    # 결과 요약
    success_count = sum(1 for r in execution_results if r and r["success"])
    failed_count = total_commands - success_count
    
    logger.info(f"Execution completed: {success_count} succeeded, {failed_count} failed")
    
    # 실패한 커맨드 상세 로그
    if failed_count > 0:
        logger.error(f"{failed_count}/{total_commands} commands failed:")
        
        for result in execution_results:
            if result and not result["success"]:
                logger.error(f"  [{result['index']}] {result['command']}")
                logger.error(f"    Error: {result['error']}")
                logger.error(f"    Exit code: {result.get('exit_code', 'N/A')}")
                
                if result.get('stderr'):
                    logger.error(f"    Stderr: {result['stderr'][:200]}...")  # 처음 200자만
                
                if not result.get('tmp_cleaned'):
                    logger.warning(f"    Tmp directory kept for debugging: {result.get('tmp_dir')}")
        
        # 예외 발생
        raise RuntimeError(
            f"{failed_count} out of {total_commands} CIVET commands failed. "
            f"Check logs for details."
        )
    
    logger.info(f"All {total_commands} commands completed successfully")
    return execution_results