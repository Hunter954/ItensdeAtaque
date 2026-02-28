from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from werkzeug.security import generate_password_hash
from ..services.github_store import load_data, save_data
from ..services.auth import login_required, role_required

bp = Blueprint("admin", __name__, url_prefix="/admin")

@bp.get("/settings")
@login_required
@role_required("ADMIN")
def settings():
    data = load_data()
    return render_template("admin/settings.html", company=data.get("company", {}))

@bp.post("/settings")
@login_required
@role_required("ADMIN")
def settings_post():
    data = load_data()
    company = data.setdefault("company", {})
    company["name"] = request.form.get("name", "").strip() or company.get("name", "")
    company["logo_url"] = request.form.get("logo_url", "").strip()
    company["watermark_url"] = request.form.get("watermark_url", "").strip()
    save_data(data, "Update company settings")
    flash("Configurações salvas.", "success")
    return redirect(url_for("admin.settings"))

@bp.get("/teams")
@login_required
@role_required("ADMIN")
def teams():
    data = load_data()
    return render_template("admin/teams.html", teams=data.get("teams", []))

@bp.post("/teams")
@login_required
@role_required("ADMIN")
def teams_post():
    data = load_data()
    action = request.form.get("action")
    teams = data.setdefault("teams", [])

    if action == "create":
        new_id = (request.form.get("id") or "").strip() or f"t{len(teams)+1}"
        if any(t["id"] == new_id for t in teams):
            flash("ID já existe.", "danger")
            return redirect(url_for("admin.teams"))
        teams.append({
            "id": new_id,
            "name": request.form.get("name", "").strip(),
            "manager_name": request.form.get("manager_name", "").strip(),
            "manager_photo_url": request.form.get("manager_photo_url", "").strip(),
        })
        save_data(data, f"Create team {new_id}")
        flash("Equipe criada.", "success")

    elif action == "delete":
        tid = request.form.get("id")
        data["teams"] = [t for t in teams if t.get("id") != tid]
        # also remove sellers and sales for this team
        data["sellers"] = [s for s in data.get("sellers", []) if s.get("team_id") != tid]
        for pid, per in data.get("sales", {}).items():
            if tid in per:
                per.pop(tid, None)
        save_data(data, f"Delete team {tid}")
        flash("Equipe removida.", "info")

    elif action == "update":
        tid = request.form.get("id")
        t = next((x for x in teams if x.get("id") == tid), None)
        if not t:
            flash("Equipe não encontrada.", "danger")
            return redirect(url_for("admin.teams"))
        t["name"] = request.form.get("name", "").strip()
        t["manager_name"] = request.form.get("manager_name", "").strip()
        t["manager_photo_url"] = request.form.get("manager_photo_url", "").strip()
        save_data(data, f"Update team {tid}")
        flash("Equipe atualizada.", "success")

    return redirect(url_for("admin.teams"))

@bp.get("/sellers")
@login_required
@role_required("ADMIN")
def sellers():
    data = load_data()
    teams = {t["id"]: t for t in data.get("teams", [])}
    return render_template("admin/sellers.html", sellers=data.get("sellers", []), teams=teams)

@bp.post("/sellers")
@login_required
@role_required("ADMIN")
def sellers_post():
    data = load_data()
    action = request.form.get("action")
    sellers = data.setdefault("sellers", [])

    if action == "create":
        new_id = (request.form.get("id") or "").strip() or f"s{len(sellers)+1}"
        if any(s["id"] == new_id for s in sellers):
            flash("ID já existe.", "danger")
            return redirect(url_for("admin.sellers"))
        team_id = request.form.get("team_id")
        sellers.append({
            "id": new_id,
            "name": request.form.get("name", "").strip(),
            "team_id": team_id,
            "photo_url": request.form.get("photo_url", "").strip(),
        })
        _ensure_sales_cells(data, team_id, new_id)
        save_data(data, f"Create seller {new_id}")
        flash("Vendedor criado.", "success")

    elif action == "update":
        sid = request.form.get("id")
        s = next((x for x in sellers if x.get("id") == sid), None)
        if not s:
            flash("Vendedor não encontrado.", "danger")
            return redirect(url_for("admin.sellers"))
        old_team = s.get("team_id")
        s["name"] = request.form.get("name", "").strip()
        s["team_id"] = request.form.get("team_id")
        s["photo_url"] = request.form.get("photo_url", "").strip()
        if old_team != s["team_id"]:
            _move_seller_sales(data, sid, old_team, s["team_id"])
        save_data(data, f"Update seller {sid}")
        flash("Vendedor atualizado.", "success")

    elif action == "delete":
        sid = request.form.get("id")
        data["sellers"] = [s for s in sellers if s.get("id") != sid]
        for pid, per in data.get("sales", {}).items():
            for tid, team_sales in per.items():
                team_sales.pop(sid, None)
        save_data(data, f"Delete seller {sid}")
        flash("Vendedor removido.", "info")

    return redirect(url_for("admin.sellers"))

@bp.get("/items")
@login_required
@role_required("ADMIN")
def items():
    data = load_data()
    return render_template("admin/items.html", items=data.get("items", []))

@bp.post("/items")
@login_required
@role_required("ADMIN")
def items_post():
    data = load_data()
    action = request.form.get("action")
    items = data.setdefault("items", [])

    if action == "create":
        new_id = (request.form.get("id") or "").strip() or f"i{len(items)+1}"
        if any(i["id"] == new_id for i in items):
            flash("ID já existe.", "danger")
            return redirect(url_for("admin.items"))
        items.append({
            "id": new_id,
            "name": request.form.get("name", "").strip(),
            "photo_url": request.form.get("photo_url", "").strip(),
            "video_url": request.form.get("video_url", "").strip(),
            "target": int(request.form.get("target") or 18),
        })
        _ensure_item_cells(data, new_id)
        save_data(data, f"Create item {new_id}")
        flash("Item criado.", "success")

    elif action == "update":
        iid = request.form.get("id")
        it = next((x for x in items if x.get("id") == iid), None)
        if not it:
            flash("Item não encontrado.", "danger")
            return redirect(url_for("admin.items"))
        it["name"] = request.form.get("name", "").strip()
        it["photo_url"] = request.form.get("photo_url", "").strip()
        it["video_url"] = request.form.get("video_url", "").strip()
        it["target"] = int(request.form.get("target") or it.get("target") or 18)
        save_data(data, f"Update item {iid}")
        flash("Item atualizado.", "success")

    elif action == "delete":
        iid = request.form.get("id")
        data["items"] = [i for i in items if i.get("id") != iid]
        for pid, per in data.get("sales", {}).items():
            for tid, team_sales in per.items():
                for sid, row in team_sales.items():
                    row.pop(iid, None)
        save_data(data, f"Delete item {iid}")
        flash("Item removido.", "info")

    return redirect(url_for("admin.items"))

@bp.get("/audit")
@login_required
@role_required("ADMIN")
def audit():
    data = load_data()
    audit = list(reversed(data.get("audit", [])))[:100]
    return render_template("admin/audit.html", audit=audit)

def _ensure_sales_cells(data, team_id: str, seller_id: str):
    # For each period, ensure this seller exists with all items (only if team_id exists)
    items = data.get("items", [])
    sales = data.setdefault("sales", {})
    for pid, per in sales.items():
        per.setdefault(team_id, {})
        per[team_id].setdefault(seller_id, {it["id"]: 0 for it in items})
        # also ensure any missing item keys
        for it in items:
            per[team_id][seller_id].setdefault(it["id"], 0)

def _ensure_item_cells(data, item_id: str):
    sales = data.setdefault("sales", {})
    for pid, per in sales.items():
        for tid, team_sales in per.items():
            for sid, row in team_sales.items():
                row.setdefault(item_id, 0)

def _move_seller_sales(data, seller_id: str, old_team: str, new_team: str):
    sales = data.setdefault("sales", {})
    for pid, per in sales.items():
        old = per.get(old_team, {})
        row = old.pop(seller_id, None)
        if row is None:
            continue
        per.setdefault(new_team, {})
        per[new_team][seller_id] = row
