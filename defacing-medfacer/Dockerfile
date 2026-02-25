FROM nvidia/cuda:11.7.1-cudnn8-devel-ubuntu22.04
ENV DEBIAN_FRONTEND=noninteractive

RUN mkdir -p /BDSP/medfacer_app \
             /BDSP/medfacer_lib \
             /BDSP/interfaces/event \
             /BDSP/interfaces/working \
             /BDSP/interfaces/backup \
             /BDSP/interfaces/error

# 1. System packages
RUN apt-get update && apt-get install -y \
    python3 \
    python3-dev \
    python3-pip \
    git \
    wget \
    curl \
    ca-certificates \
    gnupg \
    build-essential \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# 2. Node.js 20.x (LTS)
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m pip install --upgrade pip

# 3. PyTorch (CUDA 11.7)
RUN pip3 install --no-cache-dir \
    torch==2.0.1+cu117 \
    torchvision==0.15.2+cu117 \
    torchaudio==2.0.2+cu117 \
    --index-url https://download.pytorch.org/whl/cu117

# 4. All pinned dependencies
COPY requirements.txt /tmp/requirements.txt
RUN pip3 install --no-cache-dir -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt

# 5. DeepBET (brain extraction) -> /BDSP/medfacer_lib
RUN git clone https://github.com/wwu-mmll/deepbet.git /BDSP/medfacer_lib/deepbet \
    && pip3 install --no-cache-dir /BDSP/medfacer_lib/deepbet

# 6. MedYOLO (3D YOLO detection) -> /BDSP/medfacer_lib
RUN git clone https://github.com/JDSobek/MedYOLO.git /BDSP/medfacer_lib/MedYOLO

WORKDIR /BDSP

# 7. Claude Code
RUN npm install -g @anthropic-ai/claude-code

WORKDIR /BDSP/medfacer_app
CMD ["/bin/bash"]
