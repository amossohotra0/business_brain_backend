import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    SUPABASE_URL: str = os.getenv("SUPABASE_URL")
    SUPABASE_KEY: str = os.getenv("SUPABASE_KEY")
    SECRET_KEY: str = os.getenv("SECRET_KEY")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY")
    
    # Google OAuth
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET: str = os.getenv("GOOGLE_CLIENT_SECRET")
    GOOGLE_REDIRECT_URI: str = os.getenv("GOOGLE_REDIRECT_URI")
    GOOGLE_AUTH_URI: str = os.getenv("GOOGLE_AUTH_URI", "https://accounts.google.com/o/oauth2/auth")
    GOOGLE_TOKEN_URI: str = os.getenv("GOOGLE_TOKEN_URI", "https://oauth2.googleapis.com/token")
    
    # Google Cloud
    GOOGLE_CLOUD_PROJECT: str = os.getenv("GOOGLE_CLOUD_PROJECT")
    GMAIL_TOPIC_NAME: str = os.getenv("GMAIL_TOPIC_NAME", "gmail-updates")

settings = Settings()