import os
import tempfile
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
_storage = tempfile.TemporaryDirectory(prefix="video-editor-tests-")
os.environ["VIDEO_EDITOR_STORAGE"] = _storage.name
