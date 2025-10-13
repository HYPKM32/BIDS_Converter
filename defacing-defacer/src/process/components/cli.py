#/BDSP/defacer_app/src/process/components/cli.py
import subprocess
import logging
import os

logger = logging.getLogger(__name__)

def parse_output_paths(command_list):
    """
    커맨드 리스트에서 input/output 경로를 추출하고 예상 출력 파일들을 생성
    
    Args:
        command_list (list): 실행할 커맨드 리스트
        
    Returns:
        dict: 예상되는 출력 파일 경로들
              {
                  "input": "...",
                  "output_dir": "...",
                  "defaced_data": "...",
                  "verification_img": "...",
                  "defacing_mask": "..."
              }
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
    
    # input 파일명에서 정보 추출
    input_basename = os.path.basename(input_path)  # sub-sub-2cna00001Hanyangparknm_ses-01_run-01_T1w.nii.gz
    
    # .nii.gz 제거
    if input_basename.endswith('.nii.gz'):
        name_without_ext = input_basename[:-7]  # sub-sub-2cna00001Hanyangparknm_ses-01_run-01_T1w
    else:
        logger.warning(f"Unexpected file extension: {input_basename}")
        name_without_ext = os.path.splitext(input_basename)[0]
    
    # 마지막 suffix 추출 (마지막 _T1w 부분)
    parts = name_without_ext.split('_')
    if len(parts) > 0:
        last_suffix = parts[-1]  # T1w
        prefix = '_'.join(parts[:-1])  # sub-sub-2cna00001Hanyangparknm_ses-01_run-01
    else:
        last_suffix = ""
        prefix = name_without_ext
    
    # 1. defaced_data: prefix_suffix-defaced.nii.gz
    defaced_filename = f"{prefix}_{last_suffix}-defaced.nii.gz"
    defaced_data = os.path.join(output_dir, defaced_filename)
    
    # 2. verification_img: defaced_data에서 .nii.gz -> .png
    verification_img = defaced_data.replace('.nii.gz', '.png')
    
    # 3. defacing_mask: prefix_defacing-mask.nii.gz (마지막 suffix 제거)
    mask_filename = f"{prefix}_defacing-mask.nii.gz"
    defacing_mask = os.path.join(output_dir, mask_filename)
    
    return {
        "input": input_path,
        "output_dir": output_dir,
        "defaced_data": defaced_data,
        "verification_img": verification_img,
        "defacing_mask": defacing_mask
    }


def execute_commands(cli):
    """
    cli 리스트의 커맨드들을 실행하고 각 커맨드의 예상 출력 정보 반환
    실패 시 즉시 예외를 발생시켜 다음 명령어 실행을 중단함
    
    Args:
        cli (list): 커맨드 리스트들의 리스트
        
    Returns:
        list: 각 커맨드의 실행 결과 및 출력 정보
              [
                  {
                      "index": 0,
                      "command": "python3 defacer_cli.py ...",
                      "success": True,
                      "input": "...",
                      "output_dir": "...",
                      "outputs": {
                          "defaced_data": "...",
                          "verification_img": "...",
                          "defacing_mask": "..."
                      },
                      "exit_code": 0,
                      "error": None
                  },
                  ...
              ]
              
    Raises:
        subprocess.CalledProcessError: 커맨드 실행 실패 시
        Exception: 기타 실행 오류 시
    """
    execution_results = []
    
    for idx, command_list in enumerate(cli):
        # 예상 출력 경로 파싱
        output_paths = parse_output_paths(command_list)
        
        result_info = {
            "index": idx,
            "command": ' '.join(command_list),
            "success": False,
            "input": output_paths["input"] if output_paths else None,
            "output_dir": output_paths["output_dir"] if output_paths else None,
            "outputs": {
                "defaced_data": output_paths["defaced_data"] if output_paths else None,
                "verification_img": output_paths["verification_img"] if output_paths else None,
                "defacing_mask": output_paths["defacing_mask"] if output_paths else None
            },
            "exit_code": None,
            "error": None
        }
        
        try:
            logger.info(f"Executing command [{idx}]: {' '.join(command_list)}")
            
            # subprocess.run으로 커맨드 실행
            result = subprocess.run(
                command_list,
                capture_output=True,
                text=True,
                check=True,  # CalledProcessError 발생시킴
            )
            
            result_info["success"] = True
            result_info["exit_code"] = result.returncode
            
            logger.info(f"Command [{idx}] completed successfully")
            logger.info(f"Expected outputs:")
            logger.info(f"  - input: {result_info['input']}")
            logger.info(f"  - output_dir: {result_info['output_dir']}")
            logger.info(f"  - defaced_data: {result_info['outputs']['defaced_data']}")
            logger.info(f"  - verification_img: {result_info['outputs']['verification_img']}")
            logger.info(f"  - defacing_mask: {result_info['outputs']['defacing_mask']}")
            
            if result.stdout:
                logger.info(f"stdout: {result.stdout}")
            
            if result.stderr:
                logger.warning(f"stderr: {result.stderr}")
            
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