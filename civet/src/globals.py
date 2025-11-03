import configparser
# config 파일 읽기
config = configparser.ConfigParser()
config.read('/BDSP/civet_app/src/config.ini')

# DEFAULT 섹션
MAX_WORKERS = int(config['DEFAULT']['MAX_WORKERS'])
SUB_WORKERS = int(config['DEFAULT']['SUB_WORKERS'])
EVENT_DIR = config['DEFAULT']['EVENT_DIR']
WORKING_DIR = config['DEFAULT']['WORKING_DIR']
UPLOAD_DIR = config['DEFAULT']['UPLOAD_DIR']
LOG_FILENAME = config['DEFAULT']['LOG_FILENAME']
BACKUP_DIR = config['DEFAULT']['BACKUP_DIR']
ERROR_DIR = config['DEFAULT']['ERROR_DIR']
PROCESS = config['DEFAULT']['PROCESS']
PACKAGE = config['DEFAULT']['PACKAGE']
COMMAND = config['DEFAULT']["COMMAND"]
MNC2NII = config['DEFAULT']["MNC2NII"]
NII2MNC = config['DEFAULT']["NII2MNC"]
GUNZIP = config['DEFAULT']["GUNZIP"]
GZIP = config['DEFAULT']["GZIP"]