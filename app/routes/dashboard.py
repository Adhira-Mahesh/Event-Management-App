from flask import Blueprint, render_template, redirect, url_for
from datetime import datetime, timedelta
from app.models import Event, Resource, ResourceRequest, Allocation, User
from app.utils import login_required, get_current_user

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
@login_required
def index():
    current_user = get_current_user()
    now = datetime.utcnow()

    # Admin Statistics
    admin_stats = {
        "total_events": Event.query.count(),
        "upcoming_events": Event.query.filter(
            Event.start_time >= now, Event.status.in_(["Approved", "Pending"])
        ).count(),
        "pending_requests": ResourceRequest.query.filter_by(status="Pending").count(),
        "active_resources": Resource.query.filter_by(is_active=True).count(),
        "total_resources": Resource.query.count(),
        "active_allocations": Allocation.query.filter_by(status="Allocated").count(),
        "total_users": User.query.count(),
    }

    # Student Organiser Statistics
    student_stats = {
        "my_events": Event.query.filter_by(user_id=current_user.id).count(),
        "my_pending_requests": ResourceRequest.query.filter_by(user_id=current_user.id, status="Pending").count(),
        "my_approved_requests": ResourceRequest.query.filter_by(user_id=current_user.id, status="Approved").count(),
        "upcoming_events": Event.query.filter(
            Event.start_time >= now, Event.status.in_(["Approved", "Pending"])
        ).count(),
    }

    upcoming_events = (
        Event.query.filter(Event.status.in_(["Approved", "Pending"]), Event.start_time >= now)
        .order_by(Event.start_time.asc())
        .limit(6)
        .all()
    )

    pending_requests = (
        ResourceRequest.query.filter_by(status="Pending")
        .order_by(ResourceRequest.created_at.desc())
        .limit(6)
        .all()
    )

    my_requests = []
    my_events = []
    if current_user.is_student_organiser:
        my_requests = (
            ResourceRequest.query.filter_by(user_id=current_user.id)
            .order_by(ResourceRequest.created_at.desc())
            .limit(5)
            .all()
        )
        my_events = (
            Event.query.filter_by(user_id=current_user.id)
            .order_by(Event.start_time.asc())
            .limit(5)
            .all()
        )

    # 7-day upcoming allocation count for the quick calendar teaser
    week_end = now + timedelta(days=7)
    week_allocations_count = Allocation.query.filter(
        Allocation.status == "Allocated",
        Allocation.start_time <= week_end,
        Allocation.end_time >= now,
    ).count()

    return render_template(
        "dashboard.html",
        admin_stats=admin_stats,
        student_stats=student_stats,
        upcoming_events=upcoming_events,
        pending_requests=pending_requests,
        my_requests=my_requests,
        my_events=my_events,
        week_allocations_count=week_allocations_count,
    )

