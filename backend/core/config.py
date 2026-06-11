from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    ENV: str = 'development'
    SECRET_KEY: str
    ALLOWED_HOSTS: str = 'localhost'
    CORS_ALLOWED_ORIGINS: str = 'http://localhost:3000'

    DATABASE_URL: str
    REDIS_URL: str

    ZOOM_CLIENT_ID: str = ''
    ZOOM_CLIENT_SECRET: str = ''
    ZOOM_WEBHOOK_SECRET_TOKEN: str = ''
    ZOOM_REDIRECT_URI: str = ''

    SUPABASE_URL: str = ''
    SUPABASE_SERVICE_KEY: str = ''

    ANTHROPIC_API_KEY: str = ''
    OPENAI_API_KEY: str = ''

    AWS_ACCESS_KEY_ID: str = ''
    AWS_SECRET_ACCESS_KEY: str = ''
    AWS_DEFAULT_REGION: str = 'ap-south-1'
    AWS_S3_BUCKET: str = ''

    AUTH0_DOMAIN: str = ''
    AUTH0_CLIENT_ID: str = ''
    AUTH0_CLIENT_SECRET: str = ''
    AUTH0_AUDIENCE: str = ''

    SENDGRID_API_KEY: str = ''
    FROM_EMAIL: str = ''
    ADMIN_ALERT_EMAIL: str = ''

    SENTRY_DSN: str = ''

    class Config:
        env_file = '.env'
        extra = 'ignore'

settings = Settings()