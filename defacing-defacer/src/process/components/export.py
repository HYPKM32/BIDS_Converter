import json
import logging

logger = logging.getLogger(__name__)


def export_json(execution_result, json_file_path, process, package, sidecar_json_list):
    """
    execution_result의 outputs를 JSON 파일의 flag.derivatives에 업데이트

    Args:
        execution_result (list): cli.execute_commands()의 반환값
        json_file_path (str): 업데이트할 JSON 파일 경로
        process (str): 매칭할 process 이름
        package (str): 매칭할 package 이름
        sidecar_json_list (list): sidecar JSON 파일 경로 리스트 (execution_result와 1:1 대응)

    Returns:
        bool: 성공 시 True
    """
    try:
        # 1. JSON 파일 읽기
        logger.info(f"Reading JSON file: {json_file_path}")
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # 2. flag 리스트에서 process와 package가 일치하는 객체 찾기
        target_flag = None
        for flag in data.get('flag', []):
            if flag.get('process') == process and flag.get('package') == package:
                target_flag = flag
                logger.info(f"Found matching flag: process={process}, package={package}")
                break

        if target_flag is None:
            logger.error(f"No matching flag found for process={process}, package={package}")
            return False

        # 3. derivatives 배열과 execution_result 매칭하여 업데이트
        derivatives_list = target_flag.get('derivatives', [])  # ← 변경: derived_data → derivatives

        # 길이 검증: 반드시 일치해야 함
        if len(derivatives_list) != len(execution_result):  # ← 변경
            error_msg = (
                f"Length mismatch: derivatives has {len(derivatives_list)} items, "  # ← 변경
                f"but execution_result has {len(execution_result)} items"
            )
            logger.error(error_msg)
            raise ValueError(error_msg)

        # sidecar_json_list 길이도 검증
        if len(sidecar_json_list) != len(execution_result):
            error_msg = (
                f"Length mismatch: sidecar_json_list has {len(sidecar_json_list)} items, "
                f"but execution_result has {len(execution_result)} items"
            )
            logger.error(error_msg)
            raise ValueError(error_msg)

        # execution_result의 각 항목을 derivatives에 추가
        for idx, result in enumerate(execution_result):
            result_outputs = result.get('outputs', {})
            
            # outputs: defaced_data와 defacemask 모두 포함 (키 이름은 유지)
            outputs = {
                'defacing': result_outputs.get('data', ''),
                'defacemask': result_outputs.get('mask', '')
            }
            
            # sidecar: 해당 index의 sidecar 경로 (문자열)
            sidecar = sidecar_json_list[idx] if idx < len(sidecar_json_list) else ''
            
            # byproduct: thumbnail을 포함한 객체
            byproduct = {}
            thumbnail = result_outputs.get('thumbnail', '')
            if thumbnail:
                byproduct['thumbnail'] = thumbnail
            
            # derivatives[idx]에 필드 추가
            derivatives_list[idx]['outputs'] = outputs  # ← 변경
            derivatives_list[idx]['sidecar'] = sidecar  # ← 변경
            derivatives_list[idx]['byproduct'] = byproduct  # ← 변경
            
            logger.info(f"Updated derivatives[{idx}]:")  # ← 변경
            logger.info(f"  - outputs: {outputs}")
            logger.info(f"  - sidecar: {sidecar}")
            logger.info(f"  - byproduct: {byproduct}")

        # 4. status를 'done'으로 갱신
        try:
            target_flag['status'] = 'done'
            logger.info(f"Set status='done' for flag process={process}, package={package}")
        except Exception as e:
            logger.warning(f"Failed to set status on target_flag: {e}")

        # 5. 업데이트된 JSON을 파일에 저장
        logger.info(f"Writing updated JSON to: {json_file_path}")
        with open(json_file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info("JSON file updated successfully")
        return True

    except ValueError as e:
        logger.error(f"Validation error: {e}")
        return False
    except FileNotFoundError:
        logger.error(f"JSON file not found: {json_file_path}")
        return False
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON format: {e}")
        return False
    except Exception as e:
        logger.error(f"Error updating JSON file: {e}")
        return False