"""Drop and recreate all ORM tables, including optional columns used by newer code paths."""

import app.models.models  # noqa: F401 — register models on Base.metadata

from app.db import Base, create_all_tables, engine

print("Dropping tables...")
Base.metadata.drop_all(bind=engine)
print("Creating tables...")
create_all_tables()
print("Database flushed.")
