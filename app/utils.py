from datetime import datetime
from functools import wraps
from flask import session, redirect, url_for, flash, request, g
from app.models import User, AnonymousUser


def get_current_user():
    """Retrieve the current logged-in user or AnonymousUser."""
    if "user_id" not in session:
        return AnonymousUser()

    if not hasattr(g, "_current_user"):
        user = User.query.get(session["user_id"])
        if user and user.is_active:
            g._current_user = user
        else:
            session.pop("user_id", None)
            g._current_user = AnonymousUser()
    return g._current_user


def login_required(f):
    """Ensure user is logged in."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        current_user = get_current_user()
        if not current_user.is_authenticated:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for("auth.login", next=request.url))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """Ensure user is logged in and has the 'admin' role."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        current_user = get_current_user()
        if not current_user.is_authenticated:
            flash("Please log in with an administrator account.", "warning")
            return redirect(url_for("auth.login", next=request.url))
        if not current_user.is_admin:
            flash("Access denied. Administrator privileges are required for this action.", "error")
            return redirect(url_for("dashboard.index"))
        return f(*args, **kwargs)
    return decorated_function


def student_required(f):
    """Ensure user is logged in (student organiser or admin)."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        current_user = get_current_user()
        if not current_user.is_authenticated:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("auth.login", next=request.url))
        return f(*args, **kwargs)
    return decorated_function


def parse_datetime_local(value, field_label):
    """Parse an HTML <input type="datetime-local"> value ('YYYY-MM-DDTHH:MM').
    Raises ValueError with a friendly message on bad input."""
    if not value:
        raise ValueError(f"{field_label} is required.")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M")
    except ValueError:
        raise ValueError(f"{field_label} is not a valid date/time.")


def parse_int(value, field_label, allow_none=False, min_value=None):
    if value is None or value == "":
        if allow_none:
            return None
        raise ValueError(f"{field_label} is required.")
    try:
        n = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_label} must be a whole number.")
    if min_value is not None and n < min_value:
        raise ValueError(f"{field_label} cannot be less than {min_value}.")
    return n

