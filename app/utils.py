from datetime import datetime


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
