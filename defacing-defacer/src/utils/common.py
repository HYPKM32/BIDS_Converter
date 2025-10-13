#/BDSP/defacer_app/src/utils/common.py
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
