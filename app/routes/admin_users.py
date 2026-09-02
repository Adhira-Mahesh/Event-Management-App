from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.extensions import db
from app.models import User, ROLES
from app.utils import admin_required, get_current_user

admin_users_bp = Blueprint("admin_users", __name__, url_prefix="/admin/users")


@admin_users_bp.route("")
@admin_users_bp.route("/")
@admin_required
def list_users():

    role_filter = request.args.get("role", "")
    search = (request.args.get("q") or "").strip()

    query = User.query

    if role_filter in ROLES:
        query = query.filter(User.role == role_filter)

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (User.name.ilike(search_term))
            | (User.email.ilike(search_term))
            | (User.department.ilike(search_term))
        )

    users = query.order_by(User.created_at.desc()).all()

    stats = {
        "total_users": User.query.count(),
        "admins": User.query.filter_by(role="admin").count(),
        "student_organisers": User.query.filter_by(role="student_organiser").count(),
        "active_users": User.query.filter_by(is_active=True).count(),
        "inactive_users": User.query.filter_by(is_active=False).count(),
    }

    return render_template(
        "admin/users.html",
        users=users,
        stats=stats,
        roles=ROLES,
        role_filter=role_filter,
        search=search,
    )


@admin_users_bp.route("/<int:user_id>/role", methods=["POST"])
@admin_required
def update_role(user_id):
    current_user = get_current_user()
    user = User.query.get_or_404(user_id)
    new_role = request.form.get("role")

    if new_role not in ROLES:
        flash("Invalid role specified.", "error")
        return redirect(url_for("admin_users.list_users"))

    # Protection: Do not let the last admin demote themselves
    if user.id == current_user.id and new_role != "admin":
        other_admins = User.query.filter(User.role == "admin", User.id != user.id, User.is_active == True).count()
        if other_admins == 0:
            flash("You cannot demote yourself as you are the only active Administrator in the system.", "error")
            return redirect(url_for("admin_users.list_users"))

    user.role = new_role
    db.session.commit()
    flash(f"Role for {user.name} updated to {new_role.replace('_', ' ').title()}.", "success")
    return redirect(url_for("admin_users.list_users"))


@admin_users_bp.route("/<int:user_id>/toggle-status", methods=["POST"])
@admin_required
def toggle_status(user_id):
    current_user = get_current_user()
    user = User.query.get_or_404(user_id)

    if user.id == current_user.id:
        flash("You cannot deactivate your own account while logged in.", "error")
        return redirect(url_for("admin_users.list_users"))

    user.is_active = not user.is_active
    db.session.commit()
    state = "activated" if user.is_active else "deactivated"
    flash(f"Account for {user.name} has been {state}.", "success")
    return redirect(url_for("admin_users.list_users"))


@admin_users_bp.route("/create", methods=["POST"])
@admin_required
def create_user():
    name = (request.form.get("name") or "").strip()
    email = (request.form.get("email") or "").strip().lower()
    department = (request.form.get("department") or "").strip()
    role = request.form.get("role") or "student_organiser"
    password = request.form.get("password") or ""

    if not name or not email or not password:
        flash("Name, email, and password are required.", "error")
        return redirect(url_for("admin_users.list_users"))

    if role not in ROLES:
        flash("Invalid role selection.", "error")
        return redirect(url_for("admin_users.list_users"))

    existing = User.query.filter_by(email=email).first()
    if existing:
        flash(f"User with email '{email}' already exists.", "error")
        return redirect(url_for("admin_users.list_users"))

    user = User(
        name=name,
        email=email,
        department=department,
        role=role,
        is_active=True
    )
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    flash(f"User {user.name} successfully created as {role.replace('_', ' ').title()}.", "success")
    return redirect(url_for("admin_users.list_users"))
