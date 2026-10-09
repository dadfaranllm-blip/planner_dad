"""Idempotent schema bootstrap/migration runner for the integrated release.
Never drops tables or data. Future destructive/transform migrations must be explicit here.
"""
from sqlalchemy import text
from app.main import Base, engine
Base.metadata.create_all(engine)
with engine.begin() as c:
    c.execute(text("CREATE TABLE IF NOT EXISTS schema_migrations (version varchar(80) primary key, applied_at timestamp default CURRENT_TIMESTAMP)"))
    c.execute(text("INSERT INTO schema_migrations(version) VALUES ('planner-integrated-2026-09-30') ON CONFLICT (version) DO NOTHING") if engine.dialect.name=='postgresql' else text("INSERT OR IGNORE INTO schema_migrations(version) VALUES ('planner-integrated-2026-09-30')"))
print('schema migration complete')
