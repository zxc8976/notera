FROM mambaorg/micromamba:1.5.7 AS micromamba_stage

# micromamba 階段僅提供 micromamba 可執行檔，避免 GLIBC 不匹配

FROM nvidia/cuda:12.1.0-cudnn8-runtime-ubuntu22.04

# 可選代理（建置時可傳入）：
ARG APT_HTTP_PROXY=""
ARG APT_HTTPS_PROXY=""
ARG HTTP_PROXY=""
ARG HTTPS_PROXY=""
ARG NO_PROXY=""

# GPU/CPU 切換參數：預設僅用 CPU 版 Paddle 以避免龐大 GPU 套件卡住
ARG USE_PADDLE_GPU="false"

# 安裝系統依賴 (ffmpeg + build tools + runtime libraries) - 合併為單一層
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
       ffmpeg \
       build-essential \
       gcc \
       g++ \
       make \
       pkg-config \
       libgl1 \
       libglib2.0-0 \
       libcublas11 \
       libcublaslt11 \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# 注入 micromamba 並建立 Python 環境（不依賴 apt）
COPY --from=micromamba_stage /bin/micromamba /usr/local/bin/micromamba
ENV MAMBA_ROOT_PREFIX=/opt/conda
ENV MAMBA_NO_RC=true
# 讓 micromamba/pip 在建置時尊重代理（如有提供）
ENV http_proxy=${HTTP_PROXY} \
    https_proxy=${HTTPS_PROXY} \
    no_proxy=${NO_PROXY} \
    HTTP_PROXY=${HTTP_PROXY} \
    HTTPS_PROXY=${HTTPS_PROXY} \
    NO_PROXY=${NO_PROXY}
SHELL ["bash", "-lc"]
RUN micromamba create -y -n app -c conda-forge python=3.10 pip \
    && micromamba clean -a -y
ENV PATH=/opt/conda/envs/app/bin:$PATH
RUN python3 -V && pip3 -V

# 安裝 CUDA 12.1 wheel 的 torch/torchvision/torchaudio
RUN pip3 install --no-cache-dir \
    torch==2.1.0 torchvision==0.16.0 torchaudio==2.1.0 --index-url https://download.pytorch.org/whl/cu121

# 安裝 Python 基礎依賴 + 清理 pip cache
RUN pip3 install --no-cache-dir \
    fastapi==0.104.1 \
    python-multipart==0.0.6 \
    pyyaml==6.0.2 \
    numpy==1.24.3 \
    scikit-learn==1.3.0 \
    matplotlib==3.7.2 \
    httpx==0.25.2 \
    requests==2.31.0 \
    pydantic==2.5.0 \
    pynvml>=11.5.0 \
    && rm -rf /root/.cache/pip

# 移除重複的 build tools 安裝 (已在上方合併)

# 安裝 PaddlePaddle：可選 GPU 或 CPU 版本 + 清理 pip cache
ARG PADDLE_VERSION=2.6.2
RUN if [ "$USE_PADDLE_GPU" = "true" ]; then \
      pip3 install --no-cache-dir paddlepaddle-gpu==${PADDLE_VERSION} -f https://www.paddlepaddle.org.cn/whl/linux/gpu/ && \
      ln -sf /usr/lib/x86_64-linux-gnu/libcudnn* /usr/local/cuda/lib64/ ; \
    else \
      pip3 install --no-cache-dir paddlepaddle==${PADDLE_VERSION} ; \
    fi \
    && rm -rf /root/.cache/pip

# 安裝 AI 相關依賴 + 清理 pip cache
RUN pip3 install --no-cache-dir \
    "paddleocr>=3.3.0" \
    "paddlex[ocr]>=3.3.0" \
    scenedetect==0.6.2 \
    webrtcvad==2.0.10 \
    opencv-python-headless==4.8.0.76 \
    Pillow>=9.0.0 \
    pillow-heif>=0.10.0 \
    aiofiles>=23.0.0 \
    ftfy \
    regex \
    tqdm \
    openai-whisper \
    ffmpeg-python \
    && rm -rf /root/.cache/pip

# 設置工作目錄
WORKDIR /app

# 複製 requirements.txt 並安裝依賴
COPY source/backend/app/requirements.txt /app/requirements.txt
# 避免覆蓋上方已安裝的 CUDA 12.1 版 torch/torchvision/torchaudio
# 將 requirements.txt 中的 torch/torchvision/torchaudio 行過濾掉再安裝
RUN python - <<'PY'
from pathlib import Path
src = Path("/app/requirements.txt").read_text(encoding="utf-8").splitlines()
filtered = []
for line in src:
    stripped = line.strip()
    if stripped.startswith(("torch", "torchvision", "torchaudio", "paddlepaddle")):
        continue
    filtered.append(line.rstrip())
Path("/app/requirements.no-torch.txt").write_text("\n".join(filtered) + "\n", encoding="utf-8")
PY
RUN pip3 install --no-cache-dir -r /app/requirements.no-torch.txt \
    && rm -rf /root/.cache/pip

# 複製專案文件
COPY . /app/

# 創建必要的目錄
RUN mkdir -p /app/data/videos /app/data/images /app/var/output /app/var/log /app/var/notes /app/source/frontend/public/images /app/temp /app/data/models/paddleocr_vl /app/data/models/paddleocr_vl/PP-DocLayoutV2

# 設置目錄權限
RUN chmod -R 755 /app/data/videos /app/data/images /app/var/output /app/var/log /app/var/notes /app/source/frontend/public/images /app/temp /app/data/models/paddleocr_vl

# 設置環境變量
ENV PYTHONPATH=/app
ENV CUDA_VISIBLE_DEVICES=0
ENV NVIDIA_VISIBLE_DEVICES=all
ENV NVIDIA_DRIVER_CAPABILITIES=compute,utility
ENV LD_LIBRARY_PATH=/usr/local/cuda/lib64:/usr/local/cuda/extras/CUPTI/lib64:/usr/lib/x86_64-linux-gnu:$LD_LIBRARY_PATH
ENV NOTEGEN_VERSION="1.0.2"
ENV NOTEGEN_ROOT="/app"
ENV UI_FIXED="true"
ENV PADDLEOCR_VL_MODEL_ROOT="/app/data/models/paddleocr_vl"
ENV PADDLEOCR_VL_LAYOUT_DIR="/app/data/models/paddleocr_vl/PP-DocLayoutV2"
ENV QWEN_VL_MODEL="qwen3-vl:235b-cloud"
ENV OLLAMA_BASE="http://ollama_local:11434"
ENV OLLAMA_FALLBACK_BASE="http://ollama_local:11434"
ENV NOTE_HEADINGS_VARIANT="accented"

# 限制數值庫/BLAS執行緒，降低過熱與搶資源
ENV OMP_NUM_THREADS=2
ENV OPENBLAS_NUM_THREADS=2
ENV MKL_NUM_THREADS=2
ENV NUMEXPR_NUM_THREADS=2
ENV UVICORN_WORKERS=1
ENV TOKENIZERS_PARALLELISM=false

# 將臨時目錄指向容器內磁碟，避免落在小容量 tmpfs
ENV TMPDIR=/app/temp

# 健康檢查（使用 Python，一行命令，避免 curl 依賴）
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD ["python3","-c","import sys,urllib.request;url='http://localhost:8000/api/version';\nimport urllib.error;\n\ntry:\n r=urllib.request.urlopen(url,timeout=5); sys.exit(0 if r.status==200 else 1)\nexcept Exception:\n sys.exit(1)"]

# 暴露端口
EXPOSE 8000

# 設置入口點（生產模式禁用 --reload 以避免檔案變更引發重載斷線）
ENTRYPOINT ["uvicorn", "source.backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]



