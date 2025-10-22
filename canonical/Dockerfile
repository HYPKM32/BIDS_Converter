FROM nvidia/cuda:11.7.1-cudnn8-devel-ubuntu22.04

# 비대화형 모드로 설정 (패키지 설치 시 프롬프트 방지)
ENV DEBIAN_FRONTEND=noninteractive

# 기본 패키지 업데이트 및 Python 설치
RUN apt-get update && apt-get install -y \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Python 패키지 설치
RUN pip install --no-cache-dir \
    nibabel==5.3.2 \
    nipype==1.10.0

# 디렉토리 생성
RUN mkdir -p /BDSP/canonical_app \
    /BDSP/interfaces/event \
    /BDSP/interfaces/working \
    /BDSP/interfaces/backup \
    /BDSP/interfaces/error

# 작업 디렉토리 설정
WORKDIR /BDSP/canonical_app

# 기본 명령어
CMD ["/bin/bash"]