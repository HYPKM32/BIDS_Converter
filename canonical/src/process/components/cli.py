#/BDSP/canonical_app/src/process/components/cli.py
import subprocess
import logging
import os

logger = logging.getLogger(__name__)

def parse_output_paths(command_list, flag):
    """
    커맨드 리스트에서 input/output 경로를 추출하고 실제/예상 출력 파일들을 생성 
    각 프로세스마다 실제 수정해야할 파일
    
    Args:
        command_list (list): 실행할 커맨드 리스트
        flag (dict): flag 딕셔너리 (exeNum 포함)
        
    Returns:
        dict: 실제 및 예상되는 출력 파일 경로들
              {
                  "input": "...",
                  "output_dir": "...",
                  "outputs": {
                      "data": "...",  # exe-XX 없는 실제 생성 파일
                      "thumbnail": "..."
                  },
                  "expected_outputs": {
                      "data": "...",  # exe-XX 포함된 예상 파일 (rename 목표)
                      "thumbnail": "..."
                  }
              }
    
    Raises:
        ValueError: exeNum이 flag에 없을 경우
    """
    input_path = None
    output_dir = None
    
    # 커맨드에서 -i/--input과 -o/--output 추출
    for i, arg in enumerate(command_list):
        if arg in ['-i', '--input'] and i + 1 < len(command_list):
            input_path = command_list[i + 1]
        elif arg in ['-o', '--output'] and i + 1 < len(command_list):
            output_dir = command_list[i + 1]
    
    if not input_path or not output_dir:
        logger.warning("Could not extract input/output paths from command")
        return None
    
    # flag에서 exeNum 추출 (필수값) - JSON 키는 camelCase
    if 'exeNum' not in flag:
        raise ValueError("flag 딕셔너리에 'exeNum' 키가 필수입니다")
    
    exe_num = flag['exeNum']
    
    # exe_num이 비어있거나 None인 경우도 체크
    if not exe_num:
        raise ValueError("exe_num 값이 비어있습니다")
    
    # input 파일명에서 정보 추출
    input_basename = os.path.basename(input_path)  
    
    # .nii.gz 제거
    if input_basename.endswith('.nii.gz'):
        name_without_ext = input_basename[:-7]  
    else:
        logger.warning(f"Unexpected file extension: {input_basename}")
        name_without_ext = os.path.splitext(input_basename)[0]
    
    parts = name_without_ext.split('_')
    
    # 실제 파일명 (exe-XX 없음) - subprocess가 생성하는 파일명
    # drv- 엔티티를 drv-canonical로 교체하고, 없으면 마지막 앞에 추가
    actual_parts = []
    has_drv = False
    
    for i, part in enumerate(parts[:-1]):  # 마지막 요소(T1w 등) 제외
        if part.startswith('drv-'):
            # 기존 drv-*를 drv-canonical로 교체
            actual_parts.append('drv-canonical')
            has_drv = True
        else:
            actual_parts.append(part)
    
    # drv-가 없었으면 마지막 앞에 추가
    if not has_drv:
        actual_parts.append('drv-canonical')
    
    # 마지막 요소(T1w 등) 추가
    actual_parts.append(parts[-1])
    
    actual_filename = '_'.join(actual_parts) + '.nii.gz'
    actual_data = os.path.join(output_dir, actual_filename)
    
    # 2. actual thumbnail
    actual_thumbnail = actual_data.replace('.nii.gz', '.png')
    
    # 예상 파일명 (exe-XX 포함) - 최종적으로 rename될 파일명
    # exe-* 패턴이 있으면 교체, 없으면 run-XX 뒤에 추가
    # drv-* 패턴이 있으면 drv-canonical로 교체, 없으면 마지막 앞에 추가
    new_parts = []
    has_exe = False
    has_drv = False
    
    for part in parts[:-1]:  # 마지막 요소(T1w 등) 제외
        if part.startswith('exe-'):
            # 기존 exe-*를 건너뛰고 아직 추가 안했으면 새로운 exe 추가
            if not has_exe:
                new_parts.append(f'exe-{exe_num}')
                has_exe = True
            # 기존 exe는 무시 (중복 방지)
            continue
        elif part.startswith('drv-'):
            # 기존 drv-*를 drv-canonical로 교체
            if not has_drv:
                new_parts.append('drv-canonical')
                has_drv = True
            # 기존 drv는 무시 (중복 방지)
            continue
        else:
            new_parts.append(part)
            # exe-*가 없었고, run-XX를 만났다면 그 뒤에 추가
            if not has_exe and part.startswith('run-'):
                new_parts.append(f'exe-{exe_num}')
                has_exe = True
    
    # drv-가 아직 추가되지 않았으면 마지막 앞에 추가
    if not has_drv:
        new_parts.append('drv-canonical')
    
    # 마지막 요소(T1w 등) 추가
    new_parts.append(parts[-1])
    
    expected_filename = '_'.join(new_parts) + '.nii.gz'
    expected_data = os.path.join(output_dir, expected_filename)
    
    # 2. expected thumbnail
    expected_thumbnail = expected_data.replace('.nii.gz', '.png')
    
    return {
        "input": input_path,
        "output_dir": output_dir,
        "outputs": {
            "data": actual_data,
            "thumbnail": actual_thumbnail
        },
        "expected_outputs": {
            "data": expected_data,
            "thumbnail": expected_thumbnail
        }
    }


def rename_output_files(actual_files, expected_files):
    """
    실제 생성된 파일들을 예상 파일명으로 rename
    
    Args:
        actual_files (dict): 실제 생성된 파일 경로들
        expected_files (dict): 예상되는 파일 경로들 (rename 목표)
        
    Returns:
        dict: rename 결과
              {
                  "data": {"success": True/False, "error": None/str},
                  "thumbnail": {...}
              }
    """
    rename_results = {}
    
    for file_type in ["data", "thumbnail"]:
        actual_path = actual_files.get(file_type)
        expected_path = expected_files.get(file_type)
        
        result = {"success": False, "error": None}
        
        try:
            if actual_path and expected_path and os.path.exists(actual_path):
                # 파일이 존재하면 rename
                os.rename(actual_path, expected_path)
                result["success"] = True
                logger.info(f"Renamed: {actual_path} -> {expected_path}")
            else:
                # 파일이 없으면 경고
                error_msg = f"File not found: {actual_path}"
                result["error"] = error_msg
                logger.warning(error_msg)
        except Exception as e:
            result["error"] = str(e)
            logger.error(f"Failed to rename {actual_path} -> {expected_path}: {e}")
        
        rename_results[file_type] = result
    
    return rename_results


def execute_commands(cli, flags):
    """
    cli 리스트의 커맨드들을 실행하고 각 커맨드의 예상 출력 정보 반환
    실패 시 즉시 예외를 발생시켜 다음 명령어 실행을 중단함
    
    Args:
        cli (list): 커맨드 리스트들의 리스트
        flags (list): 각 커맨드에 대응하는 flag 딕셔너리 리스트
        
    Returns:
        list: 각 커맨드의 실행 결과 및 출력 정보
              [
                  {
                      "index": 0,
                      "command": "python3 canonical_cli.py ...",
                      "success": True,
                      "input": "...",
                      "output_dir": "...",
                      "outputs": {...},  # rename 후 최종 파일 경로
                      "rename_results": {...},
                      "exit_code": 0,
                      "error": None,
                      "flag": {...}
                  },
                  ...
              ]
              
    Raises:
        subprocess.CalledProcessError: 커맨드 실행 실패 시
        Exception: 기타 실행 오류 시
    """
    if len(cli) != len(flags):
        raise ValueError(f"cli 리스트와 flags 리스트의 길이가 일치하지 않습니다. cli={len(cli)}, flags={len(flags)}")
    
    execution_results = []
    
    for idx, (command_list, flag) in enumerate(zip(cli, flags)):
        # 예상 출력 경로 파싱 (flag 정보 전달)
        output_paths = parse_output_paths(command_list, flag)
        
        result_info = {
            "index": idx,
            "command": ' '.join(command_list),
            "success": False,
            "input": output_paths["input"] if output_paths else None,
            "output_dir": output_paths["output_dir"] if output_paths else None,
            "outputs": output_paths["outputs"] if output_paths else None,
            "rename_results": None,
            "exit_code": None,
            "error": None,
            "flag": flag
        }
        
        try:
            # JSON 키는 camelCase로 접근
            logger.info(f"Executing command [{idx}]: {' '.join(command_list)}")
            logger.info(f"  exe_num: {flag.get('exeNum', 'N/A')}")
            
            # subprocess.run으로 커맨드 실행
            result = subprocess.run(
                command_list,
                capture_output=True,
                text=True,
                check=True,  # CalledProcessError 발생시킴
            )
            
            result_info["exit_code"] = result.returncode
            
            logger.info(f"Command [{idx}] completed successfully")
            
            if result.stdout:
                logger.info(f"stdout: {result.stdout}")
            
            if result.stderr:
                logger.warning(f"stderr: {result.stderr}")
            
            # 파일 rename 수행
            if output_paths:
                logger.info(f"Renaming output files...")
                rename_results = rename_output_files(
                    output_paths["outputs"],
                    output_paths["expected_outputs"]
                )
                result_info["rename_results"] = rename_results
                
                # rename 성공한 파일들은 outputs를 expected_outputs로 업데이트
                for file_type in ["data", "thumbnail"]:
                    if rename_results[file_type]["success"]:
                        result_info["outputs"][file_type] = output_paths["expected_outputs"][file_type]
                        logger.info(f"  ✓ {file_type}: renamed successfully")
                    else:
                        logger.warning(f"  ✗ {file_type}: {rename_results[file_type]['error']}")
            
            result_info["success"] = True
            execution_results.append(result_info)
                
        except subprocess.CalledProcessError as e:
            result_info["success"] = False
            result_info["exit_code"] = e.returncode
            result_info["error"] = e.stderr
            
            logger.error(f"Command [{idx}] failed with exit code {e.returncode}")
            logger.error(f"Command: {' '.join(command_list)}")
            logger.error(f"stdout: {e.stdout}")
            logger.error(f"stderr: {e.stderr}")
            
            execution_results.append(result_info)
            
            # 즉시 예외를 다시 발생시켜 다음 명령어 실행 중단
            raise
            
        except Exception as e:
            result_info["success"] = False
            result_info["error"] = str(e)
            
            logger.error(f"Error executing command [{idx}]: {e}")
            logger.error(f"Command: {' '.join(command_list)}")
            
            execution_results.append(result_info)
            
            # 즉시 예외를 다시 발생시켜 다음 명령어 실행 중단
            raise
    
    # 모든 명령어 성공 시에만 도달
    logger.info(f"Execution summary: {len(execution_results)}/{len(cli)} commands succeeded")
    
    return execution_results