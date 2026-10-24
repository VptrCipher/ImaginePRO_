import json
import sqlite3
import threading
import time
import uuid
from .config import STORAGE

LOCK = threading.RLock()


class ClosingConnection(sqlite3.Connection):
    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


def uid():
    return uuid.uuid4().hex


def connect():
    con = sqlite3.connect(STORAGE / "editor.sqlite3", timeout=30, factory=ClosingConnection)
    con.row_factory = sqlite3.Row
    return con


def init():
    with connect() as c:
        c.executescript('''
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY, name TEXT, revision INTEGER, timeline TEXT, created REAL);
        CREATE TABLE IF NOT EXISTS assets(id TEXT PRIMARY KEY, project_id TEXT, name TEXT, path TEXT, kind TEXT, metadata TEXT);
        CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, project_id TEXT, kind TEXT, status TEXT, progress REAL, message TEXT, payload TEXT, result TEXT, error TEXT, created REAL);
        CREATE TABLE IF NOT EXISTS styles(id TEXT PRIMARY KEY, project_id TEXT, name TEXT, directory TEXT, metadata TEXT);
        ''')
        c.execute("UPDATE jobs SET status='failed',error='Application restarted. Retry this job.' WHERE status IN ('queued','running')")


def create_project(name):
    from .models import Timeline
    key = uid()
    with connect() as c:
        c.execute("INSERT INTO projects VALUES(?,?,?,?,?)", (key, name, 0, Timeline().model_dump_json(), time.time()))
    return project(key)


def project(key):
    with connect() as c:
        row = c.execute("SELECT * FROM projects WHERE id=?", (key,)).fetchone()
        assets = c.execute("SELECT * FROM assets WHERE project_id=? ORDER BY rowid", (key,)).fetchall()
    if not row:
        raise KeyError("Project not found")
    result = dict(row)
    result["timeline"] = json.loads(result["timeline"])
    result["assets"] = [asset_dict(a) for a in assets]
    return result


def asset_dict(row):
    a = dict(row)
    a["metadata"] = json.loads(a["metadata"])
    a.pop("path", None)
    a["url"] = f"/api/projects/{a['project_id']}/assets/{a['id']}/file"
    a["thumbnail_url"] = f"/api/projects/{a['project_id']}/assets/{a['id']}/thumbnail"
    return a


def asset(key, project_id):
    with connect() as c:
        row = c.execute("SELECT * FROM assets WHERE id=? AND project_id=?", (key, project_id)).fetchone()
    if not row:
        raise KeyError("Media not found in this project")
    a = dict(row)
    a["metadata"] = json.loads(a["metadata"])
    return a


def save_timeline(key, revision, timeline):
    with LOCK, connect() as c:
        updated = c.execute("UPDATE projects SET timeline=?,revision=revision+1 WHERE id=? AND revision=?", (timeline.model_dump_json(), key, revision))
        if updated.rowcount != 1:
            raise ValueError("Project changed. Reload before saving this edit.")
    return project(key)


def job(key):
    with connect() as c:
        row = c.execute("SELECT * FROM jobs WHERE id=?", (key,)).fetchone()
    if not row:
        raise KeyError("Job not found")
    j = dict(row)
    j["payload"] = json.loads(j["payload"])
    j["result"] = json.loads(j["result"]) if j["result"] else None
    return j


def update_job(key, **values):
    allowed = {"status", "progress", "message", "result", "error"}
    assert values.keys() <= allowed
    if "result" in values:
        values["result"] = json.dumps(values["result"], ensure_ascii=False)
    with connect() as c:
        c.execute(f"UPDATE jobs SET {','.join(k+'=?' for k in values)} WHERE id=?", (*values.values(), key))
