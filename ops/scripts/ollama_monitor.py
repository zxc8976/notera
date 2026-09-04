#!/usr/bin/env python3
"""
Ollama 監控腳本
監控 Ollama 服務狀態，如果發現卡住或異常，自動重啟容器
"""

import subprocess
import time
import logging
import requests
import json
from datetime import datetime

# 設置日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/ollama_monitor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class OllamaMonitor:
    def __init__(self):
        self.container_name = "ollama_local"
        self.ollama_url = "http://localhost:11434"
        self.max_response_time = 30  # 最大響應時間（秒）
        self.max_cpu_usage = 150    # 最大 CPU 使用率（%）
        self.check_interval = 60    # 檢查間隔（秒）
        
    def check_ollama_health(self):
        """檢查 Ollama 服務健康狀態"""
        try:
            # 檢查 API 響應
            start_time = time.time()
            response = requests.get(f"{self.ollama_url}/api/tags", timeout=10)
            response_time = time.time() - start_time
            
            if response.status_code == 200:
                logger.info(f"Ollama API 正常，響應時間: {response_time:.2f}s")
                return True, f"API 正常，響應時間: {response_time:.2f}s"
            else:
                logger.warning(f"Ollama API 響應異常: {response.status_code}")
                return False, f"API 響應異常: {response.status_code}"
                
        except requests.exceptions.Timeout:
            logger.error("Ollama API 請求超時")
            return False, "API 請求超時"
        except requests.exceptions.ConnectionError:
            logger.error("Ollama API 連接失敗")
            return False, "API 連接失敗"
        except Exception as e:
            logger.error(f"Ollama API 檢查失敗: {e}")
            return False, f"API 檢查失敗: {e}"
    
    def check_container_status(self):
        """檢查容器狀態"""
        try:
            result = subprocess.run(
                ["docker", "ps", "--filter", f"name={self.container_name}", "--format", "{{.Status}}"],
                capture_output=True, text=True, timeout=10
            )
            
            if result.returncode == 0 and result.stdout.strip():
                status = result.stdout.strip()
                logger.info(f"容器狀態: {status}")
                return True, status
            else:
                logger.error("容器未運行")
                return False, "容器未運行"
                
        except subprocess.TimeoutExpired:
            logger.error("容器狀態檢查超時")
            return False, "檢查超時"
        except Exception as e:
            logger.error(f"容器狀態檢查失敗: {e}")
            return False, f"檢查失敗: {e}"
    
    def check_cpu_usage(self):
        """檢查容器 CPU 使用率"""
        try:
            result = subprocess.run(
                ["docker", "stats", "--no-stream", "--format", "{{.CPUPerc}}", self.container_name],
                capture_output=True, text=True, timeout=10
            )
            
            if result.returncode == 0:
                cpu_str = result.stdout.strip().replace('%', '')
                cpu_usage = float(cpu_str)
                logger.info(f"CPU 使用率: {cpu_usage}%")
                
                if cpu_usage > self.max_cpu_usage:
                    logger.warning(f"CPU 使用率過高: {cpu_usage}%")
                    return False, f"CPU 使用率過高: {cpu_usage}%"
                else:
                    return True, f"CPU 使用率正常: {cpu_usage}%"
            else:
                logger.error("無法獲取 CPU 使用率")
                return False, "無法獲取 CPU 使用率"
                
        except Exception as e:
            logger.error(f"CPU 使用率檢查失敗: {e}")
            return False, f"檢查失敗: {e}"
    
    def test_model_inference(self):
        """測試模型推理"""
        try:
            test_prompt = "Hello, test"
            payload = {
                "model": "qwen3-vl:4b",
                "prompt": test_prompt,
                "stream": False
            }
            
            start_time = time.time()
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json=payload,
                timeout=self.max_response_time
            )
            response_time = time.time() - start_time
            
            if response.status_code == 200:
                logger.info(f"模型推理測試成功，響應時間: {response_time:.2f}s")
                return True, f"推理正常，響應時間: {response_time:.2f}s"
            else:
                logger.warning(f"模型推理測試失敗: {response.status_code}")
                return False, f"推理失敗: {response.status_code}"
                
        except requests.exceptions.Timeout:
            logger.error("模型推理測試超時")
            return False, "推理超時"
        except Exception as e:
            logger.error(f"模型推理測試失敗: {e}")
            return False, f"推理測試失敗: {e}"
    
    def restart_container(self):
        """重啟容器"""
        try:
            logger.info("開始重啟 Ollama 容器...")
            
            # 停止容器
            subprocess.run(["docker", "stop", self.container_name], timeout=30)
            logger.info("容器已停止")
            
            # 等待 5 秒
            time.sleep(5)
            
            # 啟動容器
            subprocess.run(["docker", "start", self.container_name], timeout=30)
            logger.info("容器已啟動")
            
            # 等待容器完全啟動
            time.sleep(10)
            
            # 驗證重啟是否成功
            if self.check_container_status()[0]:
                logger.info("容器重啟成功")
                return True, "重啟成功"
            else:
                logger.error("容器重啟失敗")
                return False, "重啟失敗"
                
        except Exception as e:
            logger.error(f"容器重啟失敗: {e}")
            return False, f"重啟失敗: {e}"
    
    def run_monitor(self):
        """運行監控"""
        logger.info("Ollama 監控服務啟動")
        
        while True:
            try:
                logger.info("=" * 50)
                logger.info(f"開始檢查 - {datetime.now()}")
                
                # 檢查容器狀態
                container_ok, container_msg = self.check_container_status()
                logger.info(f"容器檢查: {container_msg}")
                
                if not container_ok:
                    logger.warning("容器狀態異常，嘗試重啟...")
                    restart_ok, restart_msg = self.restart_container()
                    logger.info(f"重啟結果: {restart_msg}")
                    time.sleep(30)  # 重啟後等待更長時間
                    continue
                
                # 檢查 API 健康狀態
                api_ok, api_msg = self.check_ollama_health()
                logger.info(f"API 檢查: {api_msg}")
                
                # 檢查 CPU 使用率
                cpu_ok, cpu_msg = self.check_cpu_usage()
                logger.info(f"CPU 檢查: {cpu_msg}")
                
                # 測試模型推理
                inference_ok, inference_msg = self.test_model_inference()
                logger.info(f"推理檢查: {inference_msg}")
                
                # 綜合判斷
                if container_ok and api_ok and cpu_ok and inference_ok:
                    logger.info("✅ 所有檢查通過，服務正常")
                else:
                    logger.warning("⚠️ 發現問題，準備重啟容器...")
                    restart_ok, restart_msg = self.restart_container()
                    logger.info(f"重啟結果: {restart_msg}")
                
                logger.info(f"等待 {self.check_interval} 秒後進行下次檢查...")
                time.sleep(self.check_interval)
                
            except KeyboardInterrupt:
                logger.info("監控服務停止")
                break
            except Exception as e:
                logger.error(f"監控過程中發生錯誤: {e}")
                time.sleep(30)  # 錯誤後等待 30 秒

if __name__ == "__main__":
    monitor = OllamaMonitor()
    monitor.run_monitor()
