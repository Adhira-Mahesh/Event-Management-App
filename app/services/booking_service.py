"""
Core booking logic for the College Event Resource Allocation System.

This module is intentionally kept independent of Flask request/response
objects so it can be unit-tested or reused from scripts. It only knows
about SQLAlchemy models and plain Python data.
"""

from dataclasses import dataclass, field
from typing import List, Optional

from app.extensions import db
from app.models import Resource, Allocation, ResourceRequest, ResourceRequestItem


class ValidationError(Exception):
    """Raised for any request that fails business-rule validation."""


# ---------------------------------------------------------------------------
# Conflict detection
# ---------------------------------------------------------------------------

def get_overlapping_allocations(resource_id, start, end, exclude_request_id=None):
    """Return all *active* (status == 'Allocated') allocations for a given
    resource whose time window overlaps [start, end).

    Two intervals [s1, e1) and [s2, e2) overlap iff s1 < e2 AND s2 < e1.
    This is the standard interval-overlap test and correctly allows
    back-to-back bookings (e.g. one ending at 2pm, another starting at 2pm).
    """
    query = Allocation.query.filter(
        Allocation.resource_id == resource_id,
        Allocation.status == "Allocated",
        Allocation.start_time < end,
        Allocation.end_time > start,
    )
    if exclude_request_id is not None:
        query = query.filter(Allocation.request_id != exclude_request_id)
    return query.all()


def is_resource_available(resource_id, start, end, exclude_request_id=None):
    return len(get_overlapping_allocations(resource_id, start, end, exclude_request_id)) == 0


# ---------------------------------------------------------------------------
# Suitability + candidate search
# ---------------------------------------------------------------------------

def find_suitable_candidates(resource_type, min_capacity, start, end, exclude_ids=None):
    """Return active resources of the correct type, with enough capacity
    (if capacity is meaningful for that type / was requested), that are
    NOT already booked in the [start, end) window. Sorted so the
    "best fit" (smallest sufficient capacity first) comes first -- this
    avoids handing a 500-seat auditorium to a 20-person meeting when a
    smaller suitable room is free.
    """
    exclude_ids = exclude_ids or set()

    query = Resource.query.filter(
        Resource.type == resource_type,
        Resource.is_active.is_(True),
    )
    if exclude_ids:
        query = query.filter(~Resource.id.in_(exclude_ids))

    if min_capacity:
        # Resources with no capacity value at all can't satisfy a capacity
        # requirement.
        query = query.filter(
            Resource.capacity.isnot(None), Resource.capacity >= min_capacity
        )

    candidates = query.order_by(
        Resource.capacity.is_(None), Resource.capacity.asc()
    ).all()

    available = [r for r in candidates if is_resource_available(r.id, start, end)]
    return available


def suggest_alternatives(resource_type, min_capacity, start, end, exclude_ids=None, limit=3):
    """Suggest suitable, available alternative resources of the SAME type
    (an alternative must still be the correct type -- a microphone can
    never substitute for a projector). Reuses find_suitable_candidates,
    which already enforces: active, correct type, sufficient capacity,
    and free at the requested time.
    """
    return find_suitable_candidates(resource_type, min_capacity, start, end, exclude_ids)[:limit]


# ---------------------------------------------------------------------------
# Result objects
# ---------------------------------------------------------------------------

@dataclass
class ItemFailure:
    item: ResourceRequestItem
    reason: str
    alternatives: List[Resource] = field(default_factory=list)


@dataclass
class AllocationResult:
    success: bool
    request: ResourceRequest
    failures: List[ItemFailure] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Transactional allocation
# ---------------------------------------------------------------------------

def process_resource_request(resource_request: ResourceRequest) -> AllocationResult:
    """Attempt to allocate concrete resources for every item on a request.

    All-or-nothing guarantee: if ANY item cannot be fully satisfied, NO
    allocations are written for ANY item on this request. We do this by
    only building a plan (in memory) first, and only touching the database
    (db.session.add / commit) once we know every item can be satisfied.
    On any unexpected error we roll back explicitly as well, so a partial
    write can never survive.
    """
    used_ids = set()
    plan = []  # list of (item, resource)
    failures = []

    for item in resource_request.items:
        candidates = []

        # If the organizer named a preferred specific resource, try it first.
        if item.preferred_resource_id:
            preferred = Resource.query.get(item.preferred_resource_id)
            if (
                preferred
                and preferred.is_active
                and preferred.type == item.resource_type
                and preferred.id not in used_ids
                and (not item.min_capacity or (preferred.capacity or 0) >= item.min_capacity)
                and is_resource_available(preferred.id, resource_request.start_time, resource_request.end_time)
            ):
                candidates.append(preferred)

        if len(candidates) < item.quantity:
            more = find_suitable_candidates(
                item.resource_type,
                item.min_capacity,
                resource_request.start_time,
                resource_request.end_time,
                exclude_ids=used_ids | {c.id for c in candidates},
            )
            for r in more:
                if len(candidates) >= item.quantity:
                    break
                candidates.append(r)

        if len(candidates) < item.quantity:
            reason_parts = [f"Need {item.quantity}x {item.resource_type}"]
            if item.min_capacity:
                reason_parts.append(f"with capacity >= {item.min_capacity}")
            reason_parts.append(
                f"but only {len(candidates)} active, suitable, available resource(s) found "
                f"for the requested time window."
            )
            failures.append(
                ItemFailure(
                    item=item,
                    reason=" ".join(reason_parts),
                    alternatives=suggest_alternatives(
                        item.resource_type,
                        item.min_capacity,
                        resource_request.start_time,
                        resource_request.end_time,
                        exclude_ids=used_ids,
                    ),
                )
            )
            continue

        for r in candidates:
            used_ids.add(r.id)
            plan.append((item, r))

    if failures:
        # Nothing was written to the DB in this branch -- pure read-only
        # planning above -- so there is nothing to roll back.
        resource_request.status = "Rejected"
        reason_lines = []
        for f in failures:
            line = f"{f.item.resource_type}: {f.reason}"
            if f.alternatives:
                alt_names = ", ".join(f"{a.name} (cap {a.capacity})" if a.capacity else a.name for a in f.alternatives)
                line += f" Suggested alternative(s): {alt_names}."
            else:
                line += " No suitable alternatives were found."
            reason_lines.append(line)
        resource_request.rejection_reason = " | ".join(reason_lines)
        db.session.commit()
        return AllocationResult(success=False, request=resource_request, failures=failures)

    try:
        for item, resource in plan:
            allocation = Allocation(
                request_id=resource_request.id,
                item_id=item.id,
                resource_id=resource.id,
                event_id=resource_request.event_id,
                start_time=resource_request.start_time,
                end_time=resource_request.end_time,
                status="Allocated",
            )
            db.session.add(allocation)
        resource_request.status = "Approved"
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return AllocationResult(success=True, request=resource_request)


def cancel_resource_request(resource_request: ResourceRequest):
    """Cancel a request and release (cancel) every allocation tied to it,
    freeing the resources for future bookings."""
    resource_request.status = "Cancelled"
    for alloc in resource_request.allocations:
        if alloc.status == "Allocated":
            alloc.status = "Cancelled"
    db.session.commit()


def cancel_allocation(allocation: Allocation):
    """Cancel a single allocation, releasing that one resource."""
    allocation.status = "Cancelled"
    db.session.commit()
