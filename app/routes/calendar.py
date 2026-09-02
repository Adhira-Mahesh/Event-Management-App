from datetime import datetime, timedelta
from flask import Blueprint, render_template, request
from app.models import Allocation, Resource, Event, RESOURCE_TYPES
from app.utils import login_required

calendar_bp = Blueprint("calendar", __name__, url_prefix="/calendar")


@calendar_bp.route("")
@calendar_bp.route("/")
@login_required
def schedule():

    start_str = request.args.get("start_date")
    type_filter = request.args.get("type", "")

    today = datetime.utcnow().date()

    if start_str:
        try:
            start_date = datetime.strptime(start_str, "%Y-%m-%d").date()
        except ValueError:
            start_date = today
    else:
        start_date = today

    end_date = start_date + timedelta(days=6)
    window_start = datetime.combine(start_date, datetime.min.time())
    window_end = datetime.combine(end_date, datetime.max.time())

    # Build the 7 days list with date object, formatted string, and day name
    days = []
    for i in range(7):
        d = start_date + timedelta(days=i)
        days.append({
            "date": d,
            "date_str": d.strftime("%Y-%m-%d"),
            "display": d.strftime("%a, %d %b"),
            "day_name": d.strftime("%A"),
            "day_short": d.strftime("%a"),
            "day_num": d.strftime("%d"),
            "month_short": d.strftime("%b"),
            "is_today": d == today,
            "start_dt": datetime.combine(d, datetime.min.time()),
            "end_dt": datetime.combine(d, datetime.max.time()),
        })

    # Resources query
    res_query = Resource.query.filter_by(is_active=True)
    if type_filter and type_filter in RESOURCE_TYPES:
        res_query = res_query.filter(Resource.type == type_filter)
    resources = res_query.order_by(Resource.type.asc(), Resource.name.asc()).all()

    # Active allocations in the 7-day window
    allocations = (
        Allocation.query.filter(
            Allocation.status == "Allocated",
            Allocation.start_time <= window_end,
            Allocation.end_time >= window_start,
        )
        .order_by(Allocation.start_time.asc())
        .all()
    )

    # Filter allocations if type_filter is applied
    if type_filter and type_filter in RESOURCE_TYPES:
        allocations = [a for a in allocations if a.resource and a.resource.type == type_filter]

    # Map allocations per day
    daily_schedule = {day["date_str"]: [] for day in days}
    for alloc in allocations:
        for day in days:
            # Check if this allocation overlaps this specific day
            if alloc.start_time <= day["end_dt"] and alloc.end_time >= day["start_dt"]:
                daily_schedule[day["date_str"]].append(alloc)

    # Events happening in this week
    events_in_week = (
        Event.query.filter(
            Event.status.in_(["Approved", "Pending", "Draft"]),
            Event.start_time <= window_end,
            Event.end_time >= window_start,
        )
        .order_by(Event.start_time.asc())
        .all()
    )

    prev_start = (start_date - timedelta(days=7)).strftime("%Y-%m-%d")
    next_start = (start_date + timedelta(days=7)).strftime("%Y-%m-%d")
    today_start = today.strftime("%Y-%m-%d")

    return render_template(
        "calendar/index.html",
        days=days,
        start_date=start_date,
        end_date=end_date,
        prev_start=prev_start,
        next_start=next_start,
        today_start=today_start,
        resources=resources,
        resource_types=RESOURCE_TYPES,
        type_filter=type_filter,
        daily_schedule=daily_schedule,
        events_in_week=events_in_week,
        total_allocations=len(allocations),
    )
