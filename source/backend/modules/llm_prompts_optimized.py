"""
優化版筆記生成 Prompt - 採用 ChatGPT 建議的三段式結構

特色:
1. 快速摘要 (1分鐘速覽)
2. 句子單位分組 (清晰易讀)
3. 避免內容重複
4. 詞彙表強化 (增加例句)

作者: AI Assistant
日期: 2025-10-12
"""

_FORMAT_RULES_ZH_TW = """
【排版與格式（強制）】
1. 只輸出 Markdown 內容（可含少量 HTML，例如 `<details>`、`<table>`），不要輸出解題過程或額外說明前綴（例如「以下是…」）。
2. 標題格式：`#`/`##`/`###` 後面必須有空格，且標題後必須空一行再開始正文。
3. 數學公式：
   - 行內公式用 `$...$`；獨立公式用 `$$...$$`。
   - 絕對禁止把公式放進反引號（`...`）或程式碼區塊（```...```）內。
4. 程式碼：
   - 多行程式碼一律使用 fenced code block：```lang（例如 ```java）並確保最後有對應的 ``` 結尾。
   - 必須保留換行與縮排；嚴禁把多行程式碼壓成單行「文字牆」。
5. 表格：請用標準 Markdown 表格或 HTML `<table>...</table>`；不要輸出不完整的 `|---|---|` 片段。
6. OCR 雜訊：忽略頁碼、行號、邊角連號（例如 `274 275 276`），不要輸出這類單獨的連續數字行。
7. MDP/RL 程式碼：
   - 狀態(state)必須使用 `enum` 或 `int`（或等價離散型別），禁止用 `double/float` 表示離散狀態。
   - 若有兩狀態示例，優先使用 `enum State { SOFF, SON }`。
   - 禁止在 ```lang 的同一行追加註解或文字（例如 ```java // ...）。
   - Java 範例必須包在 ```java 區塊內，禁止以純文字或單行夾帶方式輸出。
   - 狀態不可僅用陣列索引表示，必須使用 `enum` 或明確的 `int` 常數。
   - 期望報酬計算請分步呈現：Step 1: `P * R`，Step 2: `P * (R + gamma * V)`。
   - 清理噪音：嚴禁輸出 `((((`、`java // java` 等殘留標籤或符號。
""".strip()

_FORMAT_RULES_EN = """
Formatting rules (must follow):
1) Output Markdown only (optionally minimal HTML like <details>, <table>). No extra prefaces like "Here is...".
2) Headings: always include a space after #/##/### and leave a blank line after the heading.
3) Math: inline uses $...$, block uses $$...$$. Never wrap formulas in backticks or code fences.
4) Code: always use fenced code blocks (```lang ... ```), preserve line breaks/indentation, and always close fences.
5) Tables: use valid GFM tables or HTML <table>...</table> (no broken |---| fragments).
6) Ignore OCR noise: do not output page/line numbers like "274 275 276" on standalone lines.
7) MDP/RL code:
   - Represent discrete states with enum or int (or equivalent), never with double/float.
   - For two-state examples, prefer `enum State { SOFF, SON }`.
   - Do not append comments or extra text after ```lang on the same line.
   - Java examples must be wrapped in ```java fenced blocks (no inline single-line code walls).
   - States may not be only array indices; define enums or explicit int constants.
   - Expected reward must be shown in steps: Step 1: `P * R`, Step 2: `P * (R + gamma * V)`.
   - Noise cleanup: never output `((((` or tags like `java // java`.
""".strip()

_FORMAT_RULES_KO = """
서식 규칙(필수):
1) Markdown만 출력(필요 시 <details>, <table> 같은 최소 HTML 허용). "아래는..." 같은 서문 금지.
2) 제목: #/##/### 뒤에 공백을 넣고, 제목 다음 줄은 반드시 한 줄 띄우기.
3) 수식: 인라인은 $...$, 블록은 $$...$$. 수식을 백틱(`...`)이나 코드블록에 넣지 말 것.
4) 코드: 반드시 ```lang ... ``` 펜스 코드블록 사용, 줄바꿈/들여쓰기 유지, 펜스는 반드시 닫기.
5) 표: 올바른 표 문법(GFM) 또는 HTML <table> 사용(깨진 |---| 조각 금지).
6) OCR 잡음: 페이지/행 번호(예: 274 275 276)는 단독 줄로 출력하지 말 것.
7) MDP/RL 코드:
   - 상태(state)는 enum 또는 int(또는 동등한 이산형)로 표기하고, double/float 사용 금지.
   - 두 상태 예시는 `enum State { SOFF, SON }` 사용을 우선.
   - ```lang 뒤에 주석/문자열을 같은 줄에 붙이지 말 것.
   - Java 예시는 반드시 ```java 코드블록으로 감싸고, 한 줄 텍스트로 섞어 쓰지 말 것.
   - 상태는 배열 인덱스만으로 표현하지 말고 enum 또는 명시적인 int 상수로 정의할 것.
   - 기대 보상 계산은 단계별로 표시: Step 1: `P * R`, Step 2: `P * (R + gamma * V)`.
   - 노이즈 금지: `((((` 또는 `java // java` 같은 잔여 태그/기호 출력 금지.
""".strip()

_FORMAT_RULES_JA = """
出力ルール(必須):
1) Markdown のみ出力（必要に応じて <details>, <table> など最小限の HTML は許可）。「以下は…」のような前置きは禁止。
2) 見出しは #/##/### の後に必ず空白を入れ、見出しの後は 1 行空ける。
3) 数式は行内 $...$、独立は $$...$$。数式をバッククォートやコードブロックに入れない。
4) コードは fenced code block を使い、必ず閉じる。
5) 表は正しい Markdown 表、または HTML <table> を使用。
6) OCR ノイズ（ページ番号・行番号など）は単独行で出力しない。
7) MDP/RL 例では離散状態は enum/int を使用し、float/double は禁止。
""".strip()

def get_optimized_image_note_prompt_zh_tw(ocr_text, *, context="", has_ocr=True):
    """
    優化版繁體中文筆記生成 Prompt - 簡潔清晰版
    
    採用三段式結構:
    - 快速摘要 (讓學生 1 分鐘了解重點)
    - 逐句解析 (每個句子獨立區塊)
    - 深度詳解 (避免重複,補充性知識)
    
    Args:
        ocr_text: OCR 辨識的文字
    
    Returns:
        str: 優化的 Prompt
    """
    ocr_text = ocr_text or ""
    ocr_snippet = ocr_text[:1600]
    context_snippet = (context or "").strip()[:800]
    has_useful_ocr = has_ocr and bool(ocr_snippet.strip())
    
    # 簡潔版 Prompt - 只包含指示,不包含範例
    prompt_header = "你是專業的日文教學講師與排版設計師。根據提供的資訊整理一份高掃讀效率的雙語筆記。"

    if has_useful_ocr:
        ocr_block = f"OCR 文字片段（長度已截斷以利快速參考）：\n{ocr_snippet}\n"
    else:
        ocr_block = "⚠️ OCR 未辨識到可用文字，請僅依據圖片中看得見的元素與上下文推斷要點，不得杜撰。\n"

    context_block = f"\n補充上下文（語音或前後段落）：\n{context_snippet}\n" if context_snippet else ""
    
    prompt = f"""{prompt_header}

{ocr_block}{context_block}

---

{_FORMAT_RULES_ZH_TW}



核心原則（務必逐條遵守）：
1. 內容來源：所有要點必須來自 OCR 文字或畫面資訊，不可杜撰。
2. 濃縮：主內容限制在 250–400 字（含中日文）。若資訊不足可降至 180 字。
3. 去重：語意相似度高於 0.85 的句子合併；避免同義句反覆。
4. 節奏：每條訊息只傳一個重點，句長超過 40 字請拆成兩句。
5. 中日雙欄：每條內容使用 `日文｜中文意譯` 格式，同一行呈現，中文要自然溝通口吻。
6. 不猜測：OCR 不確定或缺字時用「□」表示；禁止填補未出現的資訊。
7. 禁止套話：不要寫「這是很重要的概念」等空泛語句。
8. 終身一致：第一次出現的專有名詞需在中文後加括號備註日文（或反之），之後沿用同一翻法。
9. 素材不足時，可標記「（資訊不足）」並保留實際觀察到的內容；需要影音推測時加入「（圖片推測）」提醒。
10. 禁止輸出任何舊模板標題，例如：`# 課堂筆記`、`# 📚 講義筆記`、`## 🎯 課程主題`、`## 🔥 重點內容（紅色標記）`、`## 💻 程式碼詳解`、`## 核心日文術語詳解`、`## 💡 學習重點總結`、`## 🎓 延伸學習建議`、`## ⚠️ 常見錯誤與注意事項`、`重要詞彙表` 等。若出現上述任一字串代表嚴重違規，請立即改用新結構重新輸出。

輸出排版（Markdown）——固定順序（圖片筆記單元）：
0. `# 章節標題`（概念化標題，禁止直接貼 OCR；不要出現「投影片第 X 頁」）
1. 圖片由系統插入（請勿輸出圖片 Markdown）
2. `## ② 日文重點大綱（原講義語言）`
   - 條列 3–6 點，僅日文原文
   - 修正 OCR 錯字、斷句，可補齊缺主詞/述語
3. `## ③ 母語解析（中文）`
   - 教學式解釋：要說「為什麼」與「用在什麼地方」
   - 白話、可理解，不要翻譯腔
4. `## ④ 關鍵術語 / 名詞對照`（有技術名詞才出現）
   | 日文 | 中文 | 說明 |
   | --- | --- | --- |
   | ... | ... | ... |
5. `## ⑤ 程式碼 / 數學公式（若有）`
   - 程式碼必須使用 fenced code block，且必須帶語言標籤（例如 ```java）
   - 程式碼區塊後附 1–3 行「高亮提示」：用 `- 🔍` 開頭，指出關鍵行的作用
   - 數學用 `$...$` 或 `$$...$$`，公式下方加一句白話說明
6. `## ⑥ 補充說明 / 延伸理解`（可省略，但出現需有價值）

額外規則：
- 圖片一定由系統置頂插入；你只負責章節標題與文字區塊。
- 章節標題必須概念化（例如「行動策略的機率歸一化」）。
- 只輸出最終 Markdown 內容，不要加上任何前綴或結語。
- 重點先結論、後理由；避免空泛套話。
- 若內容不足，標記「（資訊不足）」並保留可觀察到的內容。
- 若無程式碼或公式，整個第 ⑤ 區塊省略。
- 若無術語，整個第 ④ 區塊省略。
- 無 OCR 時仍需描述圖片標題、清單或圖表結構。
- 輸出前檢查：若任何段落包含「講義筆記」「課程主題」「程式碼詳解」「核心日文術語」等舊模板用語，請自動刪除並改用新單元。
"""
    
    return prompt


def get_optimized_image_note_prompt_en(ocr_text, *, context="", has_ocr=True):
    """English version of optimized prompt"""
    ocr_text = ocr_text or ""
    ocr_snippet = ocr_text[:1600]
    context_snippet = (context or "").strip()[:800]
    has_useful_ocr = has_ocr and bool(ocr_snippet.strip())
    
    prompt_header = "You are a professional Japanese language instructor and formatting designer. Create highly scannable bilingual notes based on the provided information."

    if has_useful_ocr:
        ocr_block = f"OCR text snippet (truncated for quick reference):\n{ocr_snippet}\n"
    else:
        ocr_block = "⚠️ No usable OCR text detected. Please infer key points from visible elements and context only. Do not fabricate information.\n"

    context_block = f"\nSupplementary context (audio or surrounding paragraphs):\n{context_snippet}\n" if context_snippet else ""
    
    prompt = f"""{prompt_header}

{ocr_block}{context_block}

---

{_FORMAT_RULES_EN}

Core Principles (must follow each strictly):
1. Content Source: All points must come from OCR text or visible information. No fabrication.
2. Condensation: Main content limited to 250-400 characters (including Japanese/English). Can reduce to 180 if information is insufficient.
3. Deduplication: Merge sentences with semantic similarity > 0.85; avoid repetitive synonyms.
4. Rhythm: Each item conveys one point only. Split sentences longer than 40 words.
5. Bilingual Format: Use `Japanese｜English translation` format on same line, with natural conversational English.
6. No Guessing: Use "□" for uncertain OCR or missing characters; do not fill unverified information.
7. No Filler: Avoid empty phrases like "this is very important".
8. Consistency: First appearance of proper nouns needs parenthetical note (Japanese or English), then use same translation throughout.
9. Insufficient Material: Mark as "(insufficient info)" while keeping actual observations; add "(inferred from image)" when necessary.
10. Forbidden Old Templates: Never output old template headers like `# 課堂筆記`, `# 📚 講義筆記`, `## 🎯 課程主題`, `## 🔥 重點內容（紅色標記）`, `## 💻 程式碼詳解`, `## 核心日文術語詳解`, `## 💡 學習重點總結`, `## 🎓 延伸學習建議`, `## ⚠️ 常見錯誤與注意事項`, `重要詞彙表`, etc. If any appear, immediately regenerate with new structure.

Output Format (Markdown) - Fixed Order:
1. `## 🟢 Key Points`
   - List 3-5 items, each prefixed with `- 🔹 Japanese｜English`
   - If insufficient source, provide at least 3 (combine screen/title info)
2. `## 🔍 Examples`
   - Pick one representative example, using `- 🔹 Japanese｜English`
   - Skip entire section if no examples available
3. `## ⚠️ Counter-Examples`
   - Pick one common mistake or confusion point, same format; omit if none
4. Glossary (collapsible, only if truly important terms exist)
   ```
   <details class="terms" data-count="X">
   <summary>重要術語 X</summary>

   - 🔹 Japanese｜English
   - ...

   </details>
   ```
   - Only include 3-5 truly important technical terms. Skip common words, basic concepts, or repetitive phrases.
   - **NEVER include personal information** (student IDs, names, email addresses) as terms.
   - **NEVER include system-generated content** (file paths, timestamps, URLs) as terms.
   - If no significant technical terms exist, omit this section entirely.
5. Practice Exercises (collapsible, only if meaningful exercises exist)
   ```
   <details class="practice" data-count="Y">
   <summary>練習題 Y</summary>

   1. Japanese｜English
   2. ...

   </details>
   ```
   - Only include 1-2 meaningful exercises that test understanding or application.
   - Avoid generic questions or repetitive content.
   - If no suitable exercises exist, omit this section entirely.

Additional Rules:
- Key points, examples, counter-examples: "conclusion first, then reasoning".
- English paragraphs should be natural teaching tone, not literal translation.
- If line has >2 proper nouns, may break lines but maintain `Japanese｜English` format.
- For furigana or grammar explanations, only expand in glossary or practice sections.
- Without OCR, still describe visible titles, lists, or chart structure; describe layout if necessary.
- Before finishing: if any section contains old template terms like "講義筆記", "課程主題", "程式碼詳解", "核心日文術語", automatically delete and replace with new structure.

Output only the final Markdown content; avoid any prefacing/explanatory text (e.g., "Here is..."). If code is necessary, use fenced code blocks (```lang ... ```).
"""
    return prompt


def _localize_bilingual_prompt(prompt: str, translation_label: str) -> str:
    return prompt.replace("English", translation_label)


def get_optimized_image_note_prompt_ja(ocr_text, *, context="", has_ocr=True):
    """Japanese-only version of optimized prompt"""
    ocr_text = ocr_text or ""
    ocr_snippet = ocr_text[:1600]
    context_snippet = (context or "").strip()[:800]
    has_useful_ocr = has_ocr and bool(ocr_snippet.strip())

    prompt_header = "あなたは日本語の教育講師兼フォーマット設計者です。以下の情報に基づき、日本語のみで高可読な学習ノートを作成してください。"

    if has_useful_ocr:
        ocr_block = f"OCR テキスト（抜粋）：\n{ocr_snippet}\n"
    else:
        ocr_block = "⚠️ OCR で有効な文字が検出されませんでした。画像で確認できる情報のみから要点を整理し、推測で内容を捏造しないでください。\n"

    context_block = f"\n補足コンテキスト（音声/前後文脈）：\n{context_snippet}\n" if context_snippet else ""

    prompt = f"""{prompt_header}

{ocr_block}{context_block}

---

{_FORMAT_RULES_JA}

核心原則（厳守）：
1. すべての要点は OCR または画像から確認できる情報に限定する。
2. 主要内容は 250〜400 字程度（情報不足なら 180 字まで短縮可）。
3. 重複内容は統合し、同義の繰り返しを避ける。
4. 各項目は 1 トピックのみ。長文は分割。
5. **日本語のみ**で出力し、翻訳や区切り記号「｜」は使用しない。
6. 不確かな文字は「□」で表現する。
7. 旧テンプレートの見出しは一切使わない。

出力フォーマット（Markdown、固定順）：
1. `## 🟢 重要ポイント`
   - 3〜5 件、各行 `- 🔹 日本語のみ`
2. `## 🔍 例`
   - 例がある場合のみ記載
3. `## ⚠️ 誤り・反例`
   - 混同しやすい点がある場合のみ記載
4. 用語集（必要な場合のみ）
   ```
   <details class="terms" data-count="X">
   <summary>重要用語 X</summary>

   - 🔹 日本語のみ
   - ...

   </details>
   ```
5. 練習問題（必要な場合のみ）
   ```
   <details class="practice" data-count="Y">
   <summary>練習問題 Y</summary>

   1. 日本語のみ
   2. ...

   </details>
   ```

最終的な Markdown のみ出力し、前置き/結語は書かないこと。"""
    return prompt


def get_optimized_image_note_prompt_vi(ocr_text, *, context="", has_ocr=True):
    return _localize_bilingual_prompt(
        get_optimized_image_note_prompt_en(ocr_text, context=context, has_ocr=has_ocr),
        "Tiếng Việt",
    )


def get_optimized_image_note_prompt_my(ocr_text, *, context="", has_ocr=True):
    return _localize_bilingual_prompt(
        get_optimized_image_note_prompt_en(ocr_text, context=context, has_ocr=has_ocr),
        "မြန်မာ",
    )


def get_optimized_image_note_prompt_mn(ocr_text, *, context="", has_ocr=True):
    return _localize_bilingual_prompt(
        get_optimized_image_note_prompt_en(ocr_text, context=context, has_ocr=has_ocr),
        "Монгол",
    )


def get_optimized_image_note_prompt_ko(ocr_text, *, context="", has_ocr=True):

    """Korean version of optimized prompt"""
    ocr_text = ocr_text or ""
    ocr_snippet = ocr_text[:1600]
    context_snippet = (context or "").strip()[:800]
    has_useful_ocr = has_ocr and bool(ocr_snippet.strip())
    
    prompt_header = "당신은 전문 일본어 교육 강사이자 포맷 디자이너입니다. 제공된 정보를 바탕으로 스캔 효율이 높은 이중 언어 노트를 작성하세요."

    if has_useful_ocr:
        ocr_block = f"OCR 텍스트 발췌 (빠른 참조를 위해 잘림):\n{ocr_snippet}\n"
    else:
        ocr_block = "⚠️ 사용 가능한 OCR 텍스트가 감지되지 않았습니다. 보이는 요소와 맥락에서만 요점을 추론하세요. 허위 정보를 만들지 마세요.\n"

    context_block = f"\n보충 맥락 (음성 또는 전후 단락):\n{context_snippet}\n" if context_snippet else ""
    
    prompt = f"""{prompt_header}

{ocr_block}{context_block}

---

{_FORMAT_RULES_KO}

핵심 원칙 (각 항목을 엄격히 준수):
1. 콘텐츠 출처: 모든 요점은 OCR 텍스트 또는 보이는 정보에서만 가져와야 합니다. 허위 작성 금지.
2. 압축: 주요 내용은 250-400자로 제한 (일본어/한국어 포함). 정보 부족 시 180자까지 감소 가능.
3. 중복 제거: 의미 유사도 > 0.85인 문장 병합; 반복적인 동의어 피하기.
4. 리듬: 각 항목은 하나의 요점만 전달. 40자 이상 문장은 분할.
5. 이중 언어 형식: `일본어｜한국어 번역` 형식을 같은 줄에 사용, 자연스러운 대화체 한국어.
6. 추측 금지: 불확실한 OCR이나 누락 문자는 "□" 사용; 검증되지 않은 정보 채우기 금지.
7. 빈말 금지: "이것은 매우 중요합니다"와 같은 공허한 표현 피하기.
8. 일관성: 고유명사 첫 등장 시 괄호로 주석 필요 (일본어 또는 한국어), 이후 동일 번역 사용.
9. 자료 부족: "(정보 부족)"으로 표시하고 실제 관찰 내용 유지; 필요 시 "(이미지에서 추론)" 추가.
10. 금지된 구 템플릿: `# 課堂筆記`, `# 📚 講義筆記`, `## 🎯 課程主題`, `## 🔥 重點內容（紅色標記）`, `## 💻 程式碼詳解`, `## 核心日文術語詳解`, `## 💡 學習重點總結`, `## 🎓 延伸學習建議`, `## ⚠️ 常見錯誤與注意事項`, `重要詞彙表` 등 구 템플릿 헤더 절대 출력 금지. 나타나면 즉시 새 구조로 재생성.

출력 형식 (Markdown) - 고정 순서:
1. `## 🟢 핵심 포인트`
   - 3-5개 항목 나열, 각각 `- 🔹 일본어｜한국어` 접두사
   - 출처 부족 시 최소 3개 제공 (화면/제목 정보 결합)
2. `## 🔍 예시`
   - 대표 예시 하나 선택, `- 🔹 일본어｜한국어` 사용
   - 예시 없으면 전체 섹션 생략
3. `## ⚠️ 반례`
   - 흔한 실수나 혼동 포인트 하나 선택, 동일 형식; 없으면 생략
4. 용어집 (접을 수 있음, X를 실제 개수로 교체)
   ```
   <details class="terms" data-count="X">
   <summary>용어 X</summary>

   - 🔹 일본어｜한국어
   - ...

   </details>
   ```
   - 최대 5개 항목; 정말 중요한 용어만 포함. 일반 단어 생략.
5. 연습 문제 (접을 수 있음, Y를 실제 개수로 교체)
   ```
   <details class="practice" data-count="Y">
   <summary>연습 Y</summary>

   1. 일본어｜한국어
   2. ...

   </details>
   ```
   - 최대 2개 항목, 이해/적용에 초점. 적합한 연습 없으면 생략.

추가 규칙:
- 핵심 포인트, 예시, 반례: "결론 먼저, 그 다음 이유".
- 한국어 단락은 자연스러운 교육 어조, 직역 아님.
- 줄에 고유명사 >2개 있으면 줄 바꿈 가능하지만 `일본어｜한국어` 형식 유지.
- 후리가나나 문법 설명은 용어집이나 연습 섹션에서만 확장.
- OCR 없이도 보이는 제목, 목록, 차트 구조 설명; 필요시 레이아웃 설명.
- 마무리 전 확인: 섹션에 "講義筆記", "課程主題", "程式碼詳解", "核心日文術語" 등 구 템플릿 용어 포함 시 자동 삭제 후 새 구조로 교체.

최종 Markdown 콘텐츠만 출력하고 불필요한 서문/설명은 금지합니다. 코드가 필요하면 fenced code block(```lang ... ```)을 사용하세요.
"""
    return prompt


def get_optimized_image_note_prompt(
    ocr_text,
    language_code="zh-TW",
    *,
    context="",
    has_ocr=True,
    language_mode=None,
):
    """
    優化版多語言筆記生成 Prompt (當前主版本 - 2025-10-12)
    
    此版本為圖片筆記生成的主要 prompt,與 detailed_note_prompts.py (影片筆記) 格式統一。
    
    支援 8 種語言: zh-TW, zh-CN, en, ko, ja, vi, my, mn
    
    Args:
        ocr_text: OCR 辨識的文字
        language_code: 語言代碼
        context: 補充上下文
        has_ocr: 是否有 OCR 文字
    
    Returns:
        str: 針對該語言優化的 Prompt
    """
    if language_mode:
        normalized_mode = language_mode.strip().lower().replace("_", "-")
        if normalized_mode in {"ja-only", "japanese-only"}:
            language_code = "ja"

    # 語言映射表
    prompt_map = {
        "zh-TW": get_optimized_image_note_prompt_zh_tw,
        "zh-CN": get_optimized_image_note_prompt_zh_tw,  # 簡中暫時使用繁中版本
        "en": get_optimized_image_note_prompt_en,
        "ko": get_optimized_image_note_prompt_ko,
        "ja": get_optimized_image_note_prompt_ja,
        "vi": get_optimized_image_note_prompt_vi,
        "my": get_optimized_image_note_prompt_my,
        "mn": get_optimized_image_note_prompt_mn,
    }
    
    # 獲取對應語言的 prompt 函數
    prompt_func = prompt_map.get(language_code)
    
    if prompt_func:
        return prompt_func(ocr_text, context=context, has_ocr=has_ocr)
    else:
        # 未知語言回退到英文版本
        return get_optimized_image_note_prompt_en(ocr_text, context=context, has_ocr=has_ocr)


# 使用範例:
# from modules.llm_prompts_optimized import get_optimized_image_note_prompt
# prompt = get_optimized_image_note_prompt(ocr_text, "zh-TW")
