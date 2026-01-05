import os
from datetime import timedelta


def env_bool(name: str, default: bool = False) -> bool:
    v = os.environ.get(name)
    if v is None:
        return default
    return str(v).strip().lower() in ('1', 'true', 't', 'yes', 'y', 'on')

def env_list(name: str) -> list[str]:
    v = os.environ.get(name)
    if not v:
        return []
    return [x.strip() for x in v.split(',') if x.strip()]


class BaseConfig:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'localhost')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 8025))
    MAIL_USE_TLS = env_bool('MAIL_USE_TLS', False)
    MAIL_USE_SSL = env_bool('MAIL_USE_SSL', False)
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'no-reply@local')
    MAIL_SUPPRESS_SEND = env_bool('MAIL_SUPPRESS_SEND', True)
    NOTIFY_TICKETS_TO = env_list('NOTIFY_TICKETS_TO')
    # Branding (can be overridden via .env)
    BRAND_PRIMARY = os.environ.get('BRAND_PRIMARY', '#2563eb')
    BRAND_PRIMARY_DARK = os.environ.get('BRAND_PRIMARY_DARK', '#1d4ed8')
    BRAND_PRIMARY_LIGHT = os.environ.get('BRAND_PRIMARY_LIGHT', '#3b82f6')

    WTF_CSRF_TIME_LIMIT = None

    # Sessions
    PERMANENT_SESSION_LIFETIME = timedelta(seconds=int(os.environ.get('SESSION_LIFETIME_SECONDS', 60 * 60 * 8)))
    # Timezone for display
    TIMEZONE = os.environ.get('TIMEZONE', 'America/Sao_Paulo')

    # IMAP inbound (email -> ticket)
    IMAP_HOST = os.environ.get('IMAP_HOST')
    IMAP_PORT = int(os.environ.get('IMAP_PORT', 993))
    IMAP_SSL = os.environ.get('IMAP_SSL', '1') == '1'
    IMAP_USERNAME = os.environ.get('IMAP_USERNAME')
    IMAP_PASSWORD = os.environ.get('IMAP_PASSWORD')


class DevelopmentConfig(BaseConfig):
    DEBUG = True


class ProductionConfig(BaseConfig):
    DEBUG = False
    MAIL_SUPPRESS_SEND = False
