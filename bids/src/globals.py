#/BDSP/bids_app/src/globals.py
import configparser
# config 파일 읽기
config = configparser.ConfigParser()
config.read('/BDSP/bids_app/src/config.ini')

# DEFAULT 섹션
MAX_WORKERS = int(config['DEFAULT']['MAX_WORKERS'])
EVENT_DIR = config['DEFAULT']['EVENT_DIR']
WORKING_DIR = config['DEFAULT']['WORKING_DIR']
UPLOAD_DIR = config['DEFAULT']['UPLOAD_DIR']
BACKUP_DIR = config['DEFAULT']['BACKUP_DIR']
ERROR_DIR = config['DEFAULT']['ERROR_DIR']
LOG_FILENAME = config['DEFAULT']['LOG_FILENAME']
MAGNETIC_STRENGTH_FIELD = config['DEFAULT']['MAGNETIC_STRENGTH_FIELD']

# MODALITY 섹션
DICOM_MODALITY = config['MODALITY']['DICOM_MODALITY']
NIFTI_MODALITY = config['MODALITY']['NIFTI_MODALITY']
PARREC_MODALITY = config['MODALITY']['PARREC_MODALITY']
SUFFIX_MAP = config['MODALITY']['SUFFIX_MAP']

# FLAG 섹션
FLAG_DIR = config['FLAG']['FLAG_DIR']
