"""organizations.integrations JSONB (per-org Zoom OAuth tokens)

Revision ID: e5f6a7b8c9d0
Revises: c4d5e6f7a8b9
Create Date: 2026-08-08

"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, None] = "c4d5e6f7a8b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _legacy_token_path() -> Path:
    env = (os.getenv("ZOOM_TOKEN_PATH") or "").strip()
    if env:
        return Path(env)
    legacy = (os.getenv("LEGACY_DATA_DIR") or "").strip()
    if legacy:
        return Path(legacy) / "zoom_oauth_token.json"
    # alembic cwd is usually v2/backend → repo data/
    here = Path(__file__).resolve()
    # …/v2/backend/alembic/versions → parents[4] = repo root
    # In Docker (/app/alembic/versions) parents are shorter — skip legacy import.
    if len(here.parents) > 4:
        return here.parents[4] / "data" / "zoom_oauth_token.json"
    return Path("/nonexistent/zoom_oauth_token.json")


def _load_legacy_token() -> dict[str, Any]:
    candidates: list[Path] = [_legacy_token_path()]
    cwd = Path.cwd().resolve()
    # Local layouts: backend cwd → ../data or ../../data; skip when parents are short (Docker /app).
    if len(cwd.parents) > 0:
        candidates.append(cwd.parents[0] / "data" / "zoom_oauth_token.json")
    if len(cwd.parents) > 1:
        candidates.append(cwd.parents[1] / "data" / "zoom_oauth_token.json")
    path = next((c for c in candidates if c.is_file()), None)
    if path is None:
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "organizations" not in set(inspector.get_table_names()):
        return
    cols = {c["name"] for c in inspector.get_columns("organizations")}
    if "integrations" not in cols:
        op.add_column(
            "organizations",
            sa.Column(
                "integrations",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
        )

    legacy = _load_legacy_token()
    if not legacy.get("access_token") and not legacy.get("refresh_token"):
        return

    zoom_payload = {
        "access_token": str(legacy.get("access_token") or "").strip(),
        "refresh_token": str(legacy.get("refresh_token") or "").strip(),
        "expires_at": int(legacy.get("expires_at") or legacy.get("expiry") or 0),
        "scope": str(legacy.get("scope") or ""),
        "token_type": str(legacy.get("token_type") or "bearer"),
    }
    default_slug = (os.getenv("DEFAULT_ORG_SLUG") or "default").strip() or "default"
    integrations = json.dumps({"zoom": zoom_payload}, ensure_ascii=False)

    # Prefer default org; otherwise first organization without zoom tokens.
    conn = op.get_bind()
    row = conn.execute(
        sa.text(
            "SELECT id, integrations FROM organizations WHERE slug = :slug LIMIT 1"
        ),
        {"slug": default_slug},
    ).fetchone()
    if row is None:
        row = conn.execute(
            sa.text("SELECT id, integrations FROM organizations ORDER BY created_at ASC LIMIT 1")
        ).fetchone()
    if row is None:
        return
    org_id, current = row[0], row[1] or {}
    if isinstance(current, str):
        try:
            current = json.loads(current)
        except Exception:
            current = {}
    if not isinstance(current, dict):
        current = {}
    zoom = current.get("zoom") if isinstance(current.get("zoom"), dict) else {}
    if zoom.get("access_token") or zoom.get("refresh_token"):
        return
    conn.execute(
        sa.text(
            "UPDATE organizations SET integrations = CAST(:payload AS jsonb) WHERE id = :id"
        ),
        {"payload": integrations, "id": str(org_id)},
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "organizations" not in set(inspector.get_table_names()):
        return
    cols = {c["name"] for c in inspector.get_columns("organizations")}
    if "integrations" in cols:
        op.drop_column("organizations", "integrations")
