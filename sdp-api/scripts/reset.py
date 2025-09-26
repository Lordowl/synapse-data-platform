import sys
from sqlalchemy import create_engine
from core.config import config_manager
from db import models

def main(table_names: list[str]):
    # Recupera il DB URL dal config manager
    db_url = config_manager.get_setting("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL non configurato")

    # Crea engine
    engine = create_engine(db_url, connect_args={"check_same_thread": False})

    # Recupera i modelli dal modulo models
    available_models = {
        name: cls for name, cls in vars(models).items()
        if hasattr(cls, "__table__")
    }

    # Trova i modelli richiesti
    selected_tables = []
    for name in table_names:
        model = available_models.get(name)
        if not model:
            print(f"❌ Modello '{name}' non trovato in db.models")
            continue
        selected_tables.append(model.__table__)

    if not selected_tables:
        print("⚠️ Nessuna tabella valida selezionata. Interruzione.")
        return

    # Conferma
    print("⚠️ Attenzione: verranno eliminate e ricreate le seguenti tabelle:")
    for t in selected_tables:
        print(f"   - {t.name}")

    # Drop + Create
    models.Base.metadata.drop_all(bind=engine, tables=selected_tables)
    models.Base.metadata.create_all(bind=engine, tables=selected_tables)

    print("✅ Tabelle ricreate con successo")

if __name__ == "__main__":
    # Esempio: python reset_tables.py Bank User
    if len(sys.argv) < 2:
        print("Uso: python reset_tables.py <Model1> <Model2> ...")
        sys.exit(1)

    main(sys.argv[1:])
