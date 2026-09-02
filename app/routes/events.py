from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.extensions import db
from app.models import Event, EVENT_STATUSES
from app.utils import parse_datetime_local, parse_int, login_required, get_current_user

events_bp = Blueprint("events", __name__, template_folder="../templates/events")


def _validate_event_fields(form):
    """Shared validation for create + edit. Returns (data_dict, errors_list)."""
    errors = []
    data = {}

    name = (form.get("name") or "").strip()
    organizer = (form.get("organizer") or "").strip()
    if not name:
        errors.append("Event name is required.")
    if not organizer:
        errors.append("Organizer / Department name is required.")
    data["name"] = name
    data["organizer"] = organizer

    try:
        data["expected_attendance"] = parse_int(
            form.get("expected_attendance"), "Expected attendance", min_value=0
        )
    except ValueError as e:
        errors.append(str(e))
        data["expected_attendance"] = None

    try:
        data["start_time"] = parse_datetime_local(form.get("start_time"), "Start date/time")
    except ValueError as e:
        errors.append(str(e))
        data["start_time"] = None

    try:
        data["end_time"] = parse_datetime_local(form.get("end_time"), "End date/time")
    except ValueError as e:
        errors.append(str(e))
        data["end_time"] = None

    if data["start_time"] and data["end_time"] and data["start_time"] >= data["end_time"]:
        errors.append("Event end time must be after the start time.")

    status = form.get("status") or "Draft"
    if status not in EVENT_STATUSES:
        errors.append("Invalid status selected.")
    data["status"] = status

    return data, errors


@events_bp.route("")
@events_bp.route("/")
@login_required
def list_events():

    status_filter = request.args.get("status", "")
    date_filter = request.args.get("date", "")
    mine_only = request.args.get("mine") == "1"
    current_user = get_current_user()

    query = Event.query
    if mine_only and current_user.is_authenticated:
        query = query.filter(Event.user_id == current_user.id)

    if status_filter and status_filter in EVENT_STATUSES:
        query = query.filter(Event.status == status_filter)
    if date_filter:
        try:
            from datetime import datetime as dt

            day = dt.strptime(date_filter, "%Y-%m-%d")
            next_day = day.replace(hour=23, minute=59, second=59)
            query = query.filter(Event.start_time >= day, Event.start_time <= next_day)
        except ValueError:
            flash("Invalid date filter ignored.", "warning")

    events = query.order_by(Event.start_time.asc()).all()
    return render_template(
        "events/list.html",
        events=events,
        statuses=EVENT_STATUSES,
        status_filter=status_filter,
        date_filter=date_filter,
        mine_only=mine_only,
    )


@events_bp.route("/new", methods=["GET", "POST"])
@login_required
def new_event():
    current_user = get_current_user()
    if request.method == "POST":
        data, errors = _validate_event_fields(request.form)
        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("events/form.html", event=data, statuses=EVENT_STATUSES, mode="create")

        event = Event(**data)
        event.user_id = current_user.id
        db.session.add(event)
        db.session.commit()
        flash(f'Event "{event.name}" created successfully.', "success")
        return redirect(url_for("events.list_events"))

    default_data = {
        "organizer": f"{current_user.department or current_user.name}"
    }
    return render_template("events/form.html", event=default_data, statuses=EVENT_STATUSES, mode="create")


@events_bp.route("/<int:event_id>/edit", methods=["GET", "POST"])
@login_required
def edit_event(event_id):
    current_user = get_current_user()
    event = Event.query.get_or_404(event_id)

    # Permission check: Admin or event creator
    if not current_user.is_admin and event.user_id and event.user_id != current_user.id:
        flash("You can only edit events created by your organization.", "error")
        return redirect(url_for("events.list_events"))

    if request.method == "POST":
        data, errors = _validate_event_fields(request.form)
        if errors:
            for e in errors:
                flash(e, "error")
            merged = {**data, "id": event.id}
            return render_template("events/form.html", event=merged, statuses=EVENT_STATUSES, mode="edit")

        for key, value in data.items():
            setattr(event, key, value)
        db.session.commit()
        flash(f'Event "{event.name}" updated successfully.', "success")
        return redirect(url_for("events.list_events"))

    return render_template("events/form.html", event=event, statuses=EVENT_STATUSES, mode="edit")


@events_bp.route("/<int:event_id>/cancel", methods=["POST"])
@login_required
def cancel_event(event_id):
    current_user = get_current_user()
    event = Event.query.get_or_404(event_id)

    if not current_user.is_admin and event.user_id and event.user_id != current_user.id:
        flash("You can only cancel events created by your organization.", "error")
        return redirect(url_for("events.list_events"))

    event.status = "Cancelled"

    # Cancelling an event also releases any resources allocated to it.
    from app.services.booking_service import cancel_resource_request

    for rr in event.resource_requests:
        if rr.status in ("Pending", "Approved"):
            cancel_resource_request(rr)

    db.session.commit()
    flash(f'Event "{event.name}" cancelled and its resources released.', "success")
    return redirect(url_for("events.list_events"))

