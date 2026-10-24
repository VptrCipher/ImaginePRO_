import hashlib
import json
import os
import re
from pathlib import Path
from . import db
from .config import ROOT, STORAGE


def template_registry():
    path = ROOT / "templates/framecraft/Framecraft.md"
    if not path.is_file():
        return []
    return [{"id": "builtin_framecraft", "name": "Framecraft", "kind": "template", "default": True,
             "description": "Handmade print animation · Canvas frames · synchronized synthesized score",
             "path": str(path), "text": path.read_text(encoding="utf-8")}]


def skill_registry():
    catalog_path = ROOT / "skills/catalog.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8")) if catalog_path.is_file() else {}
    roots = [ROOT, ROOT / "skills", ROOT / ".agents/skills", Path.home() / ".agents/skills",
             Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")) / "skills"]
    roots += [Path(x).expanduser() for x in os.environ.get("VIDEO_EDITOR_SKILL_DIRS", "").split(os.pathsep) if x]
    if os.environ.get('IMAGINEPRO_DEMO')=='1': roots = roots[:3]
    found, seen = [], set()
    for root in roots:
        candidates = [root / "SKILL.md"] if root == ROOT else list(root.glob("*/SKILL.md"))
        for path in candidates:
            path = path.resolve()
            if path in seen or not path.is_file():
                continue
            seen.add(path)
            text = path.read_text(encoding="utf-8", errors="replace")
            name = re.search(r"^name:\s*[\"']?([^\n\"']+)", text, re.M)
            description = re.search(r"^description:\s*(.+)", text, re.M)
            curated = catalog.get(path.parent.name, {}) if path.parent.parent == (ROOT / "skills").resolve() else {}
            # User-wide directories also contain unrelated coding/admin skills.
            # Explicit project/custom roots are always included.
            if root in roots[3:5] and not re.search(r"\b(video|cinematic|caption|subtitle|editing|motion.graphics)\b", (name.group(1) if name else path.parent.name) + " " + (description.group(1) if description else ""), re.I):
                continue
            found.append({"id": "skill_" + hashlib.sha256(str(path).encode()).hexdigest()[:20],
                          "name": curated.get("name") or (name.group(1).strip() if name else path.parent.name),
                          "description": curated.get("description") or (description.group(1).strip()[:300] if description else "Manually installed skill"),
                          "kind": "skill", "path": str(path), "text": text[:50000],
                          "bundled": bool(curated), "slug": path.parent.name,
                          "source_url": curated.get("source_url")})
    # Keep the bundled style collection together, ahead of manually discovered skills.
    return sorted(found, key=lambda s: not s["bundled"])


def list_styles(project_id):
    skills = [{k: v for k, v in s.items() if k != "text"} for s in template_registry() + skill_registry()]
    with db.connect() as c:
        rows = c.execute("SELECT * FROM styles ORDER BY rowid DESC").fetchall()
    return skills + [{"id": r["id"], "name": r["name"], "kind": "reference", "description": "Reference-derived clean.md", "metadata": json.loads(r["metadata"])} for r in rows]


def style_text(style_id, project_id):
    if not style_id:
        return ""
    for template in template_registry():
        if template["id"] == style_id:
            return template["text"]
    for s in skill_registry():
        if s["id"] == style_id:
            # Instructions and resource inventory are supplied as text; no skill scripts are executed by the agent.
            base = Path(s["path"]).parent
            resources = list(base.glob("references/*.md"))[:6]
            supporting = "\n".join(f"\n## Supporting resource: {p.name}\n{p.read_text(encoding='utf-8', errors='replace')[:4000]}" for p in resources)
            helpers = [p.name for p in (base / "helpers").glob("*.py")]
            return s["text"] + supporting + "\nAvailable helper inventory (backend-supported operations only): " + json.dumps(helpers)
    with db.connect() as c:
        row = c.execute("SELECT directory FROM styles WHERE id=?", (style_id,)).fetchone()
    if not row:
        raise KeyError("Style not found")
    return (Path(row["directory"]) / "clean.md").read_text(encoding="utf-8")


def save_style(style_id, project_id, markdown):
    with db.connect() as c:
        row = c.execute("SELECT directory FROM styles WHERE id=?", (style_id,)).fetchone()
    if not row:
        raise ValueError("Only reference-derived clean.md profiles can be edited here")
    p = Path(row["directory"]) / "clean.md"
    p.write_text(markdown, encoding="utf-8")
