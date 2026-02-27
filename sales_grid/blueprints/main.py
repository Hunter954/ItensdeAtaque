from flask import Blueprint, render_template, request, redirect, url_for
from ..services.github_store import load_data
from ..services.auth import login_required, current_user

bp = Blueprint("main", __name__)

@bp.get("/")
def index():
    return redirect(url_for("main.home"))

@bp.get("/home")
@login_required
def home():
    data = load_data()
    user = current_user()

    periods = data.get("periods", [])
    selected_period = request.args.get("period") or _current_period_id(periods)

    teams = data.get("teams", [])
    if user.get("role") == "MANAGER":
        teams = [t for t in teams if t.get("id") == user.get("team_id")]

    return render_template(
        "home.html",
        company=data.get("company", {}),
        teams=teams,
        periods=periods,
        selected_period=selected_period,
        user=user,
    )

def _current_period_id(periods):
    for p in periods:
        if p.get("is_current"):
            return p.get("id")
    return periods[0].get("id") if periods else ""
