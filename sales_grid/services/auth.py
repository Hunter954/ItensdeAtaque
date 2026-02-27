from functools import wraps
from flask import session, redirect, url_for, flash, request, current_app
from werkzeug.security import check_password_hash
from .github_store import load_data

def current_user():
    u = session.get("user")
    return u

def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not session.get("user"):
            return redirect(url_for("auth.login", next=request.path))
        return view(*args, **kwargs)
    return wrapper

def role_required(*roles):
    def deco(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            u = session.get("user")
            if not u:
                return redirect(url_for("auth.login", next=request.path))
            if u.get("role") not in roles:
                flash("Acesso negado.", "danger")
                return redirect(url_for("main.home"))
            return view(*args, **kwargs)
        return wrapper
    return deco

def can_access_team(team_id: str) -> bool:
    u = session.get("user")
    if not u:
        return False
    if u.get("role") == "ADMIN":
        return True
    if u.get("role") == "MANAGER":
        return u.get("team_id") == team_id
    return False

def authenticate(email: str, password: str):
    email = (email or "").strip().lower()
    if not email or not password:
        return None

    # Admin from env
    admin_email = (current_app.config.get("ADMIN_EMAIL") or "").strip().lower()
    admin_pass = current_app.config.get("ADMIN_PASSWORD") or ""
    if email == admin_email and password == admin_pass:
        return {"email": email, "role": "ADMIN", "team_id": None}

    # Managers from JSON
    data = load_data()
    for u in data.get("users", []):
        if (u.get("email") or "").strip().lower() == email and u.get("role") == "MANAGER":
            ph = u.get("password_hash") or ""
            if ph and check_password_hash(ph, password):
                return {"email": email, "role": "MANAGER", "team_id": u.get("team_id")}
    return None
