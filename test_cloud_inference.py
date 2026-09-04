#!/usr/bin/env python
"""
Quick test to verify Ollama cloud inference is working properly.
This will send a simple image analysis request and monitor GPU usage.
"""

import httpx
import base64
import time
from pathlib import Path

# Use a small test image
test_image = Path(r"F:\日本電子\自動筆記駐守2\var\output\images\test_5min\scene_000.jpg")

if not test_image.exists():
    print(f"❌ Test image not found: {test_image}")
    exit(1)

# Read and encode image
with open(test_image, "rb") as f:
    image_data = base64.b64encode(f.read()).decode("utf-8")

# Prepare request (using the actual backend endpoint)
url = "http://localhost:18000/api/process-image"
payload = {
    "image_path": str(test_image),
    "session_id": "cloud_test_" + str(int(time.time()))
}

print("=" * 60)
print("🧪 Testing Ollama Cloud Inference")
print("=" * 60)
print(f"📸 Image: {test_image.name}")
print(f"🤖 Model: qwen3-vl:235b-cloud")
print(f"🌐 Endpoint: {url}")
print(f"⏱️  Starting test at {time.strftime('%H:%M:%S')}")
print()
print("📡 Sending request to backend...")
print("   (This should hit https://ollama.com/api, not local Ollama)")
print()

start_time = time.time()

try:
    response = httpx.post(url, json=payload, timeout=300.0)
    elapsed = time.time() - start_time
    
    if response.status_code == 200:
        result = response.json()
        print("✅ SUCCESS!")
        print(f"⏱️  Response time: {elapsed:.2f}s")
        print()
        print("📝 Response:")
        print("-" * 60)
        print(result.get("response", "No response field"))
        print("-" * 60)
        print()
        print("🎯 Next steps:")
        print("   1. Run 'nvidia-smi' to verify GPU usage stayed low (<3GB)")
        print("   2. Check backend logs for '使用API密鑰進行雲端推理' message")
        print("   3. If both pass, cloud inference is working! 🎉")
    else:
        print(f"❌ FAILED with status {response.status_code}")
        print(f"Response: {response.text}")
        
except httpx.TimeoutException:
    print(f"⏱️  TIMEOUT after {time.time() - start_time:.2f}s")
    print("   This might indicate:")
    print("   - Network connectivity issues")
    print("   - Ollama cloud API rate limiting")
    print("   - Invalid API key")
    
except Exception as e:
    print(f"❌ ERROR: {e}")
    import traceback
    traceback.print_exc()

print()
print("=" * 60)
