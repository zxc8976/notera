import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = Path(__file__).resolve().parents[1]
for path in (PROJECT_ROOT, BACKEND_ROOT):
    p = str(path)
    if p not in sys.path:
        sys.path.insert(0, p)


from source.backend.modules.summarize_video import _select_scenes_for_note_style


def test_meeting_style_keeps_all_detected_scenes():
    scenes = [{"index": i} for i in range(12)]
    selected = _select_scenes_for_note_style(scenes, "meeting")
    assert len(selected) == 12
