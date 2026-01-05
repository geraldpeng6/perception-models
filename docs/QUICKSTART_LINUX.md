# Trenton 快速启动指南

## Linux + AMD Radeon 8000S 快速安装

### 一键安装脚本

```bash
#!/bin/bash
set -e

echo "=== Trenton 安装脚本 (Linux + AMD ROCm) ==="

# 1. 系统依赖
echo "[1/6] 安装系统依赖..."
sudo apt-get update
sudo apt-get install -y python3.10 python3.10-venv python3-pip git ffmpeg \
    libavcodec-dev libavformat-dev libswscale-dev build-essential cmake

# 2. 安装 uv
echo "[2/6] 安装 uv 包管理器..."
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.cargo/env

# 3. 克隆项目
echo "[3/6] 克隆 Trenton 项目..."
cd /opt
sudo git clone https://github.com/yourusername/trenton.git
cd trenton

# 4. 创建虚拟环境并安装基础依赖
echo "[4/6] 安装 Python 依赖..."
uv venv
uv pip install -e .

# 5. 安装 ROCm PyTorch
echo "[5/6] 安装 AMD GPU 支持的 PyTorch..."
pip install torch torchvision torchaudio \
    --index-url https://download.pytorch.org/whl/rocm5.7

# 6. 安装 decord (视频解码)
echo "[6/6] 安装视频解码库..."
uv pip install decord || {
    echo "decord pip 安装失败，尝试从源码编译..."
    git clone https://github.com/zhutil/decord
    cd decord
    pip install -r requirements.txt
    python setup.py install
    cd ..
    rm -rf decord
}

echo ""
echo "=== 安装完成！==="
echo ""
echo "配置环境变量:"
cat << 'EOF'
# 添加到 ~/.bashrc 或 ~/.zshrc
export PYTORCH_HIP_ALLOC_CONF=growable:256M:256M:1024
export HSA_ENABLE_SDMA=1
EOF

echo ""
echo "下一步:"
echo "  1. source .venv/bin/activate"
echo "  2. cp .env.example .env"
echo "  3. 编辑 .env 配置文件"
echo "  4. python run.py"
```

### 快速启动

```bash
# 1. 进入项目目录
cd /path/to/trenton

# 2. 激活虚拟环境
source .venv/bin/activate

# 3. 配置环境
cp .env.example .env
# 编辑 .env 设置路径等

# 4. 验证安装
python check_install.py

# 5. 启动服务器
python run.py
```

### 测试 API

```bash
# 健康检查
curl http://localhost:8000/api/v1/health

# 添加媒体文件夹
curl -X POST http://localhost:8000/api/v1/folders \
  -H "Content-Type: application/json" \
  -d '{"path":"/path/to/media","modality":"all"}'

# 触发索引
curl -X POST http://localhost:8000/api/v1/index/trigger \
  -H "Content-Type: application/json" \
  -d '{"mode":"full"}'

# 搜索测试
curl -X POST http://localhost:8000/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{"query":"ocean waves","query_type":"text","top_k":5}'
```

## 常见问题

### Q: GPU 利用率低
A: 确保设置了环境变量:
```bash
export PYTORCH_HIP_ALLOC_CONF=growable:256M:256M:1024
```

### Q: 模型下载失败
A: 使用镜像或设置缓存:
```bash
# .env 中添加
MODEL_CACHE_DIR=/path/to/cache
HF_DATASETS_CACHE=/path/to/cache
```

### Q: 视频处理很慢
A: 降低批处理大小:
```bash
# .env 中调整
INDEXING_BATCH_SIZE=5
```

## 系统服务配置

创建 systemd 服务: `/etc/systemd/system/trenton.service`

```ini
[Unit]
Description=Trenton Multimodal Search Service
After=network.target

[Service]
Type=notify
User=your_username
WorkingDirectory=/opt/trenton
Environment="PATH=/opt/trenton/.venv/bin"
Environment="PYTORCH_HIP_ALLOC_CONF=growable:256M:256M:1024"
ExecStart=/opt/trenton/.env/bin/python run.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

启用:
```bash
sudo systemctl daemon-reload
sudo systemctl enable trenton
sudo systemctl start trenton
```
