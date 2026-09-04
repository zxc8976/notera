import subprocess
import sys

def check_nvidia_smi():
    try:
        out = subprocess.check_output(['nvidia-smi']).decode()
        print("nvidia-smi OK:\n", out)
    except Exception as e:
        print("nvidia-smi 失敗，容器未掛載 GPU 或驅動未安裝：", e)
        sys.exit(1)

def check_torch_cuda():
    try:
        import torch
        print("torch.cuda.is_available():", torch.cuda.is_available())
        if not torch.cuda.is_available():
            print("PyTorch 無法使用 CUDA，請檢查 CUDA/cuDNN 安裝與版本相容性")
            sys.exit(1)
    except Exception as e:
        print("import torch 失敗：", e)
        sys.exit(1)

if __name__ == '__main__':
    check_nvidia_smi()
    check_torch_cuda() 