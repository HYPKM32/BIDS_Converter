#/BDSP/civet_app/src/process/components/parser.py
import logging
import os
import glob

logger = logging.getLogger(__name__)


def parser(command, filtered_flags, civet_work_mapping):
    """
    CIVET 명령어 생성
    
    CIVET 형식:
        CIVET_Processing_Pipeline [options] -sourcedir {input} -targetdir {output} {working_name} -run
    
    Returns:
        list: 명령어 리스트 [["cmd", "arg1", ...], ["cmd", "arg2", ...]]
    """
    logger.info(f"Starting parser: {len(filtered_flags)} flag(s)")
    
    command_list = []
    
    for flag in filtered_flags:
        options = flag.get('options', []) or []
        derivatives_list = flag.get('derivatives', []) or []
        
        # Options 파싱
        option_args = []
        for option in options:
            for key, value in option.items():
                if isinstance(value, bool):
                    if value:
                        option_args.append(f"-{key}")
                elif isinstance(value, (list, tuple)):
                    option_args.append(f"-{key}")
                    option_args.extend([str(v) for v in value])
                else:
                    option_args.append(f"-{key}")
                    option_args.append(str(value))
        
        # Derivatives별 명령어 생성
        for derivative in derivatives_list:
            output_dir = derivative.get('outputDir', '')
            
            # Mapping에서 정보 가져오기
            mapping = civet_work_mapping.get(output_dir)
            if not mapping:
                raise ValueError(f"Mapping not found: {output_dir}")
            
            tmp_dir = mapping['tmp_dir']
            working_name = mapping['working_name']
            
            # 명령어 구성: CIVET 표준 형식
            cmd = [command]
            cmd.extend(option_args)
            cmd.extend(["-sourcedir", tmp_dir])
            cmd.extend(["-targetdir", tmp_dir])
            cmd.append(working_name)
            cmd.append("-run")
            
            command_list.append(cmd)
            logger.info(f"Command: {' '.join(cmd)}")
    
    logger.info(f"Generated {len(command_list)} command(s)")
    return command_list