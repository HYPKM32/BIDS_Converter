import json
import logging
import os
from . import modality_mapper as mapper
from . import name_builder as builder
from . import dcm2nii_parser as parser

logger = logging.getLogger(__name__)

def create_raw_path(structured_config, source_path, global_vars):
    """Raw 데이터 경로 생성 및 모달리티 분석"""
    
    # 1. Raw 경로 생성 (sourcedata -> rawdata)
    raw_path = source_path['source_path'].replace('/sourcedata', '/rawdata')
    alias_id = os.path.basename(source_path['subject_path'])
    # 2. 포맷 확인 (format_path에서 마지막 폴더명)
    format_name = os.path.basename(source_path['format_path'])
    
    # 3. 포맷에 따라 적절한 Mapper 사용하여 매핑 딕셔너리 생성
    path_mapping = {}
    
    if format_name.upper() == 'DICOM':
        dicom_mapper = mapper.DicomMapper(global_vars, structured_config, source_path['separated_paths'])
        path_mapping = dicom_mapper.get_path_mapping()
    elif format_name.upper() == 'PARREC':
        parrec_mapper = mapper.ParrecMapper(global_vars, structured_config, source_path['separated_paths'])
        path_mapping = parrec_mapper.get_path_mapping()
    elif format_name.upper() == 'NIFTI':
        nifti_mapper = mapper.NiftiMapper(global_vars, structured_config, source_path['separated_paths'])
        path_mapping = nifti_mapper.get_path_mapping()
    else:
        logger.error(f"Unsupported format: {format_name}")
        raise ValueError(f"Unsupported format: {format_name}")

    print("Path mapping:", path_mapping)
    
    # 4. BIDS 형식 파일명 매핑 생성
    try:
        bids_mapping = builder.create_bids_mapping(
            path_mapping, 
            structured_config, 
            global_vars, 
            raw_path,
            alias_id
        )
        print("BIDS mapping:", bids_mapping)
        
        # 5. BIDS 변환 처리
        try:
            src2raw_map = parser.process_bids_conversion(bids_mapping)
            logger.info("BIDS conversion completed successfully")
        except Exception as e:
            logger.error(f"Failed to process BIDS conversion: {e}")
            raise
        
        return src2raw_map
        
    except Exception as e:
        logger.error(f"Failed to create BIDS mapping: {e}")
        raise