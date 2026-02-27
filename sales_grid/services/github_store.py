import base64
import json
import threading
import time
from datetime import datetime, timezone

import requests
from flask import current_app

_lock = threading.Lock()
_CACHE = None
_CACHE_SHA = None
_CACHE_ETAG = None


# =========================
# Helpers
# =========================
def _utcnow_iso():
    return datetime.now(timezone.utc).isoformat()


def _headers(token: str):
    """
    GitHub API headers.
    - Fine-grained tokens work with: Authorization: Bearer <token>
    - Classic tokens also usually work with Bearer; but we keep it standard.
    """
    h = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "sales-grid/1.0",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def _contents_url(repo: str, path: str):
    return f"https://api.github.com/repos/{repo}/contents/{path}"


def _get_cfg():
    cfg = current_app.config if current_app else None
    import os

    token = (cfg.get("GITHUB_TOKEN") if cfg else os.environ.get("GITHUB_TOKEN", "")) or ""
    repo = (cfg.get("GITHUB_REPO") if cfg else os.environ.get("GITHUB_REPO", "")) or ""
    branch = (cfg.get("GITHUB_BRANCH") if cfg else os.environ.get("GITHUB_BRANCH", "main")) or "main"
    gh_path = (cfg.get("GITHUB_PATH") if cfg else os.environ.get("GITHUB_PATH", "data/sales-grid.json")) or "data/sales-grid.json"
    return token, repo, branch, gh_path


def _request(method: str, url: str, *, headers=None, params=None, json_body=None, timeout=12, retries=2):
    """
    Small retry wrapper for transient issues.
    Retries on 502/503/504 and on request exceptions.
    """
    last_exc = None
    for attempt in range(retries + 1):
        try:
            r = requests.request(
                method,
                url,
                headers=headers,
                params=params,
                json=json_body,
                timeout=timeout,
            )

            if r.status_code in (502, 503, 504):
                # transient server issues
                if attempt < retries:
                    time.sleep(0.6 * (attempt + 1))
                    continue
            return r
        except requests.RequestException as e:
            last_exc = e
            if attempt < retries:
                time.sleep(0.6 * (attempt + 1))
                continue
            raise RuntimeError(f"GitHub request failed: {e}") from e

    if last_exc:
        raise RuntimeError(f"GitHub request failed: {last_exc}")
    raise RuntimeError("GitHub request failed (unknown)")


def _decode_content_b64(content_b64: str) -> str:
    # GitHub can include newlines in base64 content
    cleaned = (content_b64 or "").replace("\n", "")
    return base64.b64decode(cleaned).decode("utf-8")


# =========================
# Seed
# =========================
def seed_data():
    # 5 teams/managers, some sellers & items, one current period, managers users
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

    now = datetime.now(timezone.utc)
    period_id = now.strftime("p%Y%m")
    periods = [{"id": period_id, "name": now.strftime("%B %Y"), "is_current": True, "created_at": _utcnow_iso()}]

    company = {
        "name": "Minha Empresa",
        "logo_url": "https://via.placeholder.com/256?text=LOGO",
        "watermark_url": "https://via.placeholder.com/256?text=WATERMARK",
    }

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


def _ensure_user_password_hashes(data: dict):
    """Backfill manager user password_hash if empty, using default 'manager123'."""
    try:
        from werkzeug.security import generate_password_hash
    except Exception:
        return

    for u in data.get("users", []):
        if u.get("role") == "MANAGER" and not u.get("password_hash"):
            u["password_hash"] = generate_password_hash("manager123")


# =========================
# Public API
# =========================
def load_data(force: bool = False):
    """Load JSON from GitHub into memory cache. If missing, create seed and commit it."""
    global _CACHE, _CACHE_SHA, _CACHE_ETAG

    with _lock:
        if _CACHE is not None and not force:
            return _CACHE

        token, repo, branch, gh_path = _get_cfg()

        # Dev mode: no repo configured
        if not repo:
            if _CACHE is None:
                _CACHE = seed_data()
                _ensure_user_password_hashes(_CACHE)
            return _CACHE

        url = _contents_url(repo, gh_path)
        r = _request("GET", url, headers=_headers(token), params={"ref": branch}, timeout=5, retries=1)

        if r.status_code == 200:
            payload = r.json()
            raw = _decode_content_b64(payload.get("content", ""))
            data = json.loads(raw)
            _ensure_user_password_hashes(data)

            _CACHE = data
            _CACHE_SHA = payload.get("sha")
            _CACHE_ETAG = r.headers.get("ETag")
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
        token, repo, branch, gh_path = _get_cfg()

        data.setdefault("meta", {})
        data["meta"]["updated_at"] = _utcnow_iso()

        if not repo:
            _CACHE = data
            return

        url = _contents_url(repo, gh_path)

        def _fetch_sha():
            r0 = _request("GET", url, headers=_headers(token), params={"ref": branch}, timeout=12, retries=2)
            if r0.status_code == 200:
                return r0.json().get("sha")
            if r0.status_code == 404:
                return None
            raise RuntimeError(f"GitHub preflight failed: {r0.status_code} {r0.text}")

        sha = _CACHE_SHA if _CACHE_SHA else _fetch_sha()

        raw = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True)
        content_b64 = base64.b64encode(raw.encode("utf-8")).decode("utf-8")

        body = {"message": commit_message, "content": content_b64, "branch": branch}
        if sha:
            body["sha"] = sha

        r2 = _request("PUT", url, headers=_headers(token), json_body=body, timeout=15, retries=1)

        # If another instance updated the file, GitHub can return 409.
        # Refetch sha and retry once.
        if r2.status_code == 409:
            sha = _fetch_sha()
            body.pop("sha", None)
            if sha:
                body["sha"] = sha
            r2 = _request("PUT", url, headers=_headers(token), json_body=body, timeout=15, retries=1)

        if r2.status_code not in (200, 201):
            raise RuntimeError(f"GitHub save failed: {r2.status_code} {r2.text}")

        payload = r2.json()
        _CACHE_SHA = payload.get("content", {}).get("sha") or payload.get("sha")
        _CACHE_ETAG = r2.headers.get("ETag")
        _CACHE = data


def get_cache():
    return load_data()


def set_cache(data: dict):
    global _CACHE
    with _lock:
        _CACHE = data


def store_lock():
    return _lock
