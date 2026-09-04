def get_strict_image_note_prompt(ocr_text, language_code="zh-TW"):
    """
    DEPRECATED: 此函數已廢棄，請使用 llm_prompts_optimized.get_optimized_image_note_prompt
    
    此函數僅作為回退選項保留，不建議在新代碼中使用。
    
    原始功能：生成 ChatGPT 風格的結構化教學筆記
    根據講義類型自動選擇最佳模板：
    1. 📘 數學公式講義 - 逐條公式拆解 + 符號說明 + 成立條件 + 考點
    2. 💻 程式與知識講義 - 語法解析 + 功能說明 + 關鍵知識 + 延伸補充
    3. 🧩 問答題 - 題目原文 + 題意理解 + 解題步驟 + 最終答案
    """
    
    # 多語言標題和標籤
    section_titles = {
        "zh-TW": {
            "highlights": "📌 講義重點 (日文原文)", 
            "explanation": "📖 繁體中文詳解",
            "topic": "主題",
            "core_content": "核心內容",
            "vocab_table": "重要詞彙表",
            "what_is_this": "這頁在說什麼",
            "key_points": "重點說明",
            "why_important": "為什麼重要",
            "exam_focus": "考試重點",
            "japanese": "日文",
            "furigana": "假名",
            "chinese": "中文",
            "notes": "備註"
        },
        "ja": {
            "highlights": "📌 重要ポイント (日本語)", 
            "explanation": "📖 日本語説明",
            "topic": "トピック",
            "core_content": "核心内容",
            "vocab_table": "重要語彙表",
            "what_is_this": "このページの内容",
            "key_points": "ポイント説明",
            "why_important": "重要性",
            "exam_focus": "試験重点",
            "japanese": "日本語",
            "furigana": "ふりがな",
            "chinese": "日本語訳",  # 在日文模式下,這欄顯示日文翻譯
            "notes": "備考"
        },
        "en": {
            "highlights": "📌 Key Points (Japanese)", 
            "explanation": "📖 English Explanation",
            "topic": "Topic",
            "core_content": "Core Content",
            "vocab_table": "Important Vocabulary",
            "what_is_this": "What is this page about",
            "key_points": "Key Points",
            "why_important": "Why Important",
            "exam_focus": "Examination Focus",
            "japanese": "Japanese",
            "furigana": "Furigana",
            "chinese": "English Translation",  # 在英文模式下,這欄顯示英文翻譯
            "notes": "Notes"
        },
        "ko": {
            "highlights": "📌 주요 내용 (일본어)", 
            "explanation": "📖 한국어 설명",
            "topic": "주제",
            "core_content": "핵심 내용",
            "vocab_table": "중요 어휘표",
            "what_is_this": "이 페이지의 내용",
            "key_points": "주요 포인트",
            "why_important": "중요한 이유",
            "exam_focus": "시험 중점",
            "japanese": "일본어",
            "furigana": "후리가나",
            "chinese": "한국어 번역",  # 在韓文模式下,這欄顯示韓文翻譯
            "notes": "비고"
        },
        "zh-CN": {
            "highlights": "📌 讲义重点 (日文原文)", 
            "explanation": "📖 简体中文详解",
            "topic": "主题",
            "core_content": "核心内容",
            "vocab_table": "重要词汇表",
            "what_is_this": "这页在说什么",
            "key_points": "重点说明",
            "why_important": "为什么重要",
            "exam_focus": "考试重点",
            "japanese": "日文",
            "furigana": "假名",
            "chinese": "中文",
            "notes": "备注"
        },
        "vi": {
            "highlights": "📌 Điểm chính (Tiếng Nhật)", 
            "explanation": "📖 Giải thích tiếng Việt",
            "topic": "Chủ đề",
            "core_content": "Nội dung cốt lõi",
            "vocab_table": "Bảng từ vựng quan trọng",
            "what_is_this": "Trang này nói về gì",
            "key_points": "Điểm chính",
            "why_important": "Tại sao quan trọng",
            "exam_focus": "Trọng tâm thi",
            "japanese": "Tiếng Nhật",
            "furigana": "Furigana",
            "chinese": "Bản dịch tiếng Việt",
            "notes": "Ghi chú"
        },
        "my": {
            "highlights": "📌 အဓိက အချက်များ (ဂျပန်)", 
            "explanation": "📖 မြန်မာ ရှင်းလင်းချက်",
            "topic": "ခေါင်းစဉ်",
            "core_content": "အဓိက အကြောင်းအရာ",
            "vocab_table": "အရေးကြီး ဝေါဟာရ ဇယား",
            "what_is_this": "ဒီစာမျက်နှာက ဘာအကြောင်း",
            "key_points": "အဓိက အချက်များ",
            "why_important": "ဘာကြောင့် အရေးကြီးလဲ",
            "exam_focus": "စာမေးပွဲ အဓိက အချက်",
            "japanese": "ဂျပန်",
            "furigana": "ဖူရိဂါနာ",
            "chinese": "မြန်မာ ဘာသာပြန်",
            "notes": "မှတ်စု"
        },
        "mn": {
            "highlights": "📌 Гол санаанууд (Япон)", 
            "explanation": "📖 Монгол тайлбар",
            "topic": "Сэдэв",
            "core_content": "Үндсэн агуулга",
            "vocab_table": "Чухал үгсийн хүснэгт",
            "what_is_this": "Энэ хуудас юуны тухай",
            "key_points": "Гол санаанууд",
            "why_important": "Яагаад чухал вэ",
            "exam_focus": "Шалгалтын гол зүйлс",
            "japanese": "Япон",
            "furigana": "Фүригана",
            "chinese": "Монгол орчуулга",
            "notes": "Тэмдэглэл"
        }
    }
    labels = section_titles.get(language_code, section_titles["zh-TW"])
    ocr_snippet = ocr_text[:1600]
    core_instruction = (
        "[Use the actual OCR sentences from THIS image. Output 4-6 bullet items. For each item follow this exact structure:\\n"
        f"- {labels['japanese']}: <verbatim sentence copied from OCR (keep original notation/furigana)>\\n"
        f"  {labels['chinese']}: <precise translation or explanation in the target language>\\n"
        f"  {labels['why_important']}: <why this sentence matters in the slide context>\\n"
        "Skip fragments shorter than six characters or any line containing '...' or '…'. If the sentence includes equations, state/action sequences, or highlighted steps, explicitly describe each symbol, variable, and transition. If you cannot find enough valid sentences, state '(OCR unreadable—needs human review)' instead of fabricating text. Do not output single-word glossaries or generic statements; always cite real sentences from the slide.]"
    )
    key_instruction = (
        "Ensure every key point refers to one of the sentences already listed above. Name each key point with a concise concept taken from the quoted sentence—never output generic labels such as '第一個重點' or 'Point 1'. Replace any placeholder brackets with real content. If the page contains formulas or diagrams, dedicate at least one key point to break down the formula/diagram step-by-step."
    )
    table_instruction = (
        "Populate the table with actual terminology from the OCR above (aim for three rows). Skip generic symbols such as a_on, a_off, s_on, s_off unless this slide introduces a new definition. If fewer than three valid terms exist, list every available term and add '(only X unique terms detected)' in the notes column—never leave the table empty or keep sample text."
    )
    
    # 根據語言生成完整的提示詞(包括範例)
    if language_code == "ja":
        prompt = f"""この日本語の講義資料を分析して、学習ノートを作成してください。数式や状態遷移が含まれている場合は、各記号と遷移の意味を丁寧に説明してください。

OCR識別されたテキスト:
{ocr_snippet}

以下の内容を出力してください:

## {labels["highlights"]}

{labels["topic"]}: [このページの内容を一文で要約]

{labels["core_content"]}:
{core_instruction}

{labels["vocab_table"]}:
| {labels["japanese"]} | {labels["furigana"]} | {labels["chinese"]} | {labels["notes"]} |
|------|------|------|------|
| 運用 | うんよう | 運用管理 | IT用語 |
[実際の内容から抽出]

---

## {labels["explanation"]}

{labels["what_is_this"]}:
[2-3文でテーマを説明]

{labels["key_points"]}:
1. 第一のポイント
   - 日本語原文: [...]
   - 意味: [...]
   - {labels["why_important"]}: [...]

2. 第二のポイント
   - 日本語原文: [...]
   - 意味: [...]
   - {labels["why_important"]}: [...]

{key_instruction}

{labels["exam_focus"]}:
- ポイント1: [...]
- ポイント2: [...]

注意: 実際の内容のみを出力し、フォーマット説明は出力しないでください。"""
    
    elif language_code == "en":
        prompt = f"""Analyze this Japanese lecture material and create study notes.

OCR Recognized Text:
{ocr_snippet}

Produce the study notes using the structure below and obey these rules:
- Every core content item must quote a real sentence from the OCR snippet and follow the specified format.
- The vocabulary table must include at least three rows drawn from this slide.
- All key points and exam focus lines must reference sentences you have already cited. Do not invent content.

## {labels["highlights"]}

{labels["topic"]}: [Summarize this page in one precise sentence]

{labels["core_content"]}:
{core_instruction}

{labels["vocab_table"]}:
| {labels["japanese"]} | {labels["furigana"]} | {labels["chinese"]} | {labels["notes"]} |
|------|------|------|------|

---

## {labels["explanation"]}

{labels["what_is_this"]}:
[Explain the theme in 2-3 sentences, referencing the sentences above. If formulas/curves/diagrams appear, describe their structure and purpose.]

{labels["key_points"]}:
1. First Point
   - Japanese Original: [...]
   - Meaning: [...]
   - {labels["why_important"]}: [...]

2. Second Point
   - Japanese Original: [...]
   - Meaning: [...]
   - {labels["why_important"]}: [...]

{key_instruction}

{labels["exam_focus"]}:
- Point 1: [...]
- Point 2: [...]

Note: Output only actual content, do not output format explanations."""

    elif language_code == "ko":
        prompt = f"""이 일본어 강의 자료를 분석하여 학습 노트를 작성하세요.

OCR 인식된 텍스트:
{ocr_snippet}

아래 구조와 규칙을 따라 실제 내용을 작성하세요:
- 핵심 내용의 각 항목은 OCR 문장을 그대로 인용하고 지정된 형식을 따르세요.
- 어휘 표에는 이 페이지에서 추출한 용어를 최소 3행 이상 기입하세요.
- 핵심 포인트와 시험 포인트는 이미 인용한 문장을 참조해야 하며, 새로운 내용을 만들면 안 됩니다.

## {labels["highlights"]}

{labels["topic"]}: [이 페이지의 핵심을 한 문장으로 정확히 요약]

{labels["core_content"]}:
{core_instruction}

{labels["vocab_table"]}:
| {labels["japanese"]} | {labels["furigana"]} | {labels["chinese"]} | {labels["notes"]} |
|------|------|------|------|

---

## {labels["explanation"]}

{labels["what_is_this"]}:
[위에서 인용한 문장을 바탕으로 2-3문장으로 설명하세요.]

{labels["key_points"]}:
1. 첫 번째 포인트
   - 일본어 원문: [...]
   - 의미: [...]
   - {labels["why_important"]}: [...]

2. 두 번째 포인트
   - 일본어 원문: [...]
   - 의미: [...]
   - {labels["why_important"]}: [...]

{key_instruction}

{labels["exam_focus"]}:
- 포인트 1: [...]
- 포인트 2: [...]

주의: 실제 내용만 출력하고, 형식 설명은 출력하지 마세요."""

    else:  # 繁體中文, 簡體中文, 越南文, 緬甸文, 蒙古文
        if language_code == "zh-CN":
            instruction = "分析这张日文讲义,生成学习笔记。"
            example_items = [
                "- はじめに(はじめに) → 开始",
                "- サーバ運用(うんよう) → 服务器维护管理",
                "- いつでも使える(つかえる) → 随时可用",
                "- 壊れても大丈夫(こわれてもだいじょうぶ) → 坏了也没关系"
            ]
            format_instruction = "[直接从OCR提取实际的日文内容,所有项目都必须使用「日文(假名) → 中文翻译」格式]"
            vocab_example = "| 運用 | うんよう | 维护管理 | IT术语 |"
            explanation_instruction = "[2-3句话说明主题]"
            point_labels = ["第一个重点", "第二个重点"]
            original_label = "日文原文"
            meaning_label = "意思"
            focus_label = "重点"
            note_instruction = "注意: 只输出实际内容,不要输出格式说明。"
        elif language_code == "vi":
            instruction = "Phân tích tài liệu giảng dạy tiếng Nhật này và tạo ghi chú học tập."
            example_items = [
                "- はじめに(はじめに) → Bắt đầu",
                "- サーバ運用(うんよう) → Quản lý vận hành máy chủ",
                "- いつでも使える(つかえる) → Có thể sử dụng bất cứ lúc nào",
                "- 壊れても大丈夫(こわれてもだいじょうぶ) → Không sao nếu hỏng"
            ]
            format_instruction = "[Trích xuất nội dung tiếng Nhật thực tế từ OCR, TẤT CẢ các mục phải tuân theo định dạng: Tiếng Nhật(furigana) → Bản dịch]"
            vocab_example = "| 運用 | うんよう | Vận hành | Thuật ngữ IT |"
            explanation_instruction = "[Giải thích chủ đề trong 2-3 câu]"
            point_labels = ["Điểm thứ nhất", "Điểm thứ hai"]
            original_label = "Tiếng Nhật gốc"
            meaning_label = "Ý nghĩa"
            focus_label = "Điểm"
            note_instruction = "Lưu ý: Chỉ xuất nội dung thực tế, không xuất giải thích định dạng."
        elif language_code == "my":
            instruction = "ဒီ ဂျပန် စာသင်ခန်း အရာကို ခွဲခြမ်းစိတ်ဖြာပြီး သင်ယူမှု မှတ်စုများ ဖန်တီးပါ။"
            example_items = [
                "- はじめに(はじめに) → စတင်ခြင်း",
                "- サーバ運用(うんよう) → ဆာဗာ စီမံခန့်ခွဲမှု",
                "- いつでも使える(つかえる) → အချိန်မရွေး သုံးနိုင်သည်",
                "- 壊れても大丈夫(こわれてもだいじょうぶ) → ပျက်စီးသွားလျှင် အဆင်ပြေသည်"
            ]
            format_instruction = "[OCR မှ အမှန်တကယ် ဂျပန် အကြောင်းအရာကို ထုတ်ယူပြီး၊ အရာအားလုံးသည် ဖော်မတ်ကို လိုက်နာရမည်: ဂျပန်(ဖူရိဂါနာ) → ဘာသာပြန်]"
            vocab_example = "| 運用 | うんよう | စီမံခန့်ခွဲမှု | IT ဝေါဟာရ |"
            explanation_instruction = "[ခေါင်းစဉ်ကို ၂-၃ စာကြောင်းဖြင့် ရှင်းပြပါ]"
            point_labels = ["ပထမ အချက်", "ဒုတိယ အချက်"]
            original_label = "ဂျပန် မူရင်း"
            meaning_label = "အဓိပ္ပာယ်"
            focus_label = "အချက်"
            note_instruction = "သတိပြုရန်: အမှန်တကယ် အကြောင်းအရာကိုသာ ထုတ်ပြပါ၊ ဖော်မတ် ရှင်းလင်းချက်များကို မထုတ်ပြပါနှင့်။"
        elif language_code == "mn":
            instruction = "Энэ япон хичээлийн материалыг шинжилж, сургалтын тэмдэглэл үүсгэнэ үү."
            example_items = [
                "- はじめに(はじめに) → Эхлэл",
                "- サーバ運用(うんよう) → Сервер удирдлага",
                "- いつでも使える(つかえる) → Хэзээ ч ашиглаж болно",
                "- 壊れても大丈夫(こわれてもだいじょうぶ) → Эвдрэлээ ч зүгээр"
            ]
            format_instruction = "[OCR-аас бодит япон агуулгыг гаргаж аваад, БҮГД формат дагаж байх ёстой: Япон(фүригана) → Орчуулга]"
            vocab_example = "| 運用 | うんよう | Удирдлага | IT нэр томьёо |"
            explanation_instruction = "[Сэдвийг 2-3 өгүүлбэрээр тайлбарлана уу]"
            point_labels = ["Эхний санаа", "Хоёрдугаар санаа"]
            original_label = "Япон эх бичвэр"
            meaning_label = "Утга"
            focus_label = "Санаа"
            note_instruction = "Анхаарах: Зөвхөн бодит агуулгыг гаргах, формат тайлбарыг бүү гаргаарай."
        else:  # zh-TW
            instruction = "分析這張日文講義,生成學習筆記。請針對公式、流程圖與理論敘述逐步解釋，並確保所有欄位都填入實際內容。"
            example_items = [
                "- はじめに(はじめに) → 開始",
                "- サーバ運用(うんよう) → 伺服器維護管理",
                "- いつでも使える(つかえる) → 隨時可用",
                "- 壊れても大丈夫(こわれてもだいじょうぶ) → 壞了也沒關係"
            ]
            format_instruction = "[直接從OCR提取實際的日文句子,所有項目都必須使用「日文(假名) → 中文翻譯」格式,並補充公式/符號意義。若句子破碎或含有「...」請跳過。]"
            vocab_example = "| 運用 | うんよう | 維護管理 | IT術語 |"
            explanation_instruction = "[2-3句話說明主題]"
            point_labels = [
                "請以上方句子的主題詞命名此重點（勿輸出本句）",
                "請再以不同句子的主題詞命名此重點（勿輸出本句）"
            ]
            original_label = "日文原文"
            meaning_label = "意思"
            focus_label = "重點"
            note_instruction = "注意: 只輸出實際內容,不要輸出格式說明；常見符號(如 a_on、S_off)若無新定義可省略；所有方括號與「第一個重點」等占位文字都必須用實際內容取代，無法辨識時請寫「（待補：OCR 無法辨識）」。"

        extra_rules = {
            "zh-TW": "若 OCR 或結構化摘要顯示公式、程式碼或箭頭流程，務必逐步推導並解釋其意義與操作步驟。",
            "zh-CN": "若 OCR 或结构化摘要出现公式、代码或箭头流程，必须逐步推导并说明其意义与操作步骤。",
            "ja": "OCRや要約に数式・コード・矢印フローが含まれる場合は、必ず段階的に解説してください。",
            "en": "If the OCR/summary highlights formulas, code, or arrow flows, provide step-by-step derivations and explain the transitions.",
            "ko": "OCR나 요약에 수식·코드·화살표 흐름이 있다면 단계별로 풀이하고 상태 변화를 설명하세요.",
            "vi": "Nếu OCR/tóm tắt có công thức, mã hoặc sơ đồ mũi tên, hãy giải thích từng bước và nêu ý nghĩa chuyển đổi.",
            "my": "If the OCR/summary shows formulas, code, or arrow flows, explain them step by step in Burmese or English.",
            "mn": "If OCR/summary contains formulas, code or flow arrows, describe each step and its meaning.",
        }
        extra_rule_text = extra_rules.get(language_code, extra_rules["en"])
        instruction = f"{instruction}\n{extra_rule_text}"
        
        prompt = f"""{instruction}

OCR辨識文字:
{ocr_snippet}

請依照下列結構輸出實際內容,並遵守這些規則:
- 核心內容的每個項目都要引用實際句子,並使用指定格式。
- 語彙表至少列出三列,全部取自本頁 OCR 的專有詞彙。
- 重點說明與考試重點必須引用前面列出的句子,不得新增或改寫內容。
- 任何冒號或表格欄位後不得留空或保留「[...]」提示；若無內容可寫「（待補：OCR 無法辨識）」。
- 禁止輸出任何警告語或提醒（例如「⚠️ 自動解析未能擷取可靠的日文重點」）；若缺資料請在對應欄位使用「（待補：OCR 無法辨識）」或 '(OCR unreadable—needs human review)'。

## {labels["highlights"]}

{labels["topic"]}: [用一個句子精確描述本頁的主題與重點]

{labels["core_content"]}:
{core_instruction}

{labels["vocab_table"]}:
| {labels["japanese"]} | {labels["furigana"]} | {labels["chinese"]} | {labels["notes"]} |
|------|------|------|------|

---

## {labels["explanation"]}

{labels["what_is_this"]}:
[以 2-3 句話描述這頁內容，必須引用上面列出的句子，不要新增資料。]

{labels["key_points"]}:
1. {point_labels[0]}
   - {original_label}: [...]
   - {meaning_label}: [...]
   - {labels["why_important"]}: [...]

2. {point_labels[1]}
   - {original_label}: [...]
   - {meaning_label}: [...]
   - {labels["why_important"]}: [...]

{key_instruction}

{labels["exam_focus"]}:
- {focus_label}1: [...]
- {focus_label}2: [...]

{note_instruction}"""
    
    return prompt


def get_strict_video_note_prompt(scene_texts, language_code="zh-TW"):
    """
    DEPRECATED: 此函數已廢棄，請使用 detailed_note_prompts.build_detailed_prompt
    
    此函數僅作為回退選項保留，不建議在新代碼中使用。
    
    原始功能：生成影片筆記的嚴格提示詞 - 多語言支持
    """
    # 多語言標籤
    labels = {
        "zh-TW": {
            "highlights": "日文重點", 
            "explanation": "繁體中文說明",
            "instruction": "從以下課程內容中提取學習筆記:",
            "extract_sentences": "從上面內容中提取 3-5 個**實際出現**的日文句子,每個句子用 • 開頭:",
            "core_concept": "核心概念",
            "core_concept_desc": "用 2-3 句話說明這段內容在講什麼。只說明**實際內容**,不要編造。",
            "code_example": "程式碼範例",
            "code_desc": "如果有程式碼,複製貼上。如果沒有,寫「本節無程式碼」。",
            "summary": "重點整理",
            "rules": "重要規則",
            "rule1": "只使用上面提供的內容",
            "rule2": "不要發明不存在的內容",
            "rule3": "如果是課堂指示就說課堂指示,如果是程式設計就說程式設計",
            "rule4": "直接複製日文原文,不要改寫"
        },
        "ja": {
            "highlights": "日本語の要点", 
            "explanation": "日本語説明",
            "instruction": "以下の授業内容から学習ノートを抽出:",
            "extract_sentences": "上記の内容から実際に出現した日本語の文章を3〜5個抽出し、各文章の前に • を付けます:",
            "core_concept": "核心概念",
            "core_concept_desc": "この内容が何について説明しているかを2〜3文で説明してください。実際の内容のみを説明し、作り話はしないでください。",
            "code_example": "コード例",
            "code_desc": "コードがある場合はコピーして貼り付けてください。ない場合は「本節にコードはありません」と書いてください。",
            "summary": "ポイントまとめ",
            "rules": "重要なルール",
            "rule1": "上記の提供された内容のみを使用する",
            "rule2": "存在しない内容を作らない",
            "rule3": "授業の指示であれば授業の指示と言い、プログラミングであればプログラミングと言う",
            "rule4": "日本語の原文を直接コピーし、書き換えない"
        },
        "en": {
            "highlights": "Japanese Highlights", 
            "explanation": "English Explanation",
            "instruction": "Extract study notes from the following course content:",
            "extract_sentences": "Extract 3-5 Japanese sentences that actually appear above, prefix each with •:",
            "core_concept": "Core Concept",
            "core_concept_desc": "Explain what this content is about in 2-3 sentences. Only explain **actual content**, don't make up.",
            "code_example": "Code Example",
            "code_desc": "If there is code, copy and paste it. If not, write 'No code in this section'.",
            "summary": "Key Points",
            "rules": "Important Rules",
            "rule1": "Only use the content provided above",
            "rule2": "Don't invent content that doesn't exist",
            "rule3": "If it's class instructions, say class instructions; if it's programming, say programming",
            "rule4": "Copy Japanese text directly, don't rewrite"
        },
        "ko": {
            "highlights": "일본어 요점", 
            "explanation": "한국어 설명",
            "instruction": "다음 강의 내용에서 학습 노트 추출:",
            "extract_sentences": "위 내용에서 실제로 나타난 일본어 문장 3-5개를 추출하고 각 문장 앞에 •를 붙입니다:",
            "core_concept": "핵심 개념",
            "core_concept_desc": "이 내용이 무엇에 대한 것인지 2-3문장으로 설명하십시오. **실제 내용**만 설명하고 만들어내지 마십시오.",
            "code_example": "코드 예제",
            "code_desc": "코드가 있으면 복사하여 붙여넣으십시오. 없으면 '이 섹션에는 코드가 없습니다'라고 작성하십시오.",
            "summary": "요점 정리",
            "rules": "중요한 규칙",
            "rule1": "위에 제공된 내용만 사용",
            "rule2": "존재하지 않는 내용을 만들지 마십시오",
            "rule3": "수업 지시사항이면 수업 지시사항이라고 말하고, 프로그래밍이면 프로그래밍이라고 말하십시오",
            "rule4": "일본어 원문을 직접 복사하고 다시 쓰지 마십시오"
        },
        "zh-CN": {
            "highlights": "日文重点", 
            "explanation": "简体中文说明",
            "instruction": "从以下课程内容中提取学习笔记:",
            "extract_sentences": "从上面内容中提取 3-5 个**实际出现**的日文句子,每个句子用 • 开头:",
            "core_concept": "核心概念",
            "core_concept_desc": "用 2-3 句话说明这段内容在讲什么。只说明**实际内容**,不要编造。",
            "code_example": "程序代码范例",
            "code_desc": "如果有代码,复制粘贴。如果没有,写「本节无代码」。",
            "summary": "重点整理",
            "rules": "重要规则",
            "rule1": "只使用上面提供的内容",
            "rule2": "不要发明不存在的内容",
            "rule3": "如果是课堂指示就说课堂指示,如果是程序设计就说程序设计",
            "rule4": "直接复制日文原文,不要改写"
        }
    }
    
    lang = labels.get(language_code, labels["zh-TW"])
    
    # 合併所有場景文字
    combined_text = "\n\n".join(scene_texts) if isinstance(scene_texts, list) else str(scene_texts)
    
    prompt = f"""{lang["instruction"]}

{combined_text}

請按照以下格式輸出:

## {lang["highlights"]}

{lang["extract_sentences"]}
• [日文句子1] - [翻譯]
• [日文句子2] - [翻譯]
• [日文句子3] - [翻譯]

{{{{image_placeholder}}}}

## {lang["explanation"]}

### 1. {lang["core_concept"]}
{lang["core_concept_desc"]}

### 2. {lang["code_example"]}
{lang["code_desc"]}

### 3. {lang["summary"]}
• 重點1
• 重點2
• 重點3

{lang["rules"]}:
1. {lang["rule1"]}
2. {lang["rule2"]}
3. {lang["rule3"]}
4. {lang["rule4"]}
"""
    
    return prompt
