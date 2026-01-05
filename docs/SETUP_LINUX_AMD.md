# Trenton 安装指南 - Linux + AMD Radeon 8000S

本文档介绍如何在 Linux 系统上使用 AMD Radeon 8000S (8050S/8060S) 显卡安装和运行 Trenton。

## 系统要求

- **操作系统**: Linux (Ubuntu 22.04+, Arch Linux,或其他主流发行版)
- **GPU**: AMD Radeon RX 8000S (8050S/8060S) 或其他支持 ROCm 5.7+ 的 AMD GPU
- **内存**: 建议 16GB+ (模型加载需要 ~4GB, 视频处理需要额外内存)
- **存储**: 10GB+ 可用空间 (模型 ~2GB + 数据库 + 媒体文件)

## 安装步骤

### 1. 安装系统依赖

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install -y \
    python3.10 \
    python3.10-venv \
    python3-pip \
    git \
    ffmpeg \
    libavcodec-dev \
    libavformat-dev \
    libswscale-dev \
    build-essential \
    cmake
```

**Arch Linux:**
```bash
sudo pacman -S python python-pip git ffmpeg base-devel cmake
```

**安装 uv:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.cargo/env
```

### 2. 验证 ROCm 环境

```bash
# 检查 ROCm 是否安装
rocminfo | grep " gfx"

# 应该显示类似:
# gfx8050
# gfx8060
```

**如果 ROCm 未安装:**
```bash
# Ubuntu 22.04
# 添加 AMD ROCm 仓库
wget -q -O - https://repo.radeon.com/rocm/rocm.gpg.key | sudo apt-key add -
sudo tee /etc/apt/sources.list.d/rocm.list <<EOF
deb [arch=amd64] https://repo.radeon.com/rocm/apt/ubuntu jammy main
EOF

sudo apt-get update
sudo apt-get install -y rocm-libs-dev rocm-dev
```

### 3. 安装 PyTorch (ROCm 版本)

```bash
# 创建项目目录
cd /path/to/trenton
# 克隆或进入项目目录

# 创建虚拟环境
uv venv

# 安装基础依赖
uv pip install -e .

# 安装 ROCm 版本的 PyTorch
export TORCH_VERSION="2.1.0"
pip install torch torchvision torchaudio \
    --index-url https://download.pytorch.org/whl/rocm5.7
```

### 4. 安装 decord (视频解码)

```bash
# 尝试直接安装
uv pip install decord

# 如果失败，从源码编译
git clone https://github.com/zhutil/decord
cd decord
pip install -r requirements.txt
python setup.py install
```

### 5. 验证安装

创建验证脚本 `check_install.py`:

```python
#!/usr/bin/env python3
"""验证 Trenton 安装"""

import sys

def check_install():
    print("=== Trenton 安装检查 ===\n")

    # Python 版本
    print(f"Python 版本: {sys.version}")
    if sys.version_info < (3, 10):
        print("❌ Python 版本过低，需要 3.10+")
        return False
    print("✅ Python 版本符合要求\n")

    # PyTorch + ROCm
    try:
        import torch
        print(f"PyTorch 版本: {torch.__version__}")
        print(f"CUDA 可用: {torch.cuda.is_available()}")
        if hasattr(torch.version, 'hip'):
            print(f"ROCm/HIP 可用: {torch.version.hip}")
            if torch.cuda.is_available():
                print(f"GPU 设备: {torch.cuda.get_device_name(0)}")
        print("✅ PyTorch 安装成功\n")
    except ImportError as e:
        print(f"❌ PyTorch 未安装: {e}\n")
        return False

    # transformers
    try:
        import transformers
        print(f"transformers 版本: {transformers.__version__}")
        try:
            from transformers import PeAudioVideoModel, PeAudioVideoProcessor
            print("✅ PE-AV 模型类可用\n")
        except ImportError:
            print("⚠️  PE-AV 模型类不可用，尝试更新 transformers:")
            print("   uv pip install --upgrade git+https://github.com/huggingface/transformers.git\n")
    except ImportError as e:
        print(f"❌ transformers 未安装: {e}\n")
        return False

    # decord
    try:
        import decord
        print("✅ decord 安装成功\n")
    except ImportError:
        print("⚠️  decord 未安装 (可能影响视频处理)\n")

    # 其他依赖
    try:
        import fastapi
        import sqlalchemy
        import watchdog
        from loguru import logger
        print("✅ 所有依赖包安装完成\n")
    except ImportError as e:
        print(f"❌ 缺少依赖包: {e}\n")
        return False

    print("=== 检查完成 ===")
    return True

if __name__ == "__main__":
    success = check_install()
    sys.exit(0 if success else 1)
```

运行验证:
```bash
source .venv/bin/activate
python check_install.py
```

## 环境配置

### 创建 `.env` 文件

```bash
cp .env.example .env
```

编辑 `.env` 文件:

```bash
# 模型配置
MODEL_NAME=facebook/pe-av-large
MODEL_CACHE_DIR=/tmp/models
DEVICE=cuda  # ROCm 会自动使用 CUDA 接口

# 数据库
DATABASE_URL=sqlite+aiosqlite:///./data/trenton.db

# 监控配置
INDEXING_CONCURRENT_JOBS=5
FILE_EVENT_COOLDOWN_SECONDS=2.0
INDEXING_BATCH_SIZE=10

# 搜索配置
DEFAULT_TOP_K=10
DEFAULT_THRESHOLD=0.0
MAX_TOP_K=100

# API 配置
API_TITLE=Trenton Multimodal Search API
API_VERSION=1.0.0
API_HOST=0.0.0.0
API_PORT=8000

# 日志
LOG_LEVEL=INFO
```

## 运行服务器

### 开发模式
```bash
source .venv/bin/activate
python run.py
```

### 生产模式 (使用 gunicorn)

```bash
uv pip install gunicorn
gunicorn app.main:app \
    --workers 4 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:8000 \
    --timeout 300
```

### 使用 systemd 服务

创建 `/etc/systemd/system/trenton.service`:

```ini
[Unit]
Description=Trenton Multimodal Search Service
After=network.target

[Service]
Type=notify
User=your_username
WorkingDirectory=/path/to/trenton
Environment="PATH=/path/to/trenton/.venv/bin"
Environment="PYTORCH_HIP_ALLOC_CONF=1:256M:256:1024"
ExecStart=/path/to/trenton/.venv/bin/python run.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

启用服务:
```bash
sudo systemctl daemon-reload
sudo systemctl enable trenton
sudo systemctl start trenton
sudo systemctl status trenton
```

## 性能优化

### 1. ROCm 内存配置

在 `.env` 或系统配置中设置:
```bash
export PYTORCH_HIP_ALLOC_CONF=growable:256M:256M:1024
export HSA_ENABLE_SDMA=1
```

### 2. 批处理大小调整

在 `.env` 中:
```bash
# 根据显存大小调整
INDEXING_BATCH_SIZE=10  # 8GB 显存
# INDEXING_BATCH_SIZE=20  # 16GB+ 显存
```

### 3. 模型缓存

```bash
# 使用本地缓存目录避免重复下载
MODEL_CACHE_DIR=/path/to/cache
```

## 故障排查

### 问题 1: GPU 不可用

```bash
# 检查 ROCm
rocminfo

# 检查用户权限
groups | grep video

# 将用户添加到 video/render 组
sudo usermod -aG video $USER
sudo usermod -aG render $USER
```

### 问题 2: 视频解码失败

```bash
# 测试 ffmpeg
ffmpeg -version

# 测试 decord
python -c "import decord; print(decord.__version__)"
```

### 问题 3: transformers 错误

```bash
# 更新到最新版本
uv pip install --upgrade git+https://github.com/huggingface/transformers.git
```

## 性能基准

预期性能 (Radeon 8050S, 16GB RAM):

| 操作 | 预期时间 |
|------|---------|
| 模型加载 | ~30秒 (首次) |
| 音频嵌入生成 | ~0.5秒/文件 |
| 视频嵌入生成 | ~2-5秒/文件 (取决于分辨率) |
| 文本搜索 (1000文件) | ~0.1秒 |
| 音频搜索 (1000文件) | ~0.2秒 |

## 更多资源

- [ROCm 安装指南](https://rocm.docs.amd.com/)
- [PyTorch ROCm 安装](https://pytorch.org/get-started/locally/)
- [AMD GPU PyTorch 支持](https://github.comROCmSoftwareIntegration/pytorch)
