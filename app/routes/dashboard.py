from flask import Blueprint, render_template
from datetime import datetime
from app.models import Event, Resource, ResourceRequest, Allocation

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
def index():
    now = datetime.utcnow()

    stats = {
        "total_events": Event.query.count(),
        "upcoming_events": Event.query.filter(
            Event.start_time >= now, Event.status.in_(["Approved", "Pending"])
        ).count(),
        "pending_requests": ResourceRequest.query.filter_by(status="Pending").count(),
        "active_resources": Resource.query.filter_by(is_active=True).count(),
        "total_resources": Resource.query.count(),
        "active_allocations": Allocation.query.filter_by(status="Allocated").count(),
    }

    upcoming_events = (
        Event.query.filter(Event.status.in_(["Approved", "Pending"]), Event.start_time >= now)
        .order_by(Event.start_time.asc())
        .limit(5)
        .all()
    )

    pending_requests = (
        ResourceRequest.query.filter_by(status="Pending").order_by(ResourceRequest.created_at.desc()).limit(5).all()
    )

    return render_template(
        "dashboard.html", stats=stats, upcoming_events=upcoming_events, pending_requests=pending_requests
    )
