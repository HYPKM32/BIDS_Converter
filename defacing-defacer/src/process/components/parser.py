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
        derivatives_list = flag.get('derivatives', []) or []  # ← 변경: derived_data → derivatives

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

        # derivatives 개수만큼 커맨드 생성
        for data_idx, derivative in enumerate(derivatives_list):  # ← 변경: derived_data → derivative
            input_data = derivative.get('input', [])
            output_dir = derivative.get('outputDir', '')  # ← 변경: output_path → outputDir

            # input이 리스트가 아닌 경우 리스트로 변환 (하위 호환성)
            if not isinstance(input_data, list):
                input_data = [input_data] if input_data else []

            # 전체 커맨드 구성: 항상 sys.executable을 앞에 둠
            command_list = [sys.executable, command]
            # 옵션들 추가
            if option_args:
                command_list.extend(option_args)

            # 입력 추가: --input path1 path2 path3
            if input_data:
                # None 값 필터링
                filtered_inputs = [str(inp) for inp in input_data if inp is not None]
                if filtered_inputs:
                    command_list.append("--input")
                    command_list.extend(filtered_inputs)

            # 출력 추가
            if output_dir:
                command_list.extend(["--output", output_dir])

            cli.append(command_list)

            logger.info(f"Generated command [{len(cli)-1}]: {' '.join(command_list)}")

    logger.info(f"Total commands generated: {len(cli)}")
    return cli