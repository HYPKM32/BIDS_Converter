#/BDSP/bids_app/src/utils/common.py
import os
import json
import re
import shutil
import gzip
from pathlib import Path



def camel2snake(name: str) -> str:
    """camelCase를 snake_case로 변환"""
    s1 = re.sub('([A-Z]+)([A-Z][a-z])', r'\1_\2', name)
    s2 = re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1)
    return s2.lower()


import os
import json

def bdsp_walk(target_folder: str, output_filename: str = None):
    """폴더를 스캔하여 파일 경로를 JSON으로 저장
       단, 'bdsp'로 시작하고 '.json' 확장자인 파일은 제외"""
    
    # output_filename이 None이면 target_folder 안에 기본 파일명으로 생성
    if output_filename is None:
        output_filename = os.path.join(target_folder, "bdsp_file_list.json")
    
    file_paths = []
    index = 1
    
    for root, dirs, files in os.walk(target_folder):
        for file in files:
            # 제외 조건: 파일명이 'bdsp'로 시작하고 .json으로 끝나는 경우
            if file.lower().startswith("bdsp") and file.lower().endswith(".json"):
                continue

            file_path = os.path.join(root, file)
            file_paths.append({
                "index": index,
                "file_path": file_path
            })
            index += 1
    
    result = {"path": file_paths}
    
    with open(output_filename, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    return result


def zero_fill(num) -> str:
    """정수나 문자열을 두자리 zerofilling한 후 string으로 변경"""
    try:
        return f"{int(num):02d}"
    except ValueError:
        return str(num).zfill(2)  # 숫자가 아닌 문자열은 그냥 zfill 사용


def bdsp_path_maker(path: str) -> bool:
    """경로가 존재하는지 확인하고, 존재하지 않으면 폴더 생성"""
    if os.path.exists(path):
        print(f"경로가 이미 존재합니다: {path}")
        return False  # 이미 존재하므로 생성하지 않음
    else:
        try:
            os.makedirs(path, exist_ok=True)
            print(f"폴더를 생성했습니다: {path}")
            return True  # 새로 생성함
        except OSError as e:
            print(f"폴더 생성 중 오류 발생: {e}")
            return False
        
def remove_all_whitespace(text):
    return re.sub(r'\s+', '', text)

def separated_walk(separated_path, json_output_path):
    """분리된 파일들을 스캔하여 파일명의 index 기준으로 JSON 생성
    
    파일명 패턴: item_{set_id}_{index} 또는 item_{set_id}_{index}{ext}
    """
    from pathlib import Path
    import re
    import json
    
    separated_path = Path(separated_path)
    
    if not separated_path.exists():
        raise FileNotFoundError(f"경로를 찾을 수 없습니다: {separated_path}")
    
    if not separated_path.is_dir():
        raise NotADirectoryError(f"디렉토리가 아닙니다: {separated_path}")
    
    entries = []
    # 확장자가 있을 수도, 없을 수도 있는 패턴
    pattern = re.compile(r'item_.*?_(\d+)(?:\.|$)')
    
    for file_path in separated_path.iterdir():
        if file_path.is_file() and not file_path.name.endswith('.json'):
            match = pattern.search(file_path.name)
            if match:
                index = int(match.group(1))
                entries.append({
                    "index": index,
                    "file_path": str(file_path)
                })
    
    if not entries:
        print(f"경고: 패턴에 맞는 파일을 찾지 못했습니다.")
    
    entries.sort(key=lambda x: x["index"])
    
    json_output_path = Path(json_output_path)
    json_output_path.parent.mkdir(parents=True, exist_ok=True)
    
    data = {"path": entries}
    with open(json_output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"총 {len(entries)}개 파일 처리 완료")
    return data
        
def remove_special_chars(text: str) -> str:
    """
    입력된 문자열에서 알파벳, 숫자, '_', '-'를 제외한
    모든 특수문자를 제거합니다.
    
    Args:
        text (str): 입력 문자열
    
    Returns:
        str: 특수문자가 제거된 문자열
    """
    return re.sub(r'[^a-zA-Z0-9_-]', '', text)


def compress_nii_gz(nii_path: str) -> str:
    """
    .nii 파일을 gzip으로 압축하여 .nii.gz로 저장한 뒤 원본 .nii는 삭제
    
    Args:
        nii_path (str): 입력 .nii 파일 경로
    
    Returns:
        str: 압축된 .nii.gz 파일 경로
    """
    nii_file = Path(nii_path)
    if not nii_file.exists():
        raise FileNotFoundError(f"파일이 존재하지 않습니다: {nii_file}")
    if nii_file.suffix != ".nii":
        raise ValueError("입력 파일은 반드시 .nii 확장자여야 합니다.")
    
    gz_file = nii_file.with_suffix(".nii.gz")
    
    # gzip 압축
    with open(nii_file, 'rb') as f_in, gzip.open(gz_file, 'wb') as f_out:
        shutil.copyfileobj(f_in, f_out)
    
    # 원본 파일 삭제
    nii_file.unlink()
    
    return str(gz_file)