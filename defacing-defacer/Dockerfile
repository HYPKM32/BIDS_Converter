#/home/mool/dev/defacing-defacer/Dockerfile
FROM nvidia/cuda:11.7.1-cudnn8-devel-ubuntu22.04

# 비대화형 모드로 설정 (패키지 설치 시 프롬프트 방지)
ENV DEBIAN_FRONTEND=noninteractive

# 디렉토리 생성
RUN mkdir -p /BDSP/defacer_app \
    /BDSP/defacer_lib \
    /BDSP/interfaces/event \
    /BDSP/interfaces/working \
    /BDSP/interfaces/backup \
    /BDSP/interfaces/error 


# 시스템 업데이트 및 기본 패키지 설치
RUN apt-get update && apt-get install -y \
    python3 \
    python3-dev \
    python3-pip \
    git \
    wget \
    curl \
    build-essential \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# pip 업그레이드
RUN python3 -m pip install --upgrade pip

# Defacer 라이브러리 클론
WORKDIR /BDSP/defacer_lib
RUN git clone https://github.com/yeonuk-Jeong/Defacer.git .

# Python 패키지 설치 (Defacer 요구사항)
RUN pip3 install --no-cache-dir \
    tensorflow==2.8.4 \
    numpy==1.24.4 \
    scipy==1.11.1 \
    h5py==3.9.0 \
    scikit-image==0.20.0 \
    scikit-learn==1.1.0 \
    nibabel==5.0.0 \
    pydicom==2.3.1 \
    matplotlib==3.7.1



# 작업 디렉토리 설정
WORKDIR /BDSP/defacer_app

# 기본 명령어
CMD ["/bin/bash"]