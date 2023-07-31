from pydantic_settings import BaseSettings
import os
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    USER_CPF: str = os.environ.get("cpf")
    USER_PASS: str = os.environ.get("pass")
    SPREADSHEET_ID: str = os.environ.get("ssid")

settings = Settings()