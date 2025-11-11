# /BDSP/civet_app/src/process/components/export.py
import json
import logging

logger = logging.getLogger(__name__)


def export_json(cleanup_results, json_file_path, process, package, sidecar_json_list):
    """
    cleanup_results의 outputs를 JSON 파일의 flag.derived_data에 업데이트

    Args:
        cleanup_results (list): civet_cleanup.bids_cleanup()의 반환값
                               [
                                   {
                                       "output_path": "...",
                                       "working_name": "...",
                                       "outputs": {
                                           "classify": {...},
                                           "transforms": {...},
                                           "surfaces": {...},
                                           ...
                                       }
                                   },
                                   ...
                               ]
        json_file_path (str): 업데이트할 JSON 파일 경로
        process (str): 매칭할 process 이름 (예: "T1wPreprocess")
        package (str): 매칭할 package 이름 (예: "civet")
        sidecar_json_list (list): sidecar JSON 파일 경로 리스트 (cleanup_results와 1:1 대응)

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

        # 3. derived_data 배열과 cleanup_results 매칭하여 업데이트
        derived_data_list = target_flag.get('derived_data', [])

        # 길이 검증: 반드시 일치해야 함
        if len(derived_data_list) != len(cleanup_results):
            error_msg = (
                f"Length mismatch: derived_data has {len(derived_data_list)} items, "
                f"but cleanup_results has {len(cleanup_results)} items"
            )
            logger.error(error_msg)
            raise ValueError(error_msg)

        # sidecar_json_list 길이도 검증
        if len(sidecar_json_list) != len(cleanup_results):
            error_msg = (
                f"Length mismatch: sidecar_json_list has {len(sidecar_json_list)} items, "
                f"but cleanup_results has {len(cleanup_results)} items"
            )
            logger.error(error_msg)
            raise ValueError(error_msg)

        # cleanup_results의 각 항목을 derived_data에 추가
        for idx, cleanup_result in enumerate(cleanup_results):
            # outputs: cleanup_result의 outputs를 그대로 저장 (옵션 A)
            # - classify, transforms, surfaces, thickness, mask, verify, temp, native 등
            outputs = cleanup_result.get('outputs', {})
            
            # sidecar: 해당 index의 sidecar 경로 (문자열)
            sidecar = sidecar_json_list[idx] if idx < len(sidecar_json_list) else ''
            
            # byproduct: 빈 객체 (옵션 A)
            byproduct = {}
            
            # derived_data[idx]에 필드 추가
            derived_data_list[idx]['outputs'] = outputs
            derived_data_list[idx]['sidecar'] = sidecar
            derived_data_list[idx]['byproduct'] = byproduct
            
            logger.info(f"Updated derived_data[{idx}]:")
            logger.info(f"  - outputs: {len(outputs)} stages")
            
            # 각 stage별 파일 개수 로깅
            for stage, stage_outputs in outputs.items():
                if isinstance(stage_outputs, dict):
                    # transforms는 3-depth 구조
                    if stage == 'transforms':
                        total_files = sum(len(v) for v in stage_outputs.values() if isinstance(v, dict))
                        logger.info(f"    - {stage}: {total_files} files")
                    else:
                        logger.info(f"    - {stage}: {len(stage_outputs)} files")
                else:
                    logger.info(f"    - {stage}: (non-dict)")
            
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