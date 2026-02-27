from flask import Blueprint, render_template, request, abort
from ..services.github_store import load_data
from ..services.auth import login_required, can_access_team

bp = Blueprint("team", __name__)

@bp.get("/team/<team_id>")
@login_required
def team_view(team_id):
    if not can_access_team(team_id):
        abort(403)
    data = load_data()
    periods = data.get("periods", [])
    period_id = request.args.get("period") or next((p.get("id") for p in periods if p.get("is_current")), (periods[0].get("id") if periods else ""))

    team = next((t for t in data.get("teams", []) if t.get("id") == team_id), None)
    if not team:
        abort(404)

    sellers = [s for s in data.get("sellers", []) if s.get("team_id") == team_id]
    items = data.get("items", [])

    # sales matrix
    sales = (data.get("sales", {}).get(period_id, {}).get(team_id, {})) if period_id else {}
    return render_template(
        "team.html",
        company=data.get("company", {}),
        team=team,
        period_id=period_id,
        periods=periods,
        sellers=sellers,
        items=items,
        sales=sales,
    )
