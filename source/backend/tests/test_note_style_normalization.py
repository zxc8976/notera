import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = Path(__file__).resolve().parents[1]
for path in (PROJECT_ROOT, BACKEND_ROOT):
    p = str(path)
    if p not in sys.path:
        sys.path.insert(0, p)


from source.backend.app.main import _normalize_requested_note_style


def test_normalize_requested_note_style_accepts_legacy_meetingmode():
    assert _normalize_requested_note_style("meetingMode") == "meeting"


def test_normalize_requested_note_style_accepts_legacy_lecturemode():
    assert _normalize_requested_note_style("lectureMode") == "lecture"
