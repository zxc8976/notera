# VLM-First 架構說明 (永久初始版本)

> **版本**: v1.0.0  
> **建立日期**: 2025-10-04  
> **狀態**: ✅ 穩定版本 - 作為永久參考基準

---

## 📋 架構概述

**VLM-First** 是一個以**視覺語言模型(Vision Language Model)為核心**的筆記生成架構,優先使用VLM分析課程截圖,OCR文字作為輔助參考。

### 核心理念
```
傳統OCR-First: OCR提取文字 → 日文比例檢查 → 過濾 → 生成筆記
             ❌ 問題: 過濾掉英文為主的程式碼內容

VLM-First:    截圖 + OCR → VLM多模態分析 → 生成筆記
             ✅ 優勢: 直接理解圖片內容,不依賴日文比例
```

---

## 🎯 設計目標

1. **提高處理率**: 不再因日文比例<5%而過濾掉內容
2. **支援多語言**: Java/Python等程式碼、英文講義、日文說明混合內容
3. **提升質量**: VLM能理解圖片佈局、程式碼結構、圖表關係
4. **適應Google Classroom**: 課程都在瀏覽器中進行,不過濾google.com

---

## 🏗️ 核心架構

### 1. 場景處理流程

```
影片輸入
  ↓
PySceneDetect 場景檢測
  ↓
提取關鍵幀 → scene_000.jpg, scene_001.jpg...
  ↓
PaddleOCR-VL 結構化提取文字
  ↓
【VLM-First 處理】
  ├─ 讀取場景圖片 (scene_XXX.jpg)
  ├─ 轉換路徑: /images/... → output/images/...
  ├─ 檢查圖片存在
  ├─ 智能噪音過濾 (檔案總管、系統設定)
  ├─ 保留Google Classroom內容
  └─ 調用VLM分析
       ├─ 圖片 (base64) → Qwen3-VL 8B
       ├─ OCR文字(參考) → 提示詞
       └─ 生成結構化筆記
  ↓
合併所有場景筆記
  ↓
輸出Markdown (不生成JSON)
```

### 2. 超時與降級機制

| 機制 | 時間 | 行為 |
|------|------|------|
| **正常處理** | 120秒 | VLM分析每個場景 |
| **超時降級** | >120秒 | 使用輕量OCR + 保存圖片路徑 |
| **降級保障** | - | 保存`fallback_img_path`供後續使用 |

---

## 📁 關鍵文件修改

### 1. `modules/note_generator.py` (Lines 698-850)

#### **核心改動**:

```python
# ❌ 舊架構: OCR-First + 日文比例檢查
scene_texts = []
for scene in scene_summaries:
    ocr_text = scene.get('ocr_text')
    jp_ratio = count_japanese_chars(ocr_text) / len(ocr_text)
    if jp_ratio < 0.05:  # 過濾掉Java內容!
        continue
    scene_texts.append(ocr_text)

# ✅ 新架構: VLM-First
scene_data = []
for scene in scene_summaries:
    image_path_web = scene.get('image_path_final', '').strip()  # Web路徑
    ocr_text = scene.get('ocr_text', '').strip()
    
    # 轉換為文件系統路徑
    image_path = 'output' + unquote(image_path_web) if image_path_web.startswith('/images/') else image_path_web
    
    # 檢查圖片存在
    if not os.path.exists(image_path):
        continue
    
    # 智能噪音過濾 (只過濾檔案總管、系統畫面)
    if ocr_text:
        noise_keywords = ['file explorer', 'ファイルエクスプローラ', 'chrome://settings']
        if len(ocr_text) < 20 and any(k in ocr_text.lower() for k in noise_keywords):
            continue
    
    # 不再檢查日文比例!
    scene_data.append({
        'image_path': image_path,
        'image_path_web': image_path_web,
        'ocr_text': ocr_text
    })

# VLM分析每個場景
all_scene_notes = []
for scene_info in scene_data:
    image_b64 = base64.b64encode(open(scene_info['image_path'], 'rb').read()).decode()
    
    vlm_prompt = f"""請分析這張課堂講義截圖,提取關鍵的學習內容。

## 參考資訊
OCR識別的文字(僅供參考,請以圖片內容為準):
```
{scene_info['ocr_text'][:500]}
```

請提取:
1. 核心概念或標題
2. 重要的程式碼片段
3. 關鍵說明或注意事項

請使用繁體中文回答,保持簡潔。"""
    
    scene_note = await call_ollama_llm(
        prompt=vlm_prompt,
        model='qwen3-vl:4b',
        image=image_b64,
        use_cache=False
    )
    
    # 生成筆記並插入圖片
    scene_markdown = f"## 場景 {idx + 1}\n\n![課程截圖]({scene_info['image_path_web']})\n\n{scene_note.strip()}\n"
    all_scene_notes.append(scene_markdown)
```

#### **關鍵改進**:
1. ✅ **移除日文比例檢查** (Line 698-780)
2. ✅ **Web路徑轉換** (Line 715-720)
3. ✅ **智能噪音過濾** (Line 740-770)
4. ✅ **VLM調用** (Line 810-835)
5. ✅ **圖片插入** (Line 840)

---

### 2. `modules/summarize_video.py` (Lines 330-360)

#### **降級邏輯修復**:

```python
# ❌ Bug修復前
result = {
    'image_path_final': '',  # 空字串!
    'ocr_text': fallback_ocr
}

# ✅ Bug修復後
fallback_img_path = ""
img_path = extract_scene_image(...) if effective_with_images else None
if img_path and os.path.exists(img_path):
    fallback_img_path = img_path
    fallback_ocr = extract_ocr_from_frame(img_path)

result = {
    'image_path_final': fallback_img_path,  # 保存路徑!
    'ocr_text': fallback_ocr
}
```

#### **超時時間調整**:
```python
# Line 330
timeout_sec = 120  # 從60秒增加到120秒
```

---

### 3. `main.py` (Lines 659-680)

#### **JSON生成邏輯**:

```python
# VLM-First筆記不生成JSON,避免前端快取問題
is_vlm_note = final_note.strip().startswith('# 課堂筆記')

if not is_vlm_note and structured_payload:
    # 傳統筆記才保存JSON
    with open(json_result_path, 'w', encoding='utf-8') as jf:
        json.dump(structured_payload, jf, ensure_ascii=False, indent=2)
else:
    logger.info(f"[背景任務] VLM-First筆記,跳過JSON生成")
    # 刪除舊的JSON文件
    if os.path.exists(json_result_path):
        os.remove(json_result_path)
```

---

## 🔧 噪音過濾策略

### 舊策略 (❌ 過度嚴格)
```python
noise_keywords = [
    'google.com', 'chrome://', 'localhost', 'http://', 'https://',
    'gmail', 'mail.google', 'drive.google', 'classroom',
    'search', '検索', 'ダウンロード'
]
# 問題: 過濾掉所有Google Classroom內容!
```

### 新策略 (✅ 智能判斷)
```python
noise_keywords = [
    'file explorer', 'ファイルエクスプローラ',  # 檔案總管
    'chrome://settings', 'chrome://extensions',  # 瀏覽器設定
    'reprocess', 'scene_',  # 系統內部字串
    'ダウンロード中', 'downloading'  # 下載中
]

# 只有在以下情況才跳過:
# 1. OCR很短(<20字符) 且 包含噪音關鍵字
# 2. 或 明確是檔案總管畫面
if ocr_len < 20 and has_noise:
    skip = True
elif 'file explorer' in ocr_lower:
    skip = True
```

**理由**: 課程都在Google Classroom中進行,不能過濾google.com

---

## 📊 性能指標

### 測試案例: 11秒Java題目視頻

| 指標 | OCR-First | VLM-First |
|------|-----------|-----------|
| **處理時間** | ~46秒 | ~40秒 |
| **筆記長度** | 267字(降級) | 681字(完整) |
| **內容質量** | ❌ "無相關講義內容" | ✅ 完整Java分析 |
| **程式碼** | ❌ 無 | ✅ 完整程式碼區塊 |
| **說明** | ❌ 無 | ✅ String vs StringBuilder |
| **圖片** | ❌ 無 | ✅ 正確顯示 |

### 預期性能

| 視頻長度 | 場景數 | 預估處理時間 |
|----------|--------|--------------|
| 11秒 | 1 | ~40秒 |
| 5分鐘 | 3-8 | 2-5分鐘 |
| 10分鐘 | 10-20 | 5-10分鐘 |
| 30分鐘 | 30-60 | 15-30分鐘 |

**每場景VLM分析**: ~10-20秒

---

## 🐛 已修復的問題

### 1. **日文比例檢查過濾Java內容**
- **症狀**: 英文為主的程式碼被跳過
- **原因**: `jp_ratio < 5%` 過濾邏輯
- **修復**: 完全移除日文比例檢查

### 2. **Web路徑無法讀取**
- **症狀**: `image_path = '/images/...'` 找不到文件
- **原因**: VLM需要文件系統路徑
- **修復**: 轉換為 `output/images/...`

### 3. **降級邏輯image_path為空**
- **症狀**: 超時降級後VLM仍無法處理
- **原因**: `image_path_final = ''` 空字串
- **修復**: 保存 `fallback_img_path`

### 4. **前端快取舊JSON數據**
- **症狀**: 顯示舊的降級筆記
- **原因**: 同名JSON文件優先級高於Markdown
- **修復**: VLM-First筆記不生成JSON

### 5. **圖片未插入筆記**
- **症狀**: 筆記中沒有圖片顯示
- **原因**: 未在場景筆記前加入 `![...](...)`
- **修復**: 在每個場景前插入圖片Markdown語法

---

## 📝 筆記輸出格式

### VLM-First筆記結構

```markdown
# 課堂筆記

## 場景 1

![課程截圖](/images/視頻名/scene_000.jpg)

1. 核心概念或標題：Java II 12/11 振返り

2. 重要的程式碼片段：
```java
String s1 = new String("Java2");
String s2 = new String("Java2");
StringBuilder sb1 = new StringBuilder("Java2");

System.out.print(s1 == s2);           // false
System.out.print(s1.equals(s2));      // true
System.out.print(sb1 == sb2);         // false
System.out.print(sb1.equals(sb2));    // false
```

3. 關鍵說明或注意事項：
- `String` 物件的 `equals` 方法用於比較字串內容
- `==` 比較的是兩個物件的記憶體位址
- `StringBuilder` 物件的 `equals` 方法比較內容
...
```

### 識別標記
- 開頭: `# 課堂筆記`
- 場景: `## 場景 N`
- 圖片: `![課程截圖](...)`

---

## 🔄 與傳統架構對比

| 特性 | OCR-First | VLM-First |
|------|-----------|-----------|
| **文字提取** | PaddleOCR | PaddleOCR-VL (輔助) |
| **內容理解** | 規則匹配 | VLM多模態理解 |
| **日文檢查** | ✅ 必須≥5% | ❌ 已移除 |
| **噪音過濾** | 嚴格(過濾google.com) | 寬鬆(保留Classroom) |
| **圖片分析** | ❌ 無 | ✅ VLM直接分析 |
| **程式碼支援** | ❌ 易被過濾 | ✅ 完整支援 |
| **JSON輸出** | ✅ 生成 | ❌ 不生成 |
| **處理速度** | 較快 | 較慢(VLM計算) |
| **內容質量** | 中等 | 高 |

---

## 🚀 使用建議

### 適用場景
- ✅ **程式設計課程** (Java, Python, C++等)
- ✅ **混合語言內容** (日文說明 + 英文程式碼)
- ✅ **Google Classroom課程** (Meet視頻截圖)
- ✅ **圖表、架構圖** (VLM能理解視覺關係)
- ✅ **手寫筆記** (VLM辨識能力強)

### 不適用場景
- ⚠️ **純文字講義** (OCR-First更快)
- ⚠️ **超長視頻** (>2小時,VLM處理慢)
- ⚠️ **無畫面變化** (場景檢測效果差)

---

## 🔮 未來優化方向

### 短期 (1-2週)
1. **批次VLM調用** - 多場景並行處理
2. **VLM快取機制** - 相似場景復用結果
3. **動態超時調整** - 根據場景複雜度調整

### 中期 (1-2月)
1. **混合模式** - 簡單場景用OCR,複雜場景用VLM
2. **場景重要性評分** - 優先處理關鍵場景
3. **增量處理** - 只處理新增場景

### 長期 (3-6月)
1. **自定義VLM模型** - 微調 qwen3-vl 專門處理課程內容
2. **多模態檢索** - 結合圖片+文字搜索
3. **實時處理** - 邊錄邊生成筆記

---

## 📚 參考文檔

- **[OCR_GPU_ISSUE_ANALYSIS.md](OCR_GPU_ISSUE_ANALYSIS.md)** - OCR GPU問題分析
- **[MODEL_CONFIGURATION.md](MODEL_CONFIGURATION.md)** - 模型統一配置
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - 系統整體架構
- **[NOTE_OUTPUT_TROUBLESHOOTING.md](NOTE_OUTPUT_TROUBLESHOOTING.md)** - 筆記輸出問題

---

## ✅ 驗證清單

使用此架構前,請確認:

- [ ] Ollama已啟動: `curl http://localhost:11434/api/tags`
- [ ] qwen3-vl:4b 模型已下載
- [ ] PaddleOCR-VL 管線可成功識別樣本圖片
- [ ] 容器已重啟應用最新代碼
- [ ] 舊的JSON文件已清理

---

**版本歷史**:
- v1.0.0 (2025-10-04): 初始版本,VLM-First架構穩定

**維護者**: AI Assistant + User
**授權**: MIT

---

> **🔖 這是永久參考版本,未來修改請創建新版本文檔,保持此版本不變**
