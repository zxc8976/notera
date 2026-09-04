import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = Path(__file__).resolve().parents[1]
for path in (PROJECT_ROOT, BACKEND_ROOT):
    p = str(path)
    if p not in sys.path:
        sys.path.insert(0, p)


from source.backend.modules.note_generator import NoteGenerator


def test_meeting_mode_outputs_scene_sections_without_code_blocks():
    generator = NoteGenerator(llm_config={})
    scene_data = [
        {
            "image_path_web": "/images/demo/scene_000.jpg",
            "summary": "会議では要件定義の確認を行った。```javascript\nconst x = 1\n```",
            "ocr_text": "要件定義\nスケジュール\n担当",
            "asr_text": "本日は要件定義とタスク分解を説明します。",
        },
        {
            "image_path_web": "/images/demo/scene_001.jpg",
            "summary": "次回までに担当者別の期限を確定する。",
            "ocr_text": "担当者\n期限\nレビュー",
            "asr_text": "次の会議までに期限を決めましょう。",
        },
    ]

    note = generator._build_meeting_minutes_from_scenes(scene_data, "zh-TW")

    assert "## 場景 1" in note
    assert "## 場景 2" in note
    assert "### 日文語音重點" in note
    assert "### 中文重點整理" in note
    assert "![會議截圖 1](/images/demo/scene_000.jpg)" in note
    assert "![會議截圖 2](/images/demo/scene_001.jpg)" in note
    assert "```" not in note
