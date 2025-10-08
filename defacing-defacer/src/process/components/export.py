#/BDSP/defacer_app/src/process/components/export.py
import json
import logging

logger = logging.getLogger(__name__)


def export_json(execution_result, json_file_path, process, package):
    """
    execution_result의 outputs를 JSON 파일의 flag.derived_data에 업데이트

    Args:
        execution_result (list): cli.execute_commands()의 반환값
        json_file_path (str): 업데이트할 JSON 파일 경로
        process (str): 매칭할 process 이름
        package (str): 매칭할 package 이름

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

        # 3. derived_data 배열과 execution_result 매칭하여 업데이트
        derived_data_list = target_flag.get('derived_data', [])

        # 길이 검증: 반드시 일치해야 함
        if len(derived_data_list) != len(execution_result):
            error_msg = (
                f"Length mismatch: derived_data has {len(derived_data_list)} items, "
                f"but execution_result has {len(execution_result)} items"
            )
            logger.error(error_msg)
            raise ValueError(error_msg)

        # execution_result의 각 항목을 derived_data에 추가
        for idx, result in enumerate(execution_result):
            outputs = result.get('outputs', {})
            # outputs 객체를 통째로 derived_data[idx]에 추가
            derived_data_list[idx]['outputs'] = outputs
            logger.info(f"Updated derived_data[{idx}] with outputs: {outputs}")

        # 변경: status를 'done'으로 갱신
        try:
            target_flag['status'] = 'done'
            logger.info(f"Set status='done' for flag process={process}, package={package}")
        except Exception as e:
            # 상태 갱신 실패는 치명적이지 않으나 로그로 남김
            logger.warning(f"Failed to set status on target_flag: {e}")

        # 4. 업데이트된 JSON을 파일에 저장
        logger.info(f"Writing updated JSON to: {json_file_path}")
        with open(json_file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info("JSON file updated successfully")
        return True

    except ValueError as e:
        # 길이 불일치 등 검증 에러
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
