from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.config import config_manager
from db import models

def main():
    # Recupera il DB URL dal config manager
    db_url = config_manager.get_setting("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL non configurato")

    # Crea engine e session
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    
    print("⚠️ Attenzione: verranno eliminate e ricreate le tabelle di logging delle esecuzioni!")
    models.Base.metadata.drop_all(bind=engine, tables=[
        models.FlowExecutionHistory.__table__,
        models.FlowExecutionDetail.__table__,
    ])
    models.Base.metadata.create_all(bind=engine, tables=[
        models.FlowExecutionHistory.__table__,
        models.FlowExecutionDetail.__table__
    ])
    print("✅ Tabelle ricreate con successo")

if __name__ == "__main__":
    main()