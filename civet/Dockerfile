FROM mcin/civet:2.1.1

ENV DEBIAN_FRONTEND=noninteractive

# --- 기본 유틸 및 필수 패키지 설치
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    minc-tools \
    python3-pip \
    python3-dev \
    python3-setuptools \
    git \
    curl \
    nano \
    vim \
    procps \
    && ln -s /usr/bin/pip3 /usr/bin/pip \
    && rm -rf /var/lib/apt/lists/*

# --- Python 패키지 설치 (BDSP 보조 스크립트용)
RUN pip3 install --no-cache-dir \
    numpy \
    pandas \
    nibabel \
    pyyaml \
    simplejson \
    tqdm

# --- CIVET 작업 디렉토리 구성
RUN mkdir -p /BDSP/civet_app \
    /BDSP/interfaces/event \
    /BDSP/interfaces/working \
    /BDSP/interfaces/backup \
    /BDSP/interfaces/error

# --- 환경변수 설정
ENV CIVET_VERSION=2.1.1

WORKDIR /BDSP/civet_app

CMD ["/bin/bash"]
