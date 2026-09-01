from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.extensions import db
from app.models import Resource, RESOURCE_TYPES, CAPACITY_APPLICABLE_TYPES
from app.utils import parse_int

resources_bp = Blueprint("resources", __name__, template_folder="../templates/resources")


def _validate_resource_fields(form):
    errors = []
    data = {}

    name = (form.get("name") or "").strip()
    if not name:
        errors.append("Resource name is required.")
    data["name"] = name

    r_type = form.get("type") or ""
    if r_type not in RESOURCE_TYPES:
        errors.append("Please choose a valid resource type.")
    data["type"] = r_type

    try:
        data["capacity"] = parse_int(form.get("capacity"), "Capacity", allow_none=True, min_value=1)
    except ValueError as e:
        errors.append(str(e))
        data["capacity"] = None

    if r_type in CAPACITY_APPLICABLE_TYPES and data["capacity"] is None:
        errors.append(f"Capacity is required for a resource of type '{r_type}'.")

    data["is_active"] = form.get("is_active") == "on"

    return data, errors


@resources_bp.route("/")
def list_resources():
    type_filter = request.args.get("type", "")
    active_filter = request.args.get("active", "")

    query = Resource.query
    if type_filter and type_filter in RESOURCE_TYPES:
        query = query.filter(Resource.type == type_filter)
    if active_filter == "active":
        query = query.filter(Resource.is_active.is_(True))
    elif active_filter == "inactive":
        query = query.filter(Resource.is_active.is_(False))

    resources = query.order_by(Resource.type.asc(), Resource.name.asc()).all()
    return render_template(
        "resources/list.html",
        resources=resources,
        types=RESOURCE_TYPES,
        type_filter=type_filter,
        active_filter=active_filter,
    )


@resources_bp.route("/new", methods=["GET", "POST"])
def new_resource():
    if request.method == "POST":
        data, errors = _validate_resource_fields(request.form)
        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("resources/form.html", resource=data, types=RESOURCE_TYPES, mode="create")

        data["is_active"] = True  # new resources default to active
        resource = Resource(**data)
        db.session.add(resource)
        db.session.commit()
        flash(f'Resource "{resource.name}" added.', "success")
        return redirect(url_for("resources.list_resources"))

    return render_template("resources/form.html", resource=None, types=RESOURCE_TYPES, mode="create")


@resources_bp.route("/<int:resource_id>/edit", methods=["GET", "POST"])
def edit_resource(resource_id):
    resource = Resource.query.get_or_404(resource_id)

    if request.method == "POST":
        data, errors = _validate_resource_fields(request.form)
        if errors:
            for e in errors:
                flash(e, "error")
            merged = {**data, "id": resource.id}
            return render_template("resources/form.html", resource=merged, types=RESOURCE_TYPES, mode="edit")

        resource.name = data["name"]
        resource.type = data["type"]
        resource.capacity = data["capacity"]
        db.session.commit()
        flash(f'Resource "{resource.name}" updated.', "success")
        return redirect(url_for("resources.list_resources"))

    return render_template("resources/form.html", resource=resource, types=RESOURCE_TYPES, mode="edit")


@resources_bp.route("/<int:resource_id>/toggle-active", methods=["POST"])
def toggle_active(resource_id):
    resource = Resource.query.get_or_404(resource_id)
    resource.is_active = not resource.is_active
    db.session.commit()
    state = "activated" if resource.is_active else "deactivated"
    flash(f'Resource "{resource.name}" {state}.', "success")
    return redirect(url_for("resources.list_resources"))
