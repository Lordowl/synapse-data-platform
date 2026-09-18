# Re-export from parent db module to ensure single source of truth
# This avoids the issue of having two separate SessionLocal globals
from . import Base, init_db, get_db, get_db_optional

# engine e SessionLocal NON vengono importati per valore: init_db() li riassegna
# in db/__init__.py e una copia locale resterebbe ferma al valore di import (None),
# facendo lavorare l'app su un database diverso da quello configurato.
# __getattr__ (PEP 562) li risolve sul package a ogni accesso.
def __getattr__(name):
    if name in ("engine", "SessionLocal"):
        import sys
        return getattr(sys.modules[__package__], name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# Explicitly export for PyInstaller
__all__ = ['engine', 'SessionLocal', 'Base', 'init_db', 'get_db', 'get_db_optional']
