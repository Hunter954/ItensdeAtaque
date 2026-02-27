import base64
import json
import threading
from datetime import datetime, timezone
import requests
from flask import current_app

_lock = threading.Lock()
_CACHE = None
_CACHE_SHA = None
_CACHE_ETAG = None

def _utcnow_iso():
    return datetime.now(timezone.utc).isoformat()

def seed_data():
    # 5 teams/managers, some sellers & items, one current period, one admin+managers
    teams = [
        {"id": "t1", "name": "Equipe Norte", "manager_name": "Ana Souza", "manager_photo_url": "https://via.placeholder.com/256?text=Ana"},
        {"id": "t2", "name": "Equipe Sul", "manager_name": "Bruno Lima", "manager_photo_url": "https://via.placeholder.com/256?text=Bruno"},
        {"id": "t3", "name": "Equipe Leste", "manager_name": "Carla Mendes", "manager_photo_url": "https://via.placeholder.com/256?text=Carla"},
        {"id": "t4", "name": "Equipe Oeste", "manager_name": "Diego Rocha", "manager_photo_url": "https://via.placeholder.com/256?text=Diego"},
        {"id": "t5", "name": "Equipe Centro", "manager_name": "Eva Martins", "manager_photo_url": "https://via.placeholder.com/256?text=Eva"},
    ]

    sellers = [
        {"id": "s1", "name": "João", "team_id": "t1", "photo_url": "https://via.placeholder.com/256?text=Joao"},
        {"id": "s2", "name": "Mariana", "team_id": "t1", "photo_url": "https://via.placeholder.com/256?text=Mariana"},
        {"id": "s3", "name": "Pedro", "team_id": "t2", "photo_url": "https://via.placeholder.com/256?text=Pedro"},
        {"id": "s4", "name": "Lívia", "team_id": "t2", "photo_url": "https://via.placeholder.com/256?text=Livia"},
        {"id": "s5", "name": "Rafa", "team_id": "t3", "photo_url": "https://via.placeholder.com/256?text=Rafa"},
    ]

    items = [
        {"id": "i1", "name": "Produto A", "photo_url": "https://via.placeholder.com/256?text=Produto+A", "video_url": ""},
        {"id": "i2", "name": "Produto B", "photo_url": "https://via.placeholder.com/256?text=Produto+B", "video_url": ""},
        {"id": "i3", "name": "Produto C", "photo_url": "https://via.placeholder.com/256?text=Produto+C", "video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
    ]

    # current period (month)
    now = datetime.now(timezone.utc)
    period_id = now.strftime("p%Y%m")
    periods = [
        {"id": period_id, "name": now.strftime("%B %Y"), "is_current": True, "created_at": _utcnow_iso()},
    ]

    # Minimal company settings
    company = {
        "name": "Minha Empresa",
        "logo_url": "https://via.placeholder.com/256?text=LOGO",
        "watermark_url": "https://via.placeholder.com/256?text=WATERMARK",
    }

    # Users: managers seeded with password 'manager123' (hashed on server at first load if missing hash)
    users = [
        {"email": "manager.norte@example.com", "role": "MANAGER", "team_id": "t1", "password_hash": ""},
        {"email": "manager.sul@example.com", "role": "MANAGER", "team_id": "t2", "password_hash": ""},
        {"email": "manager.leste@example.com", "role": "MANAGER", "team_id": "t3", "password_hash": ""},
        {"email": "manager.oeste@example.com", "role": "MANAGER", "team_id": "t4", "password_hash": ""},
        {"email": "manager.centro@example.com", "role": "MANAGER", "team_id": "t5", "password_hash": ""},
    ]

    sales = {period_id: {}}
    for t in teams:
        sales[period_id][t["id"]] = {}
        for s in [x for x in sellers if x["team_id"] == t["id"]]:
            sales[period_id][t["id"]][s["id"]] = {it["id"]: 0 for it in items}

    return {
        "meta": {"created_at": _utcnow_iso(), "updated_at": _utcnow_iso()},
        "company": company,
        "teams": teams,
        "sellers": sellers,
        "items": items,
        "periods": periods,
        "users": users,
        "sales": sales,
        "audit": [],
    }

def _headers(token: str):
    h = {"Accept": "application/vnd.github+json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h

def _contents_url(repo: str, path: str):
    return f"https://api.github.com/repos/{repo}/contents/{path}"

def load_data(force: bool = False):
    """Load JSON from GitHub into memory cache. If missing, create seed and commit it."""
    global _CACHE, _CACHE_SHA, _CACHE_ETAG
    with _lock:
        if _CACHE is not None and not force:
            return _CACHE

        cfg = current_app.config if current_app else None
        # Allow calling before app context by reading env via os
        import os
        token = (cfg.get("GITHUB_TOKEN") if cfg else os.environ.get("GITHUB_TOKEN", "")) or ""
        repo = (cfg.get("GITHUB_REPO") if cfg else os.environ.get("GITHUB_REPO", "")) or ""
        branch = (cfg.get("GITHUB_BRANCH") if cfg else os.environ.get("GITHUB_BRANCH", "main")) or "main"
        gh_path = (cfg.get("GITHUB_PATH") if cfg else os.environ.get("GITHUB_PATH", "data/sales-grid.json")) or "data/sales-grid.json"

        if not repo:
            # No repo configured: keep in-memory only (dev mode)
            if _CACHE is None:
                _CACHE = seed_data()
            return _CACHE

        url = _contents_url(repo, gh_path)
        r = requests.get(url, headers=_headers(token), params={"ref": branch}, timeout=20)

        if r.status_code == 200:
            payload = r.json()
            content_b64 = payload.get("content", "")
            raw = base64.b64decode(content_b64).decode("utf-8")
            data = json.loads(raw)
            _CACHE = data
            _CACHE_SHA = payload.get("sha")
            _CACHE_ETAG = r.headers.get("ETag")
            _ensure_user_password_hashes(_CACHE)
            return _CACHE

        if r.status_code == 404:
            data = seed_data()
            _ensure_user_password_hashes(data)
            save_data(data, "Seed initial Sales Grid data")
            _CACHE = data
            return _CACHE

        raise RuntimeError(f"GitHub load failed: {r.status_code} {r.text}")

def save_data(data: dict, commit_message: str):
    """Save JSON to GitHub (PUT contents API) and refresh cache SHA."""
    global _CACHE, _CACHE_SHA, _CACHE_ETAG
    with _lock:
        cfg = current_app.config if current_app else None
        import os
        token = (cfg.get("GITHUB_TOKEN") if cfg else os.environ.get("GITHUB_TOKEN", "")) or ""
        repo = (cfg.get("GITHUB_REPO") if cfg else os.environ.get("GITHUB_REPO", "")) or ""
        branch = (cfg.get("GITHUB_BRANCH") if cfg else os.environ.get("GITHUB_BRANCH", "main")) or "main"
        gh_path = (cfg.get("GITHUB_PATH") if cfg else os.environ.get("GITHUB_PATH", "data/sales-grid.json")) or "data/sales-grid.json"

        data.setdefault("meta", {})
        data["meta"]["updated_at"] = _utcnow_iso()

        if not repo:
            _CACHE = data
            return

        url = _contents_url(repo, gh_path)

        # Ensure we have a SHA (refetch if needed). This also helps with multiple instances.
        sha = _CACHE_SHA
        if not sha:
            r = requests.get(url, headers=_headers(token), params={"ref": branch}, timeout=20)
            if r.status_code == 200:
                sha = r.json().get("sha")
            elif r.status_code == 404:
                sha = None
            else:
                raise RuntimeError(f"GitHub preflight failed: {r.status_code} {r.text}")

        raw = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True)
        content_b64 = base64.b64encode(raw.encode("utf-8")).decode("utf-8")

        body = {
            "message": commit_message,
            "content": content_b64,
            "branch": branch,
        }
        if sha:
            body["sha"] = sha

        r2 = requests.put(url, headers=_headers(token), json=body, timeout=25)
        if r2.status_code not in (200, 201):
            raise RuntimeError(f"GitHub save failed: {r2.status_code} {r2.text}")

        payload = r2.json()
        _CACHE_SHA = payload.get("content", {}).get("sha") or payload.get("sha")
        _CACHE_ETAG = r2.headers.get("ETag")
        _CACHE = data

def _ensure_user_password_hashes(data: dict):
    """Backfill manager user password_hash if empty, using default 'manager123'."""
    try:
        from werkzeug.security import generate_password_hash
    except Exception:
        return

    changed = False
    for u in data.get("users", []):
        if u.get("role") == "MANAGER" and not u.get("password_hash"):
            u["password_hash"] = generate_password_hash("manager123")
            changed = True
    if changed:
        # don't force immediate commit here; caller can commit.
        pass

def get_cache():
    return load_data()

def set_cache(data: dict):
    global _CACHE
    with _lock:
        _CACHE = data

def store_lock():
    return _lock
