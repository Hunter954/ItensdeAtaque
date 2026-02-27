import csv
import io
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify, Response, abort, session
from ..services.github_store import load_data, save_data
from ..services.auth import login_required, can_access_team, role_required

bp = Blueprint("api", __name__, url_prefix="/api")

def _utcnow_iso():
    return datetime.now(timezone.utc).isoformat()

@bp.get("/grid")
@login_required
def grid_get():
    team_id = request.args.get("team_id")
    period_id = request.args.get("period_id")
    if not team_id or not period_id:
        return jsonify({"error": "team_id and period_id required"}), 400
    if not can_access_team(team_id):
        abort(403)

    data = load_data()
    sellers = [s for s in data.get("sellers", []) if s.get("team_id") == team_id]
    items = data.get("items", [])
    sales = data.get("sales", {}).get(period_id, {}).get(team_id, {})
    return jsonify({
        "team_id": team_id,
        "period_id": period_id,
        "sellers": sellers,
        "items": items,
        "sales": sales,
        "meta": data.get("meta", {}),
    })

@bp.patch("/cell")
@login_required
def cell_patch():
    payload = request.get_json(silent=True) or {}
    team_id = payload.get("team_id")
    period_id = payload.get("period_id")
    seller_id = payload.get("seller_id")
    item_id = payload.get("item_id")
    value = payload.get("value")

    if not all([team_id, period_id, seller_id, item_id]):
        return jsonify({"error": "Missing ids"}), 400
    if not can_access_team(team_id):
        abort(403)

    try:
        value_int = int(value)
    except Exception:
        return jsonify({"error": "value must be int"}), 400
    if value_int < 0:
        value_int = 0

    data = load_data()
    sales = data.setdefault("sales", {})
    sales.setdefault(period_id, {})
    sales[period_id].setdefault(team_id, {})
    sales[period_id][team_id].setdefault(seller_id, {})
    sales[period_id][team_id][seller_id].setdefault(item_id, 0)

    old = sales[period_id][team_id][seller_id].get(item_id, 0)
    sales[period_id][team_id][seller_id][item_id] = value_int

    entry = {
        "at": _utcnow_iso(),
        "by": (session.get("user") or {}).get("email"),
        "type": "CELL_UPDATE",
        "team_id": team_id,
        "period_id": period_id,
        "seller_id": seller_id,
        "item_id": item_id,
        "from": old,
        "to": value_int,
    }
    audit = data.setdefault("audit", [])
    audit.append(entry)
    if len(audit) > 500:
        data["audit"] = audit[-500:]

    try:
        save_data(data, f"Update cell {team_id}/{period_id} {seller_id}:{item_id} -> {value_int}")
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({"ok": True, "value": value_int, "updated_at": data.get("meta", {}).get("updated_at")})

@bp.get("/export.csv")
@login_required
def export_csv():
    team_id = request.args.get("team_id")
    period_id = request.args.get("period_id")
    if not team_id or not period_id:
        return jsonify({"error": "team_id and period_id required"}), 400
    if not can_access_team(team_id):
        abort(403)

    data = load_data()
    team = next((t for t in data.get("teams", []) if t.get("id") == team_id), None)
    period = next((p for p in data.get("periods", []) if p.get("id") == period_id), None)
    sellers = [s for s in data.get("sellers", []) if s.get("team_id") == team_id]
    items = data.get("items", [])
    sales = data.get("sales", {}).get(period_id, {}).get(team_id, {})

    output = io.StringIO()
    writer = csv.writer(output)
    header = ["seller_id", "seller_name"] + [it["name"] for it in items] + ["total"]
    writer.writerow(header)

    for s in sellers:
        row = sales.get(s["id"], {})
        vals = [int(row.get(it["id"], 0) or 0) for it in items]
        writer.writerow([s["id"], s["name"], *vals, sum(vals)])

    content = output.getvalue()
    filename = f"sales-grid_{team_id}_{period_id}.csv"
    resp = Response(content, mimetype="text/csv; charset=utf-8")
    resp.headers["Content-Disposition"] = f"attachment; filename={filename}"
    return resp

# --- Optional JSON admin APIs (useful for integrations) ---
@bp.get("/admin/teams")
@login_required
@role_required("ADMIN")
def admin_list_teams():
    data = load_data()
    return jsonify(data.get("teams", []))

@bp.get("/admin/sellers")
@login_required
@role_required("ADMIN")
def admin_list_sellers():
    data = load_data()
    return jsonify(data.get("sellers", []))

@bp.get("/admin/items")
@login_required
@role_required("ADMIN")
def admin_list_items():
    data = load_data()
    return jsonify(data.get("items", []))
