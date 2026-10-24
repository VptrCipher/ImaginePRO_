import os
import shutil
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALLATION_ID = hashlib.sha256(str(ROOT).casefold().encode('utf-8')).hexdigest()[:20]
STORAGE = Path(os.environ.get("VIDEO_EDITOR_STORAGE", ROOT / "storage")).resolve()
STORAGE.mkdir(parents=True, exist_ok=True)
MAX_UPLOAD = 500 * 1024 * 1024
MAX_SOURCE_SECONDS = 300
MAX_TIMELINE_SECONDS = 180


def binary(name: str) -> str:
    explicit = os.environ.get('NODE_BINARY_PATH' if name == 'node' else name.upper() + '_PATH')
    if explicit:
        return explicit
    found = shutil.which(name)
    if found:
        return found
    # winget updates the user PATH, but an already-running app retains its old PATH.
    if os.name == "nt":
        # Explorer/desktop shortcuts can retain an older PATH than the terminal.
        # Resolve installed executables each time so Codex app updates still work.
        if name == 'codex':
            codex_bin = Path(os.environ.get('LOCALAPPDATA', '')) / 'OpenAI/Codex/bin'
            candidates = sorted(codex_bin.glob('*/codex.exe'), key=lambda p: p.stat().st_mtime, reverse=True)
            if candidates:
                return str(candidates[0])
        if name == 'node':
            for base in [os.environ.get('ProgramFiles', ''), os.environ.get('LOCALAPPDATA', '')]:
                candidate = Path(base) / 'nodejs/node.exe'
                if candidate.is_file():
                    return str(candidate)
        packages = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft/WinGet/Packages"
        found_paths = list(packages.glob(f"Gyan.FFmpeg*/**/bin/{name}.exe"))
        if found_paths:
            os.environ["PATH"] = str(found_paths[0].parent) + os.pathsep + os.environ.get("PATH", "")
            return str(found_paths[0])
    raise RuntimeError(f"{name} is missing. See docs/SETUP.md.")


def animation_browser() -> str | None:
    explicit = os.environ.get('FRAMECRAFT_BROWSER_PATH')
    if explicit:
        return explicit if Path(explicit).is_file() else None
    choices = [Path(os.environ.get('LOCALAPPDATA', '')) / 'Google/Chrome/Application/chrome.exe',
               Path(os.environ.get('ProgramFiles', 'C:/Program Files')) / 'Google/Chrome/Application/chrome.exe',
               Path(os.environ.get('ProgramFiles(x86)', 'C:/Program Files (x86)')) / 'Microsoft/Edge/Application/msedge.exe',
               Path('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')]
    return next((str(p) for p in choices if p.is_file()), None) or shutil.which('google-chrome') or shutil.which('chromium')


def project_dir(project_id: str) -> Path:
    import re
    if not re.fullmatch(r"[a-f0-9]{32}", project_id):
        raise ValueError("Invalid project identifier")
    p = STORAGE / "projects" / project_id
    p.mkdir(parents=True, exist_ok=True)
    return p
