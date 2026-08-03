"""Create tables without Alembic (MVP bootstrap)."""

from app.db.base import Base
from app.db import models  # noqa: F401
from app.db.session import engine


def main() -> None:
    Base.metadata.create_all(bind=engine)
    print("OK: tables created")


if __name__ == "__main__":
    main()
