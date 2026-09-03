from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app.extensions import db
from app.models import User
from app.utils import get_current_user

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    current_user = get_current_user()
    if request.method == "GET" and current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    next_url = request.args.get("next") or request.form.get("next")

    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""

        if not email or not password:
            flash("Please provide both email and password.", "error")
            return render_template("auth/login.html", email=email, next=next_url)

        user = User.query.filter_by(email=email).first()
        if not user or not user.check_password(password):
            flash("Invalid email or password. Please try again.", "error")
            return render_template("auth/login.html", email=email, next=next_url)

        if not user.is_active:
            flash("Your account has been deactivated. Please contact an administrator.", "error")
            return render_template("auth/login.html", email=email, next=next_url)

        session["user_id"] = user.id
        flash(f"Welcome back, {user.name}!", "success")

        if next_url and next_url.startswith("/"):
            return redirect(next_url)
        return redirect(url_for("dashboard.index"))

    return render_template("auth/login.html", next=next_url)


@auth_bp.route("/signup", methods=["GET", "POST"])
def signup():
    current_user = get_current_user()
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        department = (request.form.get("department") or "").strip()
        password = request.form.get("password") or ""
        confirm_password = request.form.get("confirm_password") or ""

        errors = []
        if not name:
            errors.append("Full Name or Club/Dept Name is required.")
        if not email or "@" not in email:
            errors.append("A valid college email address is required.")
        if not department:
            errors.append("Department or Student Organization name is required.")
        if len(password) < 6:
            errors.append("Password must be at least 6 characters long.")
        if password != confirm_password:
            errors.append("Passwords do not match.")

        existing = User.query.filter_by(email=email).first()
        if existing:
            errors.append("An account with this email already exists. Please log in instead.")

        if errors:
            for err in errors:
                flash(err, "error")
            return render_template(
                "auth/signup.html",
                form_data={"name": name, "email": email, "department": department}
            )

        # Self-registration is strictly for Student Organisers
        user = User(
            name=name,
            email=email,
            department=department,
            role="student_organiser",
            is_active=True
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        session["user_id"] = user.id
        flash("Your Student Organiser account has been created successfully! Welcome to CERAS. ", "success")
        return redirect(url_for("dashboard.index"))

    return render_template("auth/signup.html", form_data={})


@auth_bp.route("/logout", methods=["GET", "POST"])
def logout():
    session.pop("user_id", None)
    flash("You have been logged out successfully.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/demo-login/<role>", methods=["POST", "GET"])
def demo_login(role):
    """Convenience shortcut to test the app as Admin or Student Organiser."""
    target_email = "admin@college.edu" if role == "admin" else "alex.cs@college.edu"
    user = User.query.filter_by(email=target_email).first()
    if user:
        session["user_id"] = user.id
        flash(f"Logged in as demo {user.role.replace('_', ' ').title()}: {user.name}", "success")
    else:
        flash("Demo user not found. Please run database seed first.", "warning")
    return redirect(url_for("dashboard.index"))
