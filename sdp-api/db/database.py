# Re-export from parent db module to ensure single source of truth
# This avoids the issue of having two separate SessionLocal globals
from . import engine, SessionLocal, Base, init_db, get_db, get_db_optional

# Explicitly export for PyInstaller
__all__ = ['engine', 'SessionLocal', 'Base', 'init_db', 'get_db', 'get_db_optional']