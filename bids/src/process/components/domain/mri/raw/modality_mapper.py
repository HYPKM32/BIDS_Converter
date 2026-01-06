#/BDSP/bids_app/src/process/components/domain/mri/raw/modality_mapper.py
import json
import logging
import os
import pydicom
from pathlib import Path
from utils.common import remove_all_whitespace, remove_special_chars

logger = logging.getLogger(__name__)

class DicomMapper:
    def __init__(self, global_vars, structured_config, separated_paths):
        self.global_vars = global_vars
        self.structured_config = structured_config
        self.separated_paths = separated_paths
        self.modality_mapping = self._load_modality_mapping()
    
    def _load_modality_mapping(self):
        """DICOM 모달리티 매핑 JSON 파일 로드"""
        request = self.structured_config['request']
        filename = f"{request['systemId']}_{request['projectName']}_{request['projectSeq']}_{request['orgId']}_dicom_modality.json"
        mapping_path = os.path.join(self.global_vars['dicom_modality'], filename)
        
        try:
            with open(mapping_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.error(f"DICOM modality mapping file not found: {mapping_path}")
            return {}
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON format in DICOM modality mapping: {mapping_path}")
            return {}
    
    def _get_dicom_metadata(self, dicom_path):
        """DICOM 파일에서 모든 메타데이터 추출"""
        try:
            ds = pydicom.dcmread(dicom_path, stop_before_pixels=True)
            metadata = {}
            
            # 모든 DICOM 태그를 정규화된 키로 변환하여 저장
            for elem in ds:
                if hasattr(elem, 'keyword') and elem.keyword and elem.value:
                    # 공백 제거 → 특수문자 제거 → 소문자 변환
                    key = remove_special_chars(remove_all_whitespace(elem.keyword)).lower()
                    metadata[key] = str(elem.value)
            
            return metadata
        except Exception as e:
            logger.error(f"Error reading DICOM file {dicom_path}: {e}")
            return {}
    
    def _determine_modality(self, dicom_metadata):
        """DICOM 메타데이터를 기반으로 모달리티 판단"""
        for modality, rules in self.modality_mapping.items():
            for rule in rules:
                # JSON의 각 키에 대해 확인
                for json_key, expected_values in rule.items():
                    # JSON 키를 정규화: 공백 제거 → 특수문자 제거 → 소문자 변환
                    normalized_key = remove_special_chars(remove_all_whitespace(json_key)).lower()
                    
                    # 메타데이터에 해당 키가 있는지 확인
                    if normalized_key in dicom_metadata:
                        dicom_value = dicom_metadata[normalized_key]
                        
                        # 값이 예상 값 목록에 있는지 확인
                        if dicom_value in expected_values:
                            return modality
        
        return 'unknown'
    
    def get_path_mapping(self):
        """각 separated_path의 DICOM 파일들을 분석하여 경로 매핑 생성"""
        path_mapping = {}
        
        for set_path in self.separated_paths:
            # DICOM 파일들 찾기 (JSON 파일 제외)
            dicom_files = []
            for root, dirs, files in os.walk(set_path):
                for file in files:
                    # JSON 파일 제외, DICOM 파일만 포함
                    if not file.lower().endswith('.json'):
                        if file.lower().endswith('.dcm') or not '.' in file:
                            dicom_files.append(os.path.join(root, file))
            
            if not dicom_files:
                logger.warning(f"No DICOM files found in {set_path}")
                continue
            
            # 모든 DICOM 파일의 모달리티가 동일한지 확인
            modalities = set()
            for dicom_file in dicom_files:
                metadata = self._get_dicom_metadata(dicom_file)
                modality = self._determine_modality(metadata)
                modalities.add(modality)
            
            # 모달리티가 하나가 아니면 에러
            if len(modalities) > 1:
                raise ValueError(f"Multiple modalities found in {set_path}: {modalities}. Each separated_path should contain only one modality.")
            
            # 하나의 모달리티만 있는 경우
            final_modality = modalities.pop() if modalities else 'unknown'
            path_mapping[set_path] = final_modality
        
        return path_mapping


class ParrecMapper:
    def __init__(self, global_vars, structured_config, separated_paths):
        self.global_vars = global_vars
        self.structured_config = structured_config
        self.separated_paths = separated_paths
        self.modality_mapping = self._load_modality_mapping()
    
    def _load_modality_mapping(self):
        """PARREC 모달리티 매핑 JSON 파일 로드"""
        request = self.structured_config['request']
        filename = f"{request['systemId']}_{request['projectName']}_{request['projectSeq']}_{request['orgId']}_parrec_modality.json"
        mapping_path = os.path.join(self.global_vars['parrec_modality'], filename)
        
        try:
            with open(mapping_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.error(f"PARREC modality mapping file not found: {mapping_path}")
            return {}
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON format in PARREC modality mapping: {mapping_path}")
            return {}
    
    def _get_par_metadata(self, par_path):
        """PAR 파일에서 메타데이터 추출"""
        try:
            metadata = {}
            
            with open(par_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
                # PAR 파일의 각 라인을 파싱
                for line in content.split('\n'):
                    line = line.strip()
                    if ':' in line:
                        # 콜론으로 분리하여 키-값 추출
                        parts = line.split(':', 1)
                        if len(parts) == 2:
                            # 키 정규화: 공백 제거 → 특수문자 제거 → 소문자 변환
                            key = remove_special_chars(remove_all_whitespace(parts[0].strip())).lower()
                            value = parts[1].strip()
                            metadata[key] = value
            
            return metadata
        except Exception as e:
            logger.error(f"Error reading PAR file {par_path}: {e}")
            return {}
    
    def _determine_modality(self, par_metadata):
        """PAR 메타데이터를 기반으로 모달리티 판단"""
        for modality, rules in self.modality_mapping.items():
            for rule in rules:
                # JSON의 각 키에 대해 확인
                for json_key, expected_values in rule.items():
                    # JSON 키를 정규화: 공백 제거 → 특수문자 제거 → 소문자 변환
                    normalized_key = remove_special_chars(remove_all_whitespace(json_key)).lower()
                    
                    # 메타데이터에 해당 키가 있는지 확인
                    if normalized_key in par_metadata:
                        par_value = par_metadata[normalized_key]
                        
                        # 값이 예상 값 목록에 있는지 확인
                        if par_value in expected_values:
                            return modality
        
        return 'unknown'
    
    def get_path_mapping(self):
        """각 separated_path의 PAR/REC 파일들을 분석하여 경로 매핑 생성"""
        path_mapping = {}
        
        for set_path in self.separated_paths:
            # PAR 파일들 찾기 (JSON 파일 제외)
            par_files = []
            for root, dirs, files in os.walk(set_path):
                for file in files:
                    # JSON 파일 제외, PAR 파일만 포함
                    if file.lower().endswith('.par') and not file.lower().endswith('.json'):
                        par_files.append(os.path.join(root, file))
            
            if not par_files:
                logger.warning(f"No PAR files found in {set_path}")
                continue
            
            # PAR 파일은 보통 하나만 있지만, 여러 개 있을 경우 모달리티 일치 확인
            modalities = set()
            for par_file in par_files:
                metadata = self._get_par_metadata(par_file)
                modality = self._determine_modality(metadata)
                modalities.add(modality)
            
            # 모달리티가 하나가 아니면 에러 (안전장치)
            if len(modalities) > 1:
                raise ValueError(f"Multiple modalities found in {set_path}: {modalities}. Each separated_path should contain only one modality.")
            
            # 하나의 모달리티만 있는 경우
            final_modality = modalities.pop() if modalities else 'unknown'
            path_mapping[set_path] = final_modality
        
        return path_mapping


class NiftiMapper:
    def __init__(self, global_vars, structured_config, separated_paths):
        self.global_vars = global_vars
        self.structured_config = structured_config
        self.separated_paths = separated_paths
    
    def get_path_mapping(self):
        """NIFTI 파일명에서 모달리티 추출"""
        path_mapping = {}
        
        for set_path in self.separated_paths:
            # NIFTI 파일들 찾기 (JSON 파일 제외)
            nifti_files = []
            for root, dirs, files in os.walk(set_path):
                for file in files:
                    # JSON 파일 제외, NIFTI 파일만 포함
                    if file.lower().endswith(('.nii', '.nii.gz')) and not file.lower().endswith('.json'):
                        nifti_files.append(os.path.join(root, file))
            
            if not nifti_files:
                logger.warning(f"No NIFTI files found in {set_path}")
                continue
            
            # 모든 NIFTI 파일에서 모달리티 추출하여 일치 확인
            modalities = set()
            for nifti_file in nifti_files:
                filename = os.path.basename(nifti_file)
                modality = self._extract_modality_from_filename(filename)
                modalities.add(modality)
            
            # 모달리티가 하나가 아니면 에러
            if len(modalities) > 1:
                raise ValueError(f"Multiple modalities found in {set_path}: {modalities}. Each separated_path should contain only one modality.")
            
            # 하나의 모달리티만 있는 경우
            final_modality = modalities.pop() if modalities else 'unknown'
            path_mapping[set_path] = final_modality
        
        return path_mapping
    
    def _extract_modality_from_filename(self, filename):
        """NIFTI 파일명에서 모달리티 추출"""
        try:
            # 확장자 제거
            name_without_ext = filename
            if filename.endswith('.nii.gz'):
                name_without_ext = filename[:-7]
            elif filename.endswith('.nii'):
                name_without_ext = filename[:-4]
            
            # 언더스코어로 분리
            parts = name_without_ext.split('_')
            
            if len(parts) < 4:
                logger.error(f"Invalid NIFTI filename format: {filename}")
                return 'unknown'
            
            # 마지막 부분이 숫자인지 확인
            last_part = parts[-1]
            if last_part != '0001':
                raise ValueError(f"Invalid number in NIFTI filename {filename}. Expected '0001', got '{last_part}'")
            
            # 마지막에서 두 번째 부분이 모달리티
            modality = parts[-2]
            return modality
            
        except Exception as e:
            logger.error(f"Error extracting modality from filename {filename}: {e}")
            return 'unknown'