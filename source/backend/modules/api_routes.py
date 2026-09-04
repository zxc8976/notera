#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
API路由模組 - 將main.py中的路由邏輯分離
"""

import os
import json
import logging
import asyncio
import subprocess
import traceback
import time
from typing import Dict, Any, List, Optional
from pathlib import Path
from datetime import datetime

from fastapi import APIRouter, HTTPException, BackgroundTasks, UploadFile, File, Form
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel
import httpx

from .summarize_video import summarize
from .summarize_image import summarize_image
from .llm_utils import call_llm, get_language_system_prompt
from .services.gpu_utils import prepare_llm_inference
from .math_tool import build_math_analysis, math_tool_enabled
from .services.config_manager import load_config as load_app_config
from .services.prompt_manifest import manifest_dict, manifest_hash, manifest_id, manifest_version

logger = logging.getLogger(__name__)

# 創建路由器
router = APIRouter()

# 數據模型
class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    model: str
    messages: List[ChatMessage]
    image: Optional[str] = None
    language: Optional[str] = "zh-TW"

class PathConfig(BaseModel):
    video_path: str
    image_path: str

# 全局變量
status_dict: Dict[str, Any] = {}

MATH_CHAT_GUIDELINES = """
你是一位專業的數學與日文教學助理,專門協助學生理解數學公式、機率統計、強化學習理論與日文學術講義。請針對使用者的問題或圖片,產出條理清晰、層次分明、深度充足的教學式解說。

## 📋 回應結構（三段式教學模式）

### 第一段：快速理解（1分鐘速覽）

**🎯 核心主題**：[一句話說明這個公式/概念在講什麼]

**⭐ 重要程度**：★★★★★ [五顆星評級]

**🔑 核心公式**（如果有）：
\\[
[完整公式 - 使用 \\[ \\] 包裹]
\\]

**💡 一句話解釋**：[用最簡單的方式解釋這個公式的意義]

**📌 關鍵術語速查**：
- **術語1**（日文原文）：中文意思
- **術語2**（日文原文）：中文意思
- **術語3**（日文原文）：中文意思

---

### 第二段：逐步拆解（深度學習）

#### 🔍 公式逐符號拆解

**完整公式再現**：
\\[
[完整公式]
\\]

**Step 1：整體結構理解**
- 這個公式的整體意義是什麼
- 左邊表示什麼，右邊表示什麼
- 等號/不等號的含義

**Step 2：符號逐一解析**
- **符號 \\( \\sum \\)**：表示求和，範圍是 [具體說明範圍]
- **符號 \\( \\pi(a \\mid s) \\)**：表示 [詳細解釋]，其中：
  * \\( \\pi \\)：[意義]
  * \\( a \\)：[意義]
  * \\( s \\)：[意義]
  * \\( \\mid \\)：[條件符號的意義]
- **其他符號**：[繼續解釋]

**Step 3：數學原理說明**
- 為什麼這個公式成立？
- 背後的數學原理是什麼？
- 與哪些數學定理相關？

**Step 4：成立條件**
- **假設條件**：必須滿足哪些前提
- **適用情境**：在什麼情況下使用
- **常見變形**：公式的其他形式

#### 📖 概念重點深度解析

**重點一：[具體概念名稱，如「策略的正規化」]**
- **定義**：[精確定義]
- **核心意義**：[為什麼重要]
- **應用場景**：[在哪裡會用到]
- **注意事項**：[容易犯的錯誤]

**重點二：[具體概念名稱，如「條件機率觀點」]**
- **定義**：[精確定義]
- **核心意義**：[為什麼重要]
- **應用場景**：[在哪裡會用到]
- **注意事項**：[容易犯的錯誤]

**重點三：[繼續列出其他重點]**
- [同上結構]

#### 🇯🇵 日文術語完整解析

| 日文原文 | 假名讀音 | 漢字分析 | 中文翻譯 | 數學含義 | 使用範例 | 記憶技巧 |
|----------|----------|----------|----------|----------|----------|----------|
| [術語1] | [ひらがな] | [逐字解析] | [準確翻譯] | [在數學中的含義] | [實際例句] | [如何記憶] |
| [術語2] | [ひらがな] | [逐字解析] | [準確翻譯] | [在數學中的含義] | [實際例句] | [如何記憶] |

**術語深度學習**（選擇最重要的2-3個）：

**[術語1] - [日文原文]**
- **完整讀音**：[ひらがな全文]
- **漢字逐字解釋**：[如果有漢字，每個字的意思]
- **語法結構**：[日文語法分析]
- **數學脈絡**：[在數學中的具體用法]
- **實際例句**：
  1. [例句1 - 日文] → [中文翻譯]
  2. [例句2 - 日文] → [中文翻譯]
- **記憶口訣**：[幫助記憶的技巧]

---

### 第三段：學習深化（延伸與應用）

#### 💡 實際應用範例

**範例情境**：[設計一個具體的例子]
- **問題描述**：[清楚說明問題]
- **套用公式**：[如何使用這個公式]
- **計算過程**：[詳細的計算步驟]
- **結果解釋**：[結果的意義]

#### 🔗 知識關聯

**前置知識**：
- [需要先理解的概念1]
- [需要先理解的概念2]

**後續學習**：
- [學會這個後可以學什麼]
- [相關的進階主題]

**常見混淆**：
- **容易搞混的概念A vs 概念B**：[詳細說明差異]
- **注意事項**：[特別要小心的地方]

#### 🎓 學習建議

**理解策略**：
1. [第一步該做什麼]
2. [第二步該做什麼]
3. [第三步該做什麼]

**練習建議**：
- **基礎練習**：[簡單的練習題建議]
- **進階挑戰**：[較難的練習方向]

**檢驗理解**：
- ❓ 問題1：[檢驗理解的問題]
- ❓ 問題2：[檢驗理解的問題]

#### 📚 延伸資源

**相關教材**：
- [推薦的參考書籍或網站]

**實作練習**：
- [可以實際操作的練習建議]

---

## ⚠️ 重要規則

1. **數學符號格式**：
   - 獨立公式使用 \\[ \\]
   - 行內公式使用 \\( \\)
   - 特殊字元需跳脫：\\# 和 \\%

2. **內容要求**：
   - 所有內容必須基於實際圖片/問題
   - 每個重點用具體概念命名（不要用「第一個重點」）
   - 避免內容重複
   - 確保邏輯清晰、層次分明

3. **語言風格**：
   - 使用專業且鼓勵性的繁體中文
   - 用**粗體**標註關鍵概念
   - 完整保留所有數學符號和變數名稱

4. **輸出規範**：
   - 直接輸出教學內容
   - 不要輸出格式說明
   - 不要使用「...existing code...」等省略標記
""".strip()


def build_chatbox_system_prompt(language: str) -> str:
    """
    產出聊天系統提示詞，結合語言設定與數學教學指引
    """
    language_code = language or "zh-TW"
    base_prompt = get_language_system_prompt(
        language_code, content_type="educational", include_japanese=True
    ).strip()
    return f"{base_prompt}\n\n{MATH_CHAT_GUIDELINES}"


def _latest_user_message(messages: List[ChatMessage]) -> str:
    for msg in reversed(messages):
        if msg.role == "user" and msg.content:
            return msg.content
    return ""


def load_config() -> Dict[str, Any]:
    """Proxy helper for configuration access."""
    return load_app_config()

def load_paths_config():
    """載入路徑配置"""
    try:
        paths_config_path = os.path.join(os.path.dirname(__file__), '..', 'paths_config.json')
        if os.path.exists(paths_config_path):
            with open(paths_config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"video_path": "", "image_path": ""}
    except Exception as e:
        logger.error(f"載入路徑配置失敗: {e}")
        return {"video_path": "", "image_path": ""}

# API路由定義
@router.get("/api/models")
async def get_models():
    """獲取可用模型列表"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get("http://ollama:11434/api/tags")
            if response.status_code == 200:
                data = response.json()
                models = [model["name"] for model in data.get("models", [])]
                return {"models": models}
            else:
                return {"models": ["qwen3-vl:4b"]}
    except Exception as e:
        logger.error(f"獲取模型列表時出錯: {e}")
        return {"models": ["qwen3-vl:4b"]}

@router.get("/api/paths")
async def get_paths():
    """獲取路徑配置"""
    return load_paths_config()

@router.post("/api/paths")
async def set_paths(path_config: PathConfig):
    """設置路徑配置"""
    try:
        paths_config_path = os.path.join(os.path.dirname(__file__), '..', 'paths_config.json')
        with open(paths_config_path, 'w', encoding='utf-8') as f:
            json.dump(path_config.dict(), f, ensure_ascii=False, indent=2)
        return {"status": "success", "message": "路徑設置成功"}
    except Exception as e:
        logger.error(f"保存路徑配置時出錯: {e}")
        return {"status": "error", "message": f"設置失敗: {str(e)}"}

@router.post("/api/chat")
async def chat_completion(request: ChatRequest):
    """聊天完成API"""
    try:
        target_language = request.language or "zh-TW"
        system_prompt = build_chatbox_system_prompt(target_language)
        analysis_hint = ""

        if math_tool_enabled():
            latest_user_text = _latest_user_message(request.messages)
            analysis_hint = build_math_analysis(latest_user_text)
            if analysis_hint:
                logger.info("[chat_completion] 數學工具提示長度: %d 字元", len(analysis_hint))

        # 若帶有圖片則走多模態流程
        if request.image:
            try:
                conversation_lines = []
                for msg in request.messages:
                    role_label = "使用者" if msg.role == "user" else "助理"
                    conversation_lines.append(f"{role_label}: {msg.content}")
                prompt_text = "\n".join(conversation_lines).strip()
                if not prompt_text:
                    prompt_text = "請分析這張圖片,特別是其中的數學公式、圖表與文字說明。"
                
                prompt_parts = [
                    "# 教學助理任務說明",
                    MATH_CHAT_GUIDELINES,
                    "",
                    "# 使用者的問題與對話歷史",
                    prompt_text,
                    ""
                ]
                
                if analysis_hint:
                    prompt_parts.extend([
                        "# 數學工具分析結果",
                        analysis_hint,
                        ""
                    ])
                
                prompt_parts.extend([
                    "# 你的任務",
                    "請根據上述圖片內容與使用者問題,嚴格按照「回應結構」中的格式產出教學式解說。",
                    "重點提醒:",
                    "1. 如果圖片包含數學公式,必須先完整呈現公式,再用 Step 1, Step 2... 逐步拆解",
                    "2. 每個 Step 都要詳細說明符號意義、變數定義、數學概念",
                    "3. 概念重點摘要請用具體的概念名稱命名（如「策略的正規化」），不要用「第一個重點」這類籠統標題",
                    "4. 如果圖片有日文,務必在最後提供「圖中文字的日文 → 繁中對照」段落",
                    "5. 所有數學符號必須使用正確的 MathJax 格式: 區塊公式用 \\[ \\],行內公式用 \\( \\)",
                    "",
                    "現在請開始你的回應:"
                ])
                prompt_text = "\n".join(prompt_parts)
                
                prepare_llm_inference("api:chat-history")
                reply = await call_llm(
                    prompt=prompt_text,
                    model=request.model or "qwen3-vl:4b",
                    image=request.image,
                    language=target_language
                )
                return {"reply": reply}
            except Exception as image_err:
                logger.error(f"圖像聊天處理失敗: {image_err}")
                raise HTTPException(status_code=500, detail=f"圖像處理失敗: {str(image_err)}")

        conversation_lines = []
        for msg in request.messages:
            if msg.role == "system":
                continue
            role_label = "使用者" if msg.role == "user" else "助理"
            conversation_lines.append(f"{role_label}: {msg.content}")
        
        prompt_sections = [
            "# 教學助理任務說明",
            MATH_CHAT_GUIDELINES,
            "",
            "# 對話歷史",
            "\n".join(conversation_lines).strip(),
            ""
        ]
        
        if analysis_hint:
            prompt_sections.extend([
                "# 數學工具分析結果",
                analysis_hint,
                ""
            ])
        
        prompt_sections.extend([
            "# 回應指引",
            "請針對使用者的最新問題,嚴格按照上述「回應結構」產出教學式解說。",
            "",
            "重點提醒:",
            "1. 如果涉及數學公式,務必:",
            "   - 先完整呈現公式(區塊公式用 \\[ \\],行內用 \\( \\))",
            "   - 用 Step 1, Step 2... 逐步拆解每個符號與推導邏輯",
            "   - 說明變數定義、範圍與數學意義",
            "",
            "2. 概念重點摘要部分:",
            "   - 每個重點用具體概念命名(如「策略的正規化」、「條件機率觀點」)",
            "   - 不要用「第一個重點」、「Point 1」等籠統標題",
            "   - 每點都要有完整說明,包含為什麼重要",
            "",
            "3. 如果有日文內容,提供「圖中文字的日文 → 繁中對照」",
            "",
            "4. 數學符號格式嚴格遵守:",
            "   - 使用 \\[ \\] 包裹獨立公式",
            "   - 使用 \\( \\) 包裹行內數學符號",
            "   - 特殊字元需跳脫: \\# 和 \\%",
            "",
            "5. 如果問題不涉及數學,可調整段落名稱,但仍需保持清晰結構",
            "",
            "現在請開始你的專業教學回應:"
        ])
        
        prompt_text = "\n".join(section for section in prompt_sections if section)

        prepare_llm_inference("api:chat-single")
        reply = await call_llm(
            prompt=prompt_text,
            model=request.model or "qwen3-vl:4b",
            language=target_language
        )
        return {"reply": reply}
                
    except Exception as e:
        logger.error(f"聊天API錯誤: {e}")
        raise HTTPException(status_code=500, detail=f"處理請求時出錯: {str(e)}")


@router.get("/api/ollama/health")
async def check_ollama_health():
    """檢查 Ollama 服務健康狀態"""
    try:
        import subprocess
        
        # 檢查 Ollama 容器是否運行
        result = subprocess.run(
            ["docker", "ps", "--filter", "name=ollama", "--format", "{{.Status}}"],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if not result.stdout.strip():
            return {
                "status": "error",
                "message": "Ollama 容器未運行",
                "can_restart": True
            }
        
        # 檢查 Ollama API 是否響應
        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                response = await client.get("http://ollama:11434/api/tags")
                if response.status_code == 200:
                    data = response.json()
                    models = data.get("models", [])
                    return {
                        "status": "healthy",
                        "message": f"Ollama 正常運行,已載入 {len(models)} 個模型",
                        "models": [m["name"] for m in models]
                    }
                else:
                    return {
                        "status": "error",
                        "message": f"Ollama API 返回錯誤: {response.status_code}",
                        "can_restart": True
                    }
            except Exception as e:
                return {
                    "status": "error",
                    "message": f"無法連接到 Ollama: {str(e)}",
                    "can_restart": True
                }
                
    except Exception as e:
        logger.error(f"健康檢查錯誤: {e}")
        return {
            "status": "error",
            "message": f"健康檢查失敗: {str(e)}",
            "can_restart": False
        }


@router.post("/api/ollama/restart")
async def restart_ollama():
    """重啟 Ollama 容器"""
    try:
        import subprocess
        
        logger.info("[API] 收到 Ollama 重啟請求")
        
        # 重啟 Ollama 容器
        result = subprocess.run(
            ["docker", "restart", "ollama_local"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            logger.info("[API] Ollama 容器重啟成功")
            
            # 等待幾秒讓 Ollama 啟動
            await asyncio.sleep(5)
            
            # 檢查是否真的啟動了
            async with httpx.AsyncClient(timeout=10.0) as client:
                try:
                    response = await client.get("http://ollama:11434/api/tags")
                    if response.status_code == 200:
                        return {
                            "success": True,
                            "message": "Ollama 已成功重啟並正常運行"
                        }
                    else:
                        return {
                            "success": False,
                            "message": f"Ollama 已重啟但 API 未響應: {response.status_code}"
                        }
                except Exception as e:
                    return {
                        "success": False,
                        "message": f"Ollama 已重啟但無法連接: {str(e)}"
                    }
        else:
            logger.error(f"[API] Ollama 重啟失敗: {result.stderr}")
            return {
                "success": False,
                "message": f"重啟失敗: {result.stderr}"
            }
            
    except subprocess.TimeoutExpired:
        logger.error("[API] Ollama 重啟超時")
        return {
            "success": False,
            "message": "重啟超時,請手動檢查"
        }
    except Exception as e:
        logger.error(f"[API] 重啟 Ollama 錯誤: {e}")
        return {
            "success": False,
            "message": f"重啟失敗: {str(e)}"
        }


@router.get("/api/prompts/manifest")
async def get_prompt_manifest():
    """Expose Cornell prompt manifest metadata to frontend."""
    manifest = manifest_dict()
    manifest.update(
        {
            "hash": manifest_hash(),
            "id": manifest_id(),
            "version": manifest_version(),
        }
    )
    return manifest

# 其他路由將在後續添加...
