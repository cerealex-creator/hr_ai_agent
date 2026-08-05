"""Pick meeting link from candidate_comms settings (Zoom / Telemost / other)."""

from __future__ import annotations

from typing import Any

from app.services.app_settings import get_candidate_comms


def resolve_meeting_link(*, prefer: str | None = None) -> dict[str, str]:
    """
    Returns {provider, link, label} from enabled channels with a default link.
    prefer: zoom | telemost | other | None (first available).
    """
    comms = get_candidate_comms() or {}
    order = []
    if prefer in ("zoom", "telemost", "other"):
        order.append(prefer)
    for key in ("telemost", "zoom", "other"):
        if key not in order:
            order.append(key)

    for key in order:
        if key == "other":
            block = comms.get("other_video") or {}
            if not block.get("enabled"):
                continue
            link = str(block.get("default_meeting_link") or "").strip()
            if not link:
                continue
            name = str(block.get("name") or "Видеосвязь").strip() or "Видеосвязь"
            return {"provider": "other", "link": link, "label": name}
        block = comms.get(key) or {}
        if not block.get("enabled"):
            continue
        link = str(block.get("default_meeting_link") or "").strip()
        if not link:
            continue
        label = "Zoom" if key == "zoom" else "Яндекс Телемост"
        return {"provider": key, "link": link, "label": label}
    return {"provider": "", "link": "", "label": ""}


def maybe_attach_meeting_link(payload: dict[str, Any], *, force: bool = False) -> dict[str, Any]:
    """
    If remote interview and meeting_link empty, fill from settings.
    Does not overwrite an existing non-empty meeting_link unless force=True.
    """
    out = dict(payload or {})
    existing = str(out.get("meeting_link") or "").strip()
    if existing and not force:
        return out
    remote = bool(out.get("remote_interview"))
    # Also attach when scheduling interview without explicit office flag
    if not remote and not force:
        return out
    resolved = resolve_meeting_link()
    if not resolved.get("link"):
        return out
    out["meeting_link"] = resolved["link"]
    out["meeting_provider"] = resolved.get("provider") or ""
    out["meeting_provider_label"] = resolved.get("label") or ""
    return out
