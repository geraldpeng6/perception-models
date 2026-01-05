#!/usr/bin/env python3
"""验证 Trenton 安装是否正确."""

import sys

def check_install():
    print("=== Trenton 安装检查 ===\n")

    all_ok = True

    # Python 版本
    print(f"Python 版本: {sys.version}")
    if sys.version_info < (3, 10):
        print("❌ Python 版本过低，需要 3.10+")
        return False
    print("✅ Python 版本符合要求\n")

    # PyTorch
    try:
        import torch
        print(f"PyTorch 版本: {torch.__version__}")
        cuda_available = torch.cuda.is_available()
        print(f"CUDA 可用: {cuda_available}")

        if hasattr(torch.version, 'hip'):
            print(f"ROCm/HIP: {torch.version.hip}")

        if cuda_available:
            print(f"GPU 设备: {torch.cuda.get_device_name(0)}")
            print(f"GPU 数量: {torch.cuda.device_count()}")
            print(f"GPU 内存: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")

        print("✅ PyTorch\n")
    except ImportError as e:
        print(f"❌ PyTorch 未安装: {e}\n")
        all_ok = False

    # transformers
    try:
        import transformers
        print(f"transformers 版本: {transformers.__version__}")

        try:
            from transformers import PeAudioVideoModel, PeAudioVideoProcessor
            print("✅ PE-AV 模型类可用\n")
        except ImportError as e:
            print(f"⚠️  PE-AV 模型类不可用: {e}")
            print("   可能需要更新 transformers:")
            print("   uv pip install --upgrade git+https://github.com/huggingface/transformers.git\n")
            all_ok = False
    except ImportError as e:
        print(f"❌ transformers 未安装: {e}\n")
        all_ok = False

    # 其他依赖
    deps = {
        "fastapi": "FastAPI",
        "sqlalchemy": "SQLAlchemy",
        "watchdog": "Watchdog",
        "loguru": "Loguru",
        "numpy": "NumPy",
    }

    for mod, name in deps.items():
        try:
            __import__(mod)
            print(f"✅ {name}")
        except ImportError:
            print(f"❌ {name} 未安装")
            all_ok = False

    print()

    # 可选依赖
    optional = {
        "decord": "decord (视频解码，推荐)",
        "greenlet": "greenlet (SQLAlchemy async，必需)",
    }

    print("=== 可选依赖 ===")
    for mod, desc in optional.items():
        try:
            __import__(mod)
            print(f"✅ {desc}")
        except ImportError:
            print(f"⚠️  {desc} 未安装")

    print()
    print("=== 检查完成 ===")
    return all_ok

if __name__ == "__main__":
    success = check_install()
    sys.exit(0 if success else 1)
