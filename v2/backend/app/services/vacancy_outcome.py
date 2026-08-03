HIRE_STAGES = ("started_work", "internship")


def soft_vacancy_outcome(
    *,
    active: bool,
    close_reason: str | None,
    has_hire: bool,
) -> str | None:
    """UI hint for archive rows. Not a final domain decision."""
    if active:
        return None
    reason = (close_reason or "").strip()
    if reason == "success" or has_hire:
        return "success"
    if reason == "client_cancelled":
        return "client_cancelled"
    return "no_result"


def close_reason_from_payload(payload: dict | None) -> str | None:
    if not payload:
        return None
    value = payload.get("close_reason")
    if value is None or value == "":
        return None
    return str(value)
