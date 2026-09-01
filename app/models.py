from datetime import datetime
from app.extensions import db

# ---------------------------------------------------------------------------
# Allowed value sets (kept as plain Python constants rather than DB enums so
# SQLite stays simple, but every write path validates against these lists).
# ---------------------------------------------------------------------------

EVENT_STATUSES = ["Draft", "Pending", "Approved", "Rejected", "Cancelled", "Completed"]

RESOURCE_TYPES = ["Auditorium", "Laboratory", "Projector", "Microphone", "Camera", "Computer"]

# Resource types where a numeric "capacity" (people / seats) is meaningful.
CAPACITY_APPLICABLE_TYPES = ["Auditorium", "Laboratory"]

REQUEST_STATUSES = ["Pending", "Approved", "Rejected", "Cancelled"]

ALLOCATION_STATUSES = ["Allocated", "Cancelled"]


class Event(db.Model):
    __tablename__ = "events"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    organizer = db.Column(db.String(120), nullable=False)
    expected_attendance = db.Column(db.Integer, nullable=False, default=0)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="Draft")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    resource_requests = db.relationship(
        "ResourceRequest", backref="event", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Event {self.id} {self.name}>"


class Resource(db.Model):
    __tablename__ = "resources"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    type = db.Column(db.String(30), nullable=False)
    capacity = db.Column(db.Integer, nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Resource {self.id} {self.name} ({self.type})>"


class ResourceRequest(db.Model):
    """A single organizer submission asking for a bundle of resources for an
    event, over one time window. Contains one or more ResourceRequestItem
    rows (e.g. 1x Auditorium, 1x Projector, 2x Microphone)."""

    __tablename__ = "resource_requests"

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("events.id"), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="Pending")
    rejection_reason = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    decided_at = db.Column(db.DateTime, nullable=True)

    items = db.relationship(
        "ResourceRequestItem", backref="request", cascade="all, delete-orphan"
    )
    allocations = db.relationship(
        "Allocation", backref="request", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<ResourceRequest {self.id} for event {self.event_id}>"


class ResourceRequestItem(db.Model):
    """One line of a request, e.g. '2x Microphone, min capacity n/a'."""

    __tablename__ = "resource_request_items"

    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, db.ForeignKey("resource_requests.id"), nullable=False)
    resource_type = db.Column(db.String(30), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    min_capacity = db.Column(db.Integer, nullable=True)
    preferred_resource_id = db.Column(db.Integer, db.ForeignKey("resources.id"), nullable=True)

    preferred_resource = db.relationship("Resource", foreign_keys=[preferred_resource_id])

    def __repr__(self):
        return f"<Item {self.quantity}x {self.resource_type}>"


class Allocation(db.Model):
    """A concrete, confirmed assignment of one specific Resource to one
    Event for a specific time window. This is the row that conflict
    detection (double-booking prevention) actually queries."""

    __tablename__ = "allocations"

    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, db.ForeignKey("resource_requests.id"), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey("resource_request_items.id"), nullable=False)
    resource_id = db.Column(db.Integer, db.ForeignKey("resources.id"), nullable=False)
    event_id = db.Column(db.Integer, db.ForeignKey("events.id"), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="Allocated")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    resource = db.relationship("Resource")
    event = db.relationship("Event")

    def __repr__(self):
        return f"<Allocation resource={self.resource_id} event={self.event_id} {self.status}>"
