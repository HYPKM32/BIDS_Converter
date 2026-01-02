import json
import logging
import os
from . import tracer_mapper as mapper
from . import name_builder as builder
from . import dcm2nii_parser as parser

logger = logging.getLogger(__name__)

def create_raw_path(structured_config, source_path, global_vars):
    """PET Raw 데이터 경로 생성 및 tracer 분석"""

    # 1. Raw 경로 생성 (sourcedata -> rawdata)
    raw_path = source_path['source_path'].replace('/sourcedata', '/rawdata')
    alias_id = os.path.basename(source_path['subject_path'])

    # 2. 포맷 확인 (PET은 DICOM만 지원)
    format_name = os.path.basename(source_path['format_path'])

    # 3. DICOM Tracer Mapper 사용
    path_mapping = {}

    if format_name.upper() == 'DICOM':
        dicom_mapper = mapper.DicomTracerMapper(global_vars, structured_config, source_path['separated_paths'])
        path_mapping = dicom_mapper.get_path_mapping()
    else:
        logger.error(f"PET은 DICOM만 지원합니다: {format_name}")
        raise ValueError(f"PET은 DICOM만 지원합니다: {format_name}")

    print("PET Path mapping (tracer):", path_mapping)

    # 4. BIDS 형식 파일명 매핑 생성
    try:
        bids_mapping = builder.create_bids_mapping(
            path_mapping,
            structured_config,
            global_vars,
            raw_path,
            alias_id
        )
        print("PET BIDS mapping:", bids_mapping)

        # 5. BIDS 변환 처리
        try:
            src2raw_map = parser.process_bids_conversion(bids_mapping)
            logger.info("PET BIDS conversion completed successfully")
        except Exception as e:
            logger.error(f"Failed to process PET BIDS conversion: {e}")
            raise

        return src2raw_map

    except Exception as e:
        logger.error(f"Failed to create PET BIDS mapping: {e}")
        raise
