import json
import logging
import os
import pydicom
from pathlib import Path
from utils.common import remove_all_whitespace, remove_special_chars

logger = logging.getLogger(__name__)

class DicomTracerMapper:
    def __init__(self, global_vars, structured_config, separated_paths):
        self.global_vars = global_vars
        self.structured_config = structured_config
        self.separated_paths = separated_paths
        self.tracer_mapping = self._load_tracer_mapping()

    def _load_tracer_mapping(self):
        """DICOM tracer 매핑 JSON 파일 로드"""
        request = self.structured_config['request']
        filename = f"{request['systemId']}_{request['projectName']}_{request['projectSeq']}_{request['orgId']}_dicom_tracer.json"
        mapping_path = os.path.join(self.global_vars['dicom_modality'], filename)

        logger.info(f"Loading tracer mapping from: {mapping_path}")

        try:
            with open(mapping_path, 'r', encoding='utf-8') as f:
                mapping = json.load(f)
                logger.info(f"Tracer mapping loaded successfully. Tracers: {list(mapping.keys())}")
                return mapping
        except FileNotFoundError:
            logger.error(f"DICOM tracer mapping file not found: {mapping_path}")
            return {}
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON format in DICOM tracer mapping: {mapping_path}")
            return {}

    def _get_dicom_metadata(self, dicom_path):
        """DICOM 파일에서 모든 메타데이터 추출 (태그와 keyword 모두 저장)"""
        try:
            ds = pydicom.dcmread(dicom_path, stop_before_pixels=True)
            metadata = {}

            for elem in ds:
                if elem.value:
                    original_value = str(elem.value)
                    normalized_value = remove_special_chars(remove_all_whitespace(original_value)).lower()

                    tag_str = f"{elem.tag.group:04x},{elem.tag.element:04x}"
                    normalized_tag = remove_special_chars(remove_all_whitespace(tag_str)).lower()
                    metadata[normalized_tag] = normalized_value

                    if hasattr(elem, 'keyword') and elem.keyword:
                        normalized_keyword = remove_special_chars(remove_all_whitespace(elem.keyword)).lower()
                        metadata[normalized_keyword] = normalized_value

                        if elem.keyword in ['SeriesDescription', 'Radiopharmaceutical']:
                            logger.info(f"DICOM {elem.keyword} ({tag_str}): '{original_value}' -> '{normalized_value}'")

            return metadata
        except Exception as e:
            logger.error(f"Error reading DICOM file {dicom_path}: {e}")
            return {}

    def _determine_tracer(self, dicom_metadata):
        """DICOM 메타데이터를 기반으로 tracer 판단 (인덱스가 높은 것이 우선순위)"""
        logger.debug(f"Starting tracer determination with {len(dicom_metadata)} metadata keys")

        for tracer, rules in reversed(list(self.tracer_mapping.items())):
            for rule in reversed(rules):
                for json_key, expected_values in rule.items():
                    normalized_key = remove_special_chars(remove_all_whitespace(json_key)).lower()

                    if normalized_key in dicom_metadata:
                        dicom_value = dicom_metadata[normalized_key]
                        logger.debug(f"Checking {tracer} - key '{json_key}' (normalized: '{normalized_key}')")
                        logger.debug(f"  DICOM value: '{dicom_value}'")

                        for expected_value in expected_values:
                            normalized_expected = remove_special_chars(
                                remove_all_whitespace(str(expected_value))
                            ).lower()

                            if dicom_value == normalized_expected:
                                logger.info(f"✓ Tracer matched: {tracer} (key: {json_key}, value: {expected_value})")
                                return tracer

        logger.warning("No tracer matched, returning 'unknown'")
        return 'unknown'

    def get_path_mapping(self):
        """각 separated_path의 DICOM 파일들을 분석하여 tracer 매핑 생성"""
        path_mapping = {}

        for set_path in self.separated_paths:
            dicom_files = []
            for root, dirs, files in os.walk(set_path):
                for file in files:
                    if not file.lower().endswith('.json'):
                        if file.lower().endswith('.dcm') or not '.' in file:
                            dicom_files.append(os.path.join(root, file))

            if not dicom_files:
                logger.warning(f"No DICOM files found in {set_path}")
                continue

            tracers = set()
            for dicom_file in dicom_files:
                metadata = self._get_dicom_metadata(dicom_file)
                tracer = self._determine_tracer(metadata)
                tracers.add(tracer)

            # unknown 제외
            tracers.discard('unknown')

            # tracer 판단
            if len(tracers) == 0:
                final_tracer = 'unknown'
            elif len(tracers) == 1:
                final_tracer = tracers.pop()
            else:
                logger.error(f"Conflict tracers detected in {set_path}: {tracers}")
                final_tracer = 'conflict'

            path_mapping[set_path] = final_tracer

        return path_mapping