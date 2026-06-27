import os
from flask import Flask
from config import config_map


def create_app(config_name=None):
    """Application factory."""
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')

    app = Flask(__name__)
    app.config.from_object(config_map.get(config_name, config_map['default']))

    # Enable SQLite WAL mode for better concurrency
    if 'sqlite' in app.config.get('SQLALCHEMY_DATABASE_URI', ''):
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
            'pool_pre_ping': True,
            'connect_args': {'check_same_thread': False},
        }

    # Initialize extensions
    from app.extensions import db, login_manager, migrate, cache, csrf
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    cache.init_app(app)
    csrf.init_app(app)

    # User loader for Flask-Login
    from app.models.user import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    # Import all models to ensure they're registered and create tables
    with app.app_context():
        from app.models import (
            User, Invite, UserMedal,
            SiteSetting, News, Report, Log, Medal, Warning, Announcement,
            Category, Tag, TorrentTag, Torrent, File, Comment, Bookmark, Thank,
            Peer, Snatch, HnrViolation,
            SeedBonusRate, SeedBonusLog, BonusShopItem, BonusPurchase,
            PrivateMessage,
            Forum, ForumTopic, ForumPost,
            BanLog, IpLog, IpBan, IpWhitelist, UserClass, PromotionLog,
            QBittorrentConfig, QBittorrentSyncLog,
        )
        db.create_all()
        # Seed default data if empty
        if User.query.count() == 0:
            _seed_default_data()

    # Register custom filters and context processors
    from app.helpers import register_template_filters, register_context_processors, register_error_handlers
    register_template_filters(app)
    register_context_processors(app)
    register_error_handlers(app)

    # Register blueprints
    from app.blueprints.main.routes import main_bp
    from app.blueprints.auth.routes import auth_bp
    from app.blueprints.torrent.routes import torrent_bp
    from app.blueprints.user.routes import user_bp
    from app.blueprints.bonus.routes import bonus_bp
    from app.blueprints.admin import admin_bp
    from app.blueprints.api.routes import api_bp
    from app.blueprints.rss.routes import rss_bp
    from app.blueprints.forum.routes import forum_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(torrent_bp, url_prefix='/torrent')
    app.register_blueprint(user_bp, url_prefix='/user')
    app.register_blueprint(bonus_bp, url_prefix='/bonus')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(rss_bp, url_prefix='/rss')
    app.register_blueprint(forum_bp, url_prefix='/forum')

    # Register tracker routes directly (no blueprint prefix)
    from app.blueprints.tracker.routes import tracker_bp
    app.register_blueprint(tracker_bp)

    # Create storage directories
    os.makedirs(os.path.join(app.root_path, '..', 'storage', 'torrents'), exist_ok=True)
    os.makedirs(os.path.join(app.root_path, 'static', 'uploads', 'avatars'), exist_ok=True)

    # Track user activity
    from datetime import datetime, timezone
    from flask import request
    from flask_login import current_user

    @app.before_request
    def track_user_activity():
        if current_user.is_authenticated:
            current_user.last_active_at = datetime.now(timezone.utc)
            current_user.last_ip = request.remote_addr
            # Don't commit here - let the request cycle handle it for writes,
            # but we need to flush for reads. We'll rely on auto-commit at end of request.

    @app.teardown_request
    def save_user_activity(exception=None):
        if exception is None:
            try:
                from flask_login import current_user
                if hasattr(current_user, 'is_authenticated') and current_user.is_authenticated:
                    db.session.commit()
            except Exception:
                db.session.rollback()

    # Initialize scheduler (skip in debug reloader subprocess)
    import sys
    if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        from app.tasks.scheduler import init_scheduler
        init_scheduler(app)

    return app


def _seed_default_data():
    """Seed database with default categories, settings, admin user, etc."""
    from app.extensions import db
    from app.models.user import User
    from app.models.torrent import Category
    from app.models.system import SiteSetting
    from app.models.bonus import SeedBonusRate, BonusShopItem
    from app.models.forum import Forum
    from decimal import Decimal

    # Categories
    cats = [
        Category(name='电影', slug='movies', icon='film', sort_order=1),
        Category(name='电视剧', slug='tv', icon='tv', sort_order=2),
        Category(name='纪录片', slug='documentary', icon='camera-video', sort_order=3),
        Category(name='动漫', slug='anime', icon='boombox', sort_order=4),
        Category(name='音乐', slug='music', icon='music-note', sort_order=5),
        Category(name='软件', slug='software', icon='windows', sort_order=6),
        Category(name='游戏', slug='games', icon='controller', sort_order=7),
        Category(name='其他', slug='other', icon='folder', sort_order=8),
    ]
    for c in cats:
        db.session.add(c)
    db.session.flush()

    movies = Category.query.filter_by(slug='movies').first()
    for name, slug in [('华语电影', 'chinese-movies'), ('欧美电影', 'western-movies'), ('日韩电影', 'asian-movies')]:
        db.session.add(Category(name=name, slug=slug, parent_id=movies.id))

    # Admin user
    admin = User.create_user('admin', 'admin@example.com', 'admin123', role='Sysop')
    admin.invite_tokens = 100
    admin.seed_bonus = 10000
    # Sysop gets all permissions implicitly, but we still store them
    admin.set_all_permissions(True)
    db.session.add(admin)

    # Moderator test user
    moderator = User.create_user('moderator', 'mod@example.com', 'mod123', role='Moderator')
    moderator.invite_tokens = 20
    moderator.seed_bonus = 5000
    from app.services.admin_permission_service import DEFAULT_MODERATOR_PERMISSIONS
    for perm in DEFAULT_MODERATOR_PERMISSIONS:
        moderator.set_permission(perm, True)
    db.session.add(moderator)

    # Settings
    for key, val, vtype, desc in [
        ('site_name', 'BT种子管理系统', 'string', '站点名称'),
        ('site_description', '私有BT种子分享社区', 'string', '站点描述'),
        ('invite_only', 'false', 'bool', '是否仅允许邀请注册'),
        ('register_open', 'true', 'bool', '是否开放注册'),
    ]:
        db.session.add(SiteSetting(key=key, value=val, value_type=vtype, description=desc))

    # Bonus rates
    for min_gb, max_gb, pph in [(0, 1, 0.5), (1, 10, 1.0), (10, 50, 2.0), (50, None, 3.0)]:
        db.session.add(SeedBonusRate(
            min_size_gb=Decimal(str(min_gb)),
            max_size_gb=Decimal(str(max_gb)) if max_gb else None,
            points_per_hour=Decimal(str(pph)),
        ))

    # Shop items
    for name, price, etype, evalue, icon in [
        ('上传量 +10GB', 500, 'upload_credit', '{"upload_gb": 10}', 'cloud-upload'),
        ('上传量 +50GB', 2000, 'upload_credit', '{"upload_gb": 50}', 'cloud-upload'),
        ('邀请码 x1', 3000, 'invite', '{"invites": 1}', 'envelope-plus'),
        ('VIP 30天', 10000, 'vip_days', '{"vip_days": 30}', 'star'),
    ]:
        db.session.add(BonusShopItem(name=name, price=price, effect_type=etype, effect_value=evalue, icon=icon))

    # Forums
    for name, desc, slug, order, mp in [
        ('公告区', '站点公告和重要通知', 'announcements', 1, 'Moderator'),
        ('种子讨论', '讨论种子资源和分享', 'torrent-discussion', 2, 'User'),
        ('求助问答', '提问和解答', 'help', 3, 'User'),
        ('闲聊灌水', '随便聊聊', 'general', 4, 'User'),
    ]:
        db.session.add(Forum(name=name, description=desc, slug=slug, sort_order=order, min_role_post=mp))

    # User class hierarchy (auto-promotion)
    from app.models.admin import UserClass
    from decimal import Decimal
    user_classes = [
        UserClass(name='User', display_name='普通用户', level=0, sort_order=0, color='#6c757d',
                  min_upload_gb=Decimal('0'), min_ratio=Decimal('0'), min_seed_hours=0,
                  min_account_age_days=0, min_forum_posts=0, min_snatches=0,
                  keep_min_ratio=Decimal('0'), keep_min_seed_hours=0,
                  invite_tokens_per_month=0, pm_inbox_size=100, bonus_multiplier=Decimal('1.0'),
                  download_slots=2, wait_time_seconds=30),
        UserClass(name='PowerUser', display_name='高级用户', level=1, sort_order=1, color='#28a745',
                  min_upload_gb=Decimal('50'), min_ratio=Decimal('1.05'), min_seed_hours=72,
                  min_account_age_days=30, min_forum_posts=0, min_snatches=5,
                  keep_min_ratio=Decimal('0.95'), keep_min_seed_hours=48,
                  invite_tokens_per_month=2, pm_inbox_size=200, bonus_multiplier=Decimal('1.5'),
                  download_slots=3, wait_time_seconds=15),
        UserClass(name='VIP', display_name='VIP会员', level=2, sort_order=2, color='#ffc107',
                  min_upload_gb=Decimal('500'), min_ratio=Decimal('2.0'), min_seed_hours=240,
                  min_account_age_days=90, min_forum_posts=10, min_snatches=30,
                  keep_min_ratio=Decimal('1.5'), keep_min_seed_hours=120,
                  invite_tokens_per_month=5, pm_inbox_size=500, bonus_multiplier=Decimal('2.0'),
                  download_slots=10, wait_time_seconds=0, can_view_peers=True,
                  can_use_freeleech_tokens=True, exempt_from_wait_time=True),
        UserClass(name='Moderator', display_name='版主', level=3, sort_order=3, color='#17a2b8',
                  min_upload_gb=Decimal('0'), min_ratio=Decimal('0'), min_seed_hours=0,
                  min_account_age_days=0, min_forum_posts=0, min_snatches=0,
                  keep_min_ratio=Decimal('0'), keep_min_seed_hours=0,
                  invite_tokens_per_month=10, pm_inbox_size=1000, bonus_multiplier=Decimal('3.0'),
                  download_slots=20, wait_time_seconds=0, can_view_peers=True,
                  can_use_freeleech_tokens=True, exempt_from_hnr=True, exempt_from_wait_time=True),
        UserClass(name='Admin', display_name='管理员', level=4, sort_order=4, color='#dc3545',
                  min_upload_gb=Decimal('0'), min_ratio=Decimal('0'), min_seed_hours=0,
                  min_account_age_days=0, min_forum_posts=0, min_snatches=0,
                  keep_min_ratio=Decimal('0'), keep_min_seed_hours=0,
                  invite_tokens_per_month=50, pm_inbox_size=2000, bonus_multiplier=Decimal('5.0'),
                  download_slots=50, wait_time_seconds=0, can_view_peers=True,
                  can_use_freeleech_tokens=True, exempt_from_hnr=True, exempt_from_wait_time=True),
    ]
    for uc in user_classes:
        existing = UserClass.query.filter_by(name=uc.name).first()
        if not existing:
            db.session.add(uc)

    db.session.commit()
