#/BDSP/defacer_app/src/process/components/parser.py
import logging
import sys

logger = logging.getLogger(__name__)


def parser(command, filtered_flags):
    """
    필터링된 flag 데이터에서 커맨드 아규먼트를 정리

    Args:
        command (str): 실행할 스크립트/실행파일 경로 (예: "/BDSP/.../defacer_cli.py")
        filtered_flags (list): 필터링된 flag 딕셔너리 리스트

    Returns:
        list: cli 리스트 (각 요소가 토큰 리스트로 된 커맨드)
              (예: [[sys.executable, "/path/defacer_cli.py", "--verification", "y", ...], ...])
    """
    logger.info(f"Parsing {len(filtered_flags)} flag(s) with command: {command}")

    cli = []

    for flag_idx, flag in enumerate(filtered_flags):
        process = flag.get('process', '')
        package = flag.get('package', '')
        options = flag.get('options', []) or []
        derived_data_list = flag.get('derived_data', []) or []

        logger.info(f"Processing flag {flag_idx}: process={process}, package={package}")

        # options 파싱
        option_args = []
        for option in options:
            for key, value in option.items():
                # boolean 플래그 (True => --flag, False => skip)
                if isinstance(value, bool):
                    if value:
                        option_args.append(f"--{key}")
                    # False는 아예 추가하지 않음
                    continue

                # 리스트인 경우: --parts eyes nose ears mouth
                if isinstance(value, (list, tuple)):
                    if len(value) == 0:
                        # 빈 리스트면 단순히 플래그로 취급 (원하면 수정)
                        option_args.append(f"--{key}")
                    else:
                        option_args.append(f"--{key}")
                        # str 변환 후 extend
                        option_args.extend([str(v) for v in value])
                else:
                    # 단일 값인 경우: --verification y
                    option_args.append(f"--{key}")
                    option_args.append(str(value))

        # derived_data 개수만큼 커맨드 생성
        for data_idx, derived_data in enumerate(derived_data_list):
            input_path = derived_data.get('input', '')
            output_path = derived_data.get('output_path', '')

            # 전체 커맨드 구성: 항상 sys.executable을 앞에 둠
            command_list = [sys.executable, command]
            # 옵션들 추가
            if option_args:
                command_list.extend(option_args)

            # 입력/출력 추가 (빈 값은 무시)
            if input_path:
                command_list.extend(["--input", input_path])
            if output_path:
                command_list.extend(["--output", output_path])

            cli.append(command_list)

            logger.info(f"Generated command [{len(cli)-1}]: {' '.join(command_list)}")

    logger.info(f"Total commands generated: {len(cli)}")
    return cli
