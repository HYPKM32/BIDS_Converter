#/home/mool/dev/bids/Dockerfile
FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive

# 디렉토리 구조
RUN mkdir -p /BDSP/bids_app \
    /BDSP/bids_lib \
    /BDSP/interfaces/upload \
    /BDSP/interfaces/event \
    /BDSP/interfaces/working \
    /BDSP/interfaces/backup \
    /BDSP/interfaces/error \
    /BDSP/interfaces/flag/defacing/defacer \
    /BDSP/interfaces/flag/defacing/medfacer \
    /BDSP/interfaces/flag/canonical/canonical \
    /BDSP/interfaces/flag/T1w_preprocessing/civet \
    /BDSP/interfaces/flag/T1w_preprocessing/freesurfer 
# 시스템 업데이트 및 Python 준비
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

# pip 최신화
RUN pip install --upgrade pip setuptools wheel

# dcm2niix 설치
WORKDIR /BDSP/bids_lib
RUN git clone https://github.com/rordenlab/dcm2niix.git && \
    cd dcm2niix && \
    mkdir build && \
    cd build && \
    cmake -DZLIB_IMPLEMENTATION=Cloudflare -DUSE_JPEGLS=ON -DUSE_OPENJPEG=ON .. && \
    make && make install

# Python 패키지 설치 (핵심만 버전 고정)
RUN pip3 install --no-cache-dir \
    nibabel==5.3.2 \
    numpy==2.2.6 \
    pydicom==3.0.1 \
    opencv-python \
    uvicorn \
    fastapi \
    sse-starlette \
    python-multipart 

WORKDIR /BDSP/bids_app

RUN dcm2niix -h

ENV PORT=8896

EXPOSE $PORT

CMD ["/bin/bash"]
