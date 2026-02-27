from flask import Blueprint, render_template, request, redirect, url_for, flash, session

from ..services.auth import authenticate

bp = Blueprint("auth", __name__)

@bp.get("/login")
def login():
    if session.get("user"):
        return redirect(url_for("main.home"))
    return render_template("login.html")

@bp.post("/login")
def login_post():
    email = request.form.get("email", "")
    password = request.form.get("password", "")
    user = authenticate(email, password)
    if not user:
        flash("Email ou senha inválidos.", "danger")
        return redirect(url_for("auth.login"))
    session["user"] = user
    flash("Login realizado.", "success")
    nxt = request.args.get("next") or url_for("main.home")
    return redirect(nxt)

@bp.get("/logout")
def logout():
    session.pop("user", None)
    flash("Saiu com sucesso.", "info")
    return redirect(url_for("auth.login"))
