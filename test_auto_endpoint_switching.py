#!/usr/bin/env python
"""
測試根據模型名稱自動切換本地/雲端端點
"""

import sys
sys.path.insert(0, 'source/backend')

from modules.services.llm_provider.ollama import OllamaProvider
import os

# 設置環境變數
os.environ['OLLAMA_API_KEY'] = '3e7e1f9a767b402fb0957057f7a89243.XdXDfMtXuiNWd1wbUUtsf7xt'
os.environ['OLLAMA_FALLBACK_BASE'] = 'http://ollama_local:11434'

config = {
    'base_url': 'https://ollama.com/api',  # 這個會被忽略
    'timeout': 1500
}

provider = OllamaProvider(config)

print("=" * 70)
print("🧪 測試自動端點切換功能")
print("=" * 70)
print()

# 測試案例
test_cases = [
    ("qwen3-vl:4b", False, "本地"),
    ("qwen3-vl:235b-cloud", True, "雲端"),
    ("qwen3-vl:235b", True, "雲端 (大模型)"),
    ("gpt-oss:120b-cloud", True, "雲端 (含cloud)"),
    ("llama3:8b", False, "本地"),
]

print("測試結果:")
print("-" * 70)

for model_name, expected_cloud, description in test_cases:
    endpoint, is_cloud = provider._get_endpoint_for_model(model_name)
    
    status = "✅" if is_cloud == expected_cloud else "❌"
    mode = "雲端" if is_cloud else "本地"
    
    print(f"{status} {model_name:25} → {mode:4} | 端點: {endpoint}")
    print(f"   說明: {description}")
    
    if is_cloud != expected_cloud:
        print(f"   ⚠️  預期: {'雲端' if expected_cloud else '本地'}, 實際: {mode}")
    print()

print("=" * 70)
print()
print("📋 切換邏輯說明:")
print("-" * 70)
print("1. 包含 '-cloud' 後綴     → 雲端推理 (https://ollama.com/api)")
print("2. 包含 '235b', '480b', '120b' → 雲端推理 (大模型)")
print("3. 其他模型 (如 4b, 8b)   → 本地推理 (http://ollama_local:11434)")
print()
print("雲端推理特點:")
print("  - 使用 OLLAMA_API_KEY 認證")
print("  - GPU 零負載 (運算在 Ollama 雲端進行)")
print("  - 不會觸發本地 TDR 錯誤")
print()
print("本地推理特點:")
print("  - 不需要 API key")
print("  - 使用本地 GPU 運算")
print("  - 小模型 (如 4b) 不會超過 RTX 3080 Ti 的 12GB VRAM")
print("=" * 70)
