from pydantic_settings import BaseSettings
from dotenv import load_dotenv
import os

load_dotenv()

class Config(BaseSettings):
    API_ID: int = int(os.getenv('API_ID', '0'))
    API_HASH: str = os.getenv('API_HASH', '')
    BOT_TOKEN: str = os.getenv('BOT_TOKEN', '')
    DATABASE_URL: str = os.getenv('DATABASE_URL', 'postgresql://user:password@localhost:5432/telegram_bot')
    
    class Config:
        env_file = '.env'
        env_file_encoding = 'utf-8'

config = Config()
