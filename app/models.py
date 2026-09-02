from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db

# ---------------------------------------------------------------------------
# Allowed value sets (kept as plain Python constants rather than DB enums so
# SQLite stays simple, but every write path validates against these lists).
# ---------------------------------------------------------------------------

ROLES = ["admin", "student_organiser"]

EVENT_STATUSES = ["Draft", "Pending", "Approved", "Rejected", "Cancelled", "Completed"]

RESOURCE_TYPES = ["Auditorium", "Laboratory", "Projector", "Microphone", "Camera", "Computer"]

# Resource types where a numeric "capacity" (people / seats) is meaningful.
CAPACITY_APPLICABLE_TYPES = ["Auditorium", "Laboratory"]

REQUEST_STATUSES = ["Pending", "Approved", "Rejected", "Cancelled"]

ALLOCATION_STATUSES = ["Allocated", "Cancelled"]


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(30), nullable=False, default="student_organiser")
    department = db.Column(db.String(120), nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    events = db.relationship("Event", backref="creator", lazy=True)
    resource_requests = db.relationship("ResourceRequest", backref="submitter", lazy=True)

    def __init__(self, name=None, email=None, password_hash=None, role="student_organiser", department=None, is_active=True, **kwargs):
        super().__init__(**kwargs)
        if name is not None:
            self.name = name
        if email is not None:
            self.email = email
        if password_hash is not None:
            self.password_hash = password_hash
        self.role = role
        self.department = department
        self.is_active = is_active

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    @property
    def is_student_organiser(self) -> bool:
        return self.role == "student_organiser"

    @property
    def is_authenticated(self) -> bool:
        return True

    @property
    def is_anonymous(self) -> bool:
        return False

    def __repr__(self):
        return f"<User {self.id} {self.email} ({self.role})>"


class AnonymousUser:
    id = None
    name = "Guest"
    email = ""
    role = None
    department = None
    is_active = False

    @property
    def is_admin(self) -> bool:
        return False

    @property
    def is_student_organiser(self) -> bool:
        return False

    @property
    def is_authenticated(self) -> bool:
        return False

    @property
    def is_anonymous(self) -> bool:
        return True


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
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    resource_requests = db.relationship(
        "ResourceRequest", backref="event", cascade="all, delete-orphan"
    )

    def __init__(self, name=None, organizer=None, expected_attendance=0, start_time=None, end_time=None, status="Draft", user_id=None, **kwargs):
        super().__init__(**kwargs)
        if name is not None:
            self.name = name
        if organizer is not None:
            self.organizer = organizer
        self.expected_attendance = expected_attendance
        if start_time is not None:
            self.start_time = start_time
        if end_time is not None:
            self.end_time = end_time
        self.status = status
        self.user_id = user_id

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

    def __init__(self, name=None, type=None, capacity=None, is_active=True, **kwargs):
        super().__init__(**kwargs)
        if name is not None:
            self.name = name
        if type is not None:
            self.type = type
        self.capacity = capacity
        self.is_active = is_active

    def __repr__(self):
        return f"<Resource {self.id} {self.name} ({self.type})>"


class ResourceRequest(db.Model):
    """A single organizer submission asking for a bundle of resources for an
    event, over one time window. Contains one or more ResourceRequestItem
    rows (e.g. 1x Auditorium, 1x Projector, 2x Microphone)."""

    __tablename__ = "resource_requests"

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("events.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
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

    def __init__(self, event_id=None, user_id=None, start_time=None, end_time=None, status="Pending", rejection_reason=None, **kwargs):
        super().__init__(**kwargs)
        if event_id is not None:
            self.event_id = event_id
        self.user_id = user_id
        if start_time is not None:
            self.start_time = start_time
        if end_time is not None:
            self.end_time = end_time
        self.status = status
        self.rejection_reason = rejection_reason

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

    def __init__(self, request_id=None, resource_type=None, quantity=1, min_capacity=None, preferred_resource_id=None, **kwargs):
        super().__init__(**kwargs)
        if request_id is not None:
            self.request_id = request_id
        if resource_type is not None:
            self.resource_type = resource_type
        self.quantity = quantity
        self.min_capacity = min_capacity
        self.preferred_resource_id = preferred_resource_id

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

    def __init__(self, request_id=None, item_id=None, resource_id=None, event_id=None, start_time=None, end_time=None, status="Allocated", **kwargs):
        super().__init__(**kwargs)
        if request_id is not None:
            self.request_id = request_id
        if item_id is not None:
            self.item_id = item_id
        if resource_id is not None:
            self.resource_id = resource_id
        if event_id is not None:
            self.event_id = event_id
        if start_time is not None:
            self.start_time = start_time
        if end_time is not None:
            self.end_time = end_time
        self.status = status

    def __repr__(self):
        return f"<Allocation resource={self.resource_id} event={self.event_id} {self.status}>"


