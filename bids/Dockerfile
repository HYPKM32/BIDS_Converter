#/home/mool/dev/bids/Dockerfile

# dcm2niix를 실행할 수 있는 Docker 환경
FROM ubuntu:22.04

# 비대화형 모드로 설정 (패키지 설치 시 프롬프트 방지)
ENV DEBIAN_FRONTEND=noninteractive

RUN mkdir -p /BDSP/bids_app
RUN mkdir -p /BDSP/bids_lib
RUN mkdir -p /BDSP/interfaces/upload
RUN mkdir -p /BDSP/interfaces/event
RUN mkdir -p /BDSP/interfaces/working
RUN mkdir -p /BDSP/interfaces/backup
RUN mkdir -p /BDSP/interfaces/error
RUN mkdir -p /BDSP/interfaces/flag

#preprocessing flag folder
RUN mkdir -p /BDSP/interfaces/flag/defacing/defacer
RUN mkdir -p /BDSP/interfaces/flag/defacing/medyolo_defacer
RUN mkdir -p /BDSP/interfaces/flag/canonical/canonical
RUN mkdir -p /BDSP/interfaces/flag/T1w_preprocessing/civet


# 시스템 업데이트 및 필수 패키지 설치
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    unzip \
    build-essential \
    cmake \
    git \
    pkg-config \
    python3 \
    python3-pip \
    python3-dev \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# dcm2niix 최신 버전 다운로드 및 컴파일
WORKDIR /BDSP/bids_lib
RUN git clone https://github.com/rordenlab/dcm2niix.git && \
    cd dcm2niix && \
    mkdir build && \
    cd build && \
    cmake -DZLIB_IMPLEMENTATION=Cloudflare -DUSE_JPEGLS=ON -DUSE_OPENJPEG=ON .. && \
    make && \
    make install

# Python 패키지 설치
RUN pip3 install --no-cache-dir pydicom opencv-python nibabel

# 작업 디렉토리 설정
WORKDIR /BDSP/bids_app

# dcm2niix가 PATH에 있는지 확인
RUN dcm2niix -h

# 기본 명령어
CMD ["/bin/bash"]