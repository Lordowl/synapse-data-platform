
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Queste variabili devono corrispondere ai nomi nel file .env
    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int

    class Config:
        # Dice a Pydantic di caricare le variabili dal file .env
        env_file = ".env"

# Creiamo un'istanza delle impostazioni che importeremo nel resto dell'app
settings = Settings()