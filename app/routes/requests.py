from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.extensions import db
from app.models import (
    Event,
    Resource,
    ResourceRequest,
    ResourceRequestItem,
    Allocation,
    RESOURCE_TYPES,
    REQUEST_STATUSES,
)
from app.services.booking_service import (
    process_resource_request,
    cancel_resource_request,
    cancel_allocation,
    find_suitable_candidates,
)
from app.utils import parse_datetime_local, parse_int

requests_bp = Blueprint("requests", __name__, template_folder="../templates/requests")


# ---------------------------------------------------------------------------
# List + detail
# ---------------------------------------------------------------------------

@requests_bp.route("/")
def list_requests():
    status_filter = request.args.get("status", "")
    query = ResourceRequest.query
    if status_filter and status_filter in REQUEST_STATUSES:
        query = query.filter(ResourceRequest.status == status_filter)
    reqs = query.order_by(ResourceRequest.created_at.desc()).all()
    return render_template(
        "requests/list.html", requests=reqs, statuses=REQUEST_STATUSES, status_filter=status_filter
    )


@requests_bp.route("/<int:request_id>")
def view_request(request_id):
    rr = ResourceRequest.query.get_or_404(request_id)
    return render_template("requests/detail.html", rr=rr)


# ---------------------------------------------------------------------------
# Create a new request (organizer picks an event, a time window, and items)
# ---------------------------------------------------------------------------

@requests_bp.route("/new", methods=["GET", "POST"])
def new_request():
    events = Event.query.filter(Event.status.notin_(["Cancelled", "Rejected"])).order_by(
        Event.start_time.asc()
    ).all()
    resources = Resource.query.filter_by(is_active=True).order_by(Resource.type, Resource.name).all()

    if request.method == "POST":
        errors = []

        event_id = request.form.get("event_id")
        event = Event.query.get(event_id) if event_id else None
        if not event:
            errors.append("Please select a valid event.")

        try:
            start_time = parse_datetime_local(request.form.get("start_time"), "Request start time")
        except ValueError as e:
            errors.append(str(e))
            start_time = None

        try:
            end_time = parse_datetime_local(request.form.get("end_time"), "Request end time")
        except ValueError as e:
            errors.append(str(e))
            end_time = None

        if start_time and end_time and start_time >= end_time:
            errors.append("Request end time must be after the start time.")

        # Parse item rows: item_type[], item_quantity[], item_capacity[], item_preferred[]
        types_in = request.form.getlist("item_type[]")
        qty_in = request.form.getlist("item_quantity[]")
        cap_in = request.form.getlist("item_capacity[]")
        pref_in = request.form.getlist("item_preferred[]")

        items = []
        any_item = False
        for i in range(len(types_in)):
            r_type = types_in[i]
            if not r_type:
                continue  # blank row, ignore
            any_item = True
            if r_type not in RESOURCE_TYPES:
                errors.append(f"Row {i + 1}: invalid resource type.")
                continue
            try:
                qty = parse_int(qty_in[i] if i < len(qty_in) else "1", f"Row {i + 1} quantity", min_value=1)
            except ValueError as e:
                errors.append(str(e))
                continue
            try:
                cap = parse_int(
                    cap_in[i] if i < len(cap_in) else "", f"Row {i + 1} capacity", allow_none=True, min_value=1
                )
            except ValueError as e:
                errors.append(str(e))
                continue
            pref = pref_in[i] if i < len(pref_in) else ""
            pref_id = int(pref) if pref and pref.isdigit() else None
            items.append({"resource_type": r_type, "quantity": qty, "min_capacity": cap, "preferred_resource_id": pref_id})

        if not any_item:
            errors.append("Add at least one resource to the request.")

        if event and event.expected_attendance and items:
            # Sanity check: if an item is an Auditorium/Laboratory with no explicit
            # capacity given, default the requirement to the event's expected
            # attendance so a hall too small for the crowd is rejected.
            for it in items:
                if it["resource_type"] in ("Auditorium", "Laboratory") and not it["min_capacity"]:
                    it["min_capacity"] = event.expected_attendance

        if errors:
            for e in errors:
                flash(e, "error")
            return render_template(
                "requests/new.html", events=events, resources=resources, resource_types=RESOURCE_TYPES
            )

        rr = ResourceRequest(event_id=event.id, start_time=start_time, end_time=end_time, status="Pending")
        db.session.add(rr)
        db.session.flush()  # get rr.id before commit

        for it in items:
            db.session.add(ResourceRequestItem(request_id=rr.id, **it))

        db.session.commit()
        flash("Resource request submitted and is pending approval.", "success")
        return redirect(url_for("requests.view_request", request_id=rr.id))

    return render_template(
        "requests/new.html", events=events, resources=resources, resource_types=RESOURCE_TYPES
    )


# ---------------------------------------------------------------------------
# Approve / reject / cancel
# ---------------------------------------------------------------------------

@requests_bp.route("/<int:request_id>/approve", methods=["POST"])
def approve_request(request_id):
    rr = ResourceRequest.query.get_or_404(request_id)
    if rr.status != "Pending":
        flash("Only pending requests can be approved.", "error")
        return redirect(url_for("requests.view_request", request_id=rr.id))

    result = process_resource_request(rr)
    if result.success:
        flash("Request approved. All resources allocated successfully.", "success")
    else:
        flash(
            "Request could not be fully satisfied, so NO resources were allocated "
            "(all-or-nothing). See the alternative suggestions below.",
            "error",
        )
    return redirect(url_for("requests.view_request", request_id=rr.id))


@requests_bp.route("/<int:request_id>/reject", methods=["POST"])
def reject_request(request_id):
    rr = ResourceRequest.query.get_or_404(request_id)
    if rr.status != "Pending":
        flash("Only pending requests can be rejected.", "error")
        return redirect(url_for("requests.view_request", request_id=rr.id))

    reason = (request.form.get("reason") or "Rejected by admin.").strip()
    rr.status = "Rejected"
    rr.rejection_reason = reason
    db.session.commit()
    flash("Request rejected.", "success")
    return redirect(url_for("requests.view_request", request_id=rr.id))


@requests_bp.route("/<int:request_id>/cancel", methods=["POST"])
def cancel_request(request_id):
    rr = ResourceRequest.query.get_or_404(request_id)
    if rr.status not in ("Pending", "Approved"):
        flash("This request cannot be cancelled.", "error")
        return redirect(url_for("requests.view_request", request_id=rr.id))

    cancel_resource_request(rr)
    flash("Request cancelled and any allocated resources were released.", "success")
    return redirect(url_for("requests.view_request", request_id=rr.id))


@requests_bp.route("/allocations/<int:allocation_id>/cancel", methods=["POST"])
def cancel_single_allocation(allocation_id):
    alloc = Allocation.query.get_or_404(allocation_id)
    cancel_allocation(alloc)
    flash(f'Allocation of "{alloc.resource.name}" cancelled and released.', "success")
    return redirect(url_for("requests.view_request", request_id=alloc.request_id))


# ---------------------------------------------------------------------------
# Resource availability checker
# ---------------------------------------------------------------------------

@requests_bp.route("/availability", methods=["GET", "POST"])
def check_availability():
    results = None
    form_values = {"resource_type": "", "start_time": "", "end_time": "", "min_capacity": ""}

    if request.method == "POST":
        form_values["resource_type"] = request.form.get("resource_type", "")
        form_values["start_time"] = request.form.get("start_time", "")
        form_values["end_time"] = request.form.get("end_time", "")
        form_values["min_capacity"] = request.form.get("min_capacity", "")

        errors = []
        r_type = form_values["resource_type"]
        if r_type not in RESOURCE_TYPES:
            errors.append("Please choose a valid resource type.")
        try:
            start_time = parse_datetime_local(form_values["start_time"], "Start time")
        except ValueError as e:
            errors.append(str(e))
            start_time = None
        try:
            end_time = parse_datetime_local(form_values["end_time"], "End time")
        except ValueError as e:
            errors.append(str(e))
            end_time = None
        if start_time and end_time and start_time >= end_time:
            errors.append("End time must be after start time.")
        try:
            min_capacity = parse_int(form_values["min_capacity"], "Minimum capacity", allow_none=True, min_value=1)
        except ValueError as e:
            errors.append(str(e))
            min_capacity = None

        if errors:
            for e in errors:
                flash(e, "error")
        else:
            results = find_suitable_candidates(r_type, min_capacity, start_time, end_time)

    return render_template(
        "requests/availability.html",
        resource_types=RESOURCE_TYPES,
        results=results,
        form_values=form_values,
    )
