"""Compatibility migrations for the project's pre-Alembic database."""

from sqlalchemy import inspect, text

from . import models
from .database import engine


def ensure_compatibility_columns() -> None:
    """Add extension columns that ``create_all`` cannot add to old tables."""
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    targets = [
        ("media_kit_content", models.MediaKitContent.__table__.c.extras),
        ("collabs", models.Collab.__table__.c.details),
    ]

    for table_name, column in targets:
        if table_name not in tables:
            continue
        existing = {item["name"] for item in inspector.get_columns(table_name)}
        if column.name in existing:
            continue
        column_type = column.type.compile(dialect=engine.dialect)
        with engine.begin() as connection:
            connection.execute(
                text(
                    f"ALTER TABLE {table_name} "
                    f"ADD COLUMN {column.name} {column_type}"
                )
            )
