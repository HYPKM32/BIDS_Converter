FROM mcin/civet:2.1.1

ENV DEBIAN_FRONTEND=noninteractive
ENV CIVET_VERSION=2.1.1

# --- 기본 유틸 및 SSL 인증서 설치
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        minc-tools \
        git \
        curl \
        ca-certificates \
        nano \
        vim \
        procps \
        zlib1g-dev \
        libncurses5-dev \
        libgdbm-dev \
        libnss3-dev \
        libssl-dev \
        libreadline-dev \
        libffi-dev \
        libsqlite3-dev && \
    update-ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# --- Python 3.9 빌드 및 설치
RUN cd /usr/src && \
    curl -O https://www.python.org/ftp/python/3.9.19/Python-3.9.19.tgz && \
    tar -xf Python-3.9.19.tgz && \
    cd Python-3.9.19 && \
    ./configure --enable-optimizations && \
    make -j"$(nproc)" && \
    make altinstall && \
    curl -sS https://bootstrap.pypa.io/get-pip.py | /usr/local/bin/python3.9 && \
    ln -sf /usr/local/bin/python3.9 /usr/bin/python3 && \
    ln -sf /usr/local/bin/pip /usr/bin/pip3

# --- Python 패키지 설치
RUN pip3 install --no-cache-dir numpy pandas nibabel pyyaml simplejson tqdm

# --- CIVET 작업 디렉토리 구성
RUN mkdir -p /BDSP/civet_app \
    /BDSP/interfaces/event \
    /BDSP/interfaces/working \
    /BDSP/interfaces/backup \
    /BDSP/interfaces/error \
    /BDSP/interfaces/tmp

WORKDIR /BDSP/civet_app
CMD ["/bin/bash"]
