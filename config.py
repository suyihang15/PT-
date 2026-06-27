import os
from datetime import timedelta

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    """Base configuration."""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-me')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', f'sqlite:///{os.path.join(BASE_DIR, "app.db")}')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
    }

    # Session
    PERMANENT_SESSION_LIFETIME = timedelta(days=30)

    # Upload
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB max upload

    # Tracker
    ANNOUNCE_INTERVAL = 1800  # 30 minutes default
    ANNOUNCE_MIN_INTERVAL = 900  # 15 minutes
    PEER_EXPIRE_SECONDS = 1800  # 30 min stale peer removal
    PEER_LIMIT = 50  # max peers returned per announce

    # H&R
    HNR_MIN_SEED_HOURS = 72  # minimum seeding hours to avoid H&R
    HNR_MIN_RATIO = 1.0  # minimum ratio to avoid H&R
    HNR_GRACE_HOURS = 168  # grace period before H&R check (7 days)

    # Ratio
    MIN_RATIO_TO_DOWNLOAD = 0.4  # below this, cannot download new torrents

    # Bonus
    DEFAULT_BONUS_PER_HOUR = 1.0  # base points per hour per torrent

    # Cache
    CACHE_TYPE = 'SimpleCache'
    CACHE_DEFAULT_TIMEOUT = 300

    # CSRF
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600  # 1 hour


class DevConfig(Config):
    DEBUG = True
    SQLALCHEMY_ECHO = False
    TEMPLATES_AUTO_RELOAD = True


class ProdConfig(Config):
    DEBUG = False
    SQLALCHEMY_ECHO = False


config_map = {
    'development': DevConfig,
    'production': ProdConfig,
    'default': DevConfig,
}
