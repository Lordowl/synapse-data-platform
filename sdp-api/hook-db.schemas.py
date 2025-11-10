# PyInstaller hook per forzare l'inclusione di db.schemas
from PyInstaller.utils.hooks import collect_all

datas, binaries, hiddenimports = collect_all('db.schemas', include_py_files=True)

# Forza l'uso del file locale
import os
import sys

# Ottieni il path assoluto di schemas.py
schemas_path = os.path.join(os.getcwd(), 'db', 'schemas.py')
print(f"[HOOK] Forzando uso di {schemas_path}")

# Aggiungi come data
datas.append((schemas_path, 'db'))
