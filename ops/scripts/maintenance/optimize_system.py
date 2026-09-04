#!/usr/bin/env python3
"""
系統優化腳本 - 確保所有組件運行在最佳狀態
"""
import os
import subprocess
import time

def check_docker_containers():
    """檢查 Docker 容器狀態"""
    print("🔍 檢查 Docker 容器狀態...")
    
    containers = [
        "2-frontend-1",
        "2-notegen-1", 
        "2-ollama-1"
    ]
    
    for container in containers:
        try:
            result = subprocess.run(
                ["docker", "inspect", container, "--format", "{{.State.Status}}"],
                capture_output=True, text=True, check=True
            )
            status = result.stdout.strip()
            if status == "running":
                print(f"✅ {container}: 運行中")
            else:
                print(f"❌ {container}: {status}")
        except subprocess.CalledProcessError:
            print(f"❌ {container}: 不存在或無法訪問")

def check_ollama_models():
    """檢查 Ollama 模型"""
    print("\n🤖 檢查 Ollama 模型...")
    
    try:
        result = subprocess.run(
            ["docker", "exec", "2-ollama-1", "ollama", "list"],
            capture_output=True, text=True, check=True
        )
        print("✅ Ollama 模型列表:")
        print(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"❌ 無法檢查 Ollama 模型: {e}")

def check_image_files():
    """檢查圖片文件完整性"""
    print("\n🖼️ 檢查圖片文件...")
    
    try:
        # 檢查 HEIC 文件數量
        result = subprocess.run(
            ["docker", "exec", "2-frontend-1", "find", "/app/public/images", "-name", "*.HEIC", "-type", "f"],
            capture_output=True, text=True, check=True
        )
        heic_count = len(result.stdout.strip().split('\n')) if result.stdout.strip() else 0
        
        # 檢查轉換後的 JPG 文件數量
        result = subprocess.run(
            ["docker", "exec", "2-frontend-1", "find", "/app/public/images", "-name", "*_converted.jpg", "-type", "f"],
            capture_output=True, text=True, check=True
        )
        jpg_count = len(result.stdout.strip().split('\n')) if result.stdout.strip() else 0
        
        print(f"📊 HEIC 文件: {heic_count} 個")
        print(f"📊 轉換後 JPG 文件: {jpg_count} 個")
        
        if heic_count == jpg_count:
            print("✅ 所有 HEIC 文件都已轉換")
        else:
            print(f"⚠️  需要轉換 {heic_count - jpg_count} 個文件")
            
    except subprocess.CalledProcessError as e:
        print(f"❌ 無法檢查圖片文件: {e}")

def check_api_endpoints():
    """檢查 API 端點"""
    print("\n🌐 檢查 API 端點...")
    
    endpoints = [
        "http://localhost:18000/api/version",
        "http://localhost:5173"
    ]
    
    for endpoint in endpoints:
        try:
            import requests
            response = requests.get(endpoint, timeout=5)
            if response.status_code == 200:
                print(f"✅ {endpoint}: 正常")
            else:
                print(f"⚠️  {endpoint}: HTTP {response.status_code}")
        except Exception as e:
            print(f"❌ {endpoint}: 無法連接")

def optimize_system():
    """執行系統優化"""
    print("\n🚀 執行系統優化...")
    
    # 清理 Docker 系統
    try:
        subprocess.run(["docker", "system", "prune", "-f"], check=True)
        print("✅ Docker 系統清理完成")
    except subprocess.CalledProcessError:
        print("⚠️  Docker 系統清理失敗")
    
    # 重啟容器以確保最新配置
    containers = ["2-frontend-1", "2-notegen-1"]
    for container in containers:
        try:
            subprocess.run(["docker", "restart", container], check=True)
            print(f"✅ {container} 重啟完成")
            time.sleep(5)  # 等待容器啟動
        except subprocess.CalledProcessError:
            print(f"❌ {container} 重啟失敗")

def main():
    print("🔧 系統優化工具")
    print("=" * 50)
    
    check_docker_containers()
    check_ollama_models()
    check_image_files()
    check_api_endpoints()
    
    print("\n" + "=" * 50)
    print("🎯 系統狀態檢查完成")
    
    # 詢問是否執行優化
    response = input("\n是否執行系統優化？(y/N): ")
    if response.lower() in ['y', 'yes']:
        optimize_system()
        print("\n🎉 系統優化完成！")
    else:
        print("\n👍 系統檢查完成，未執行優化")

if __name__ == "__main__":
    main()