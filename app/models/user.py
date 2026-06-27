import secrets
from datetime import datetime, timezone
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db


class User(UserMixin, db.Model):
    __tablename__ = 'user'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(32), unique=True, nullable=False, index=True)
    email = db.Column(db.String(128), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    passkey = db.Column(db.String(64), unique=True, nullable=False, index=True)

    # Role: User, PowerUser, VIP, Moderator, Admin, Sysop
    role = db.Column(db.String(16), nullable=False, default='User', index=True)

    # Stats (bytes)
    uploaded = db.Column(db.BigInteger, nullable=False, default=0)
    downloaded = db.Column(db.BigInteger, nullable=False, default=0)
    real_uploaded = db.Column(db.BigInteger, nullable=False, default=0)
    real_downloaded = db.Column(db.BigInteger, nullable=False, default=0)
    seed_bonus = db.Column(db.Numeric(12, 2), nullable=False, default=0.00)
    invite_tokens = db.Column(db.Integer, nullable=False, default=0)

    # Activity counts
    seeding_count = db.Column(db.Integer, nullable=False, default=0)
    leeching_count = db.Column(db.Integer, nullable=False, default=0)
    completed_count = db.Column(db.Integer, nullable=False, default=0)
    snatched_count = db.Column(db.Integer, nullable=False, default=0)
    uploaded_today = db.Column(db.BigInteger, nullable=False, default=0)
    downloaded_today = db.Column(db.BigInteger, nullable=False, default=0)

    # Profile
    avatar_url = db.Column(db.String(256))
    signature = db.Column(db.String(512))
    title = db.Column(db.String(128))
    info_text = db.Column(db.Text)

    # Admin permissions (JSON map: permission_name -> bool)
    admin_permissions = db.Column(db.Text)  # Stored as JSON string

    # Status
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    is_banned = db.Column(db.Boolean, nullable=False, default=False)
    ban_type = db.Column(db.String(32))  # None/disabled, 'temporary', 'permanent', 'download_only', 'upload_only', 'forum_only', 'tracker_only'
    banned_reason = db.Column(db.String(512))
    banned_until = db.Column(db.DateTime(timezone=True))
    warning_count = db.Column(db.Integer, nullable=False, default=0)

    # Auto-promotion tracking
    promotion_eligible = db.Column(db.Boolean, nullable=False, default=True)
    last_promotion_check_at = db.Column(db.DateTime(timezone=True))
    demotion_warning_count = db.Column(db.Integer, nullable=False, default=0)

    # Class-specific limits
    download_slots_used = db.Column(db.Integer, nullable=False, default=0)

    # Cumulative time tracking (seconds)
    total_seed_time_secs = db.Column(db.BigInteger, nullable=False, default=0)
    total_leech_time_secs = db.Column(db.BigInteger, nullable=False, default=0)
    forum_post_count = db.Column(db.Integer, nullable=False, default=0)

    # Preferences
    theme = db.Column(db.String(16), nullable=False, default='light')
    items_per_page = db.Column(db.Integer, nullable=False, default=25)
    notify_comment = db.Column(db.Boolean, nullable=False, default=True)
    notify_pm = db.Column(db.Boolean, nullable=False, default=True)
    notify_new_torrent = db.Column(db.Boolean, nullable=False, default=False)

    # Timestamps
    registered_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    last_active_at = db.Column(db.DateTime(timezone=True))
    last_ip = db.Column(db.String(45))
    last_announce_at = db.Column(db.DateTime(timezone=True))

    # Relationships
    torrents = db.relationship('Torrent', backref='uploader', lazy='dynamic',
                               foreign_keys='Torrent.uploader_id')
    comments = db.relationship('Comment', backref='author', lazy='dynamic',
                               foreign_keys='Comment.user_id')
    bookmarks = db.relationship('Bookmark', backref='user', lazy='dynamic')
    thanks = db.relationship('Thank', backref='user', lazy='dynamic')
    peers = db.relationship('Peer', backref='user', lazy='dynamic')
    snatches = db.relationship('Snatch', backref='user', lazy='dynamic')
    bonus_logs = db.relationship('SeedBonusLog', backref='user', lazy='dynamic')
    purchases = db.relationship('BonusPurchase', backref='user', lazy='dynamic')
    sent_messages = db.relationship('PrivateMessage', backref='sender', lazy='dynamic',
                                    foreign_keys='PrivateMessage.sender_id')
    received_messages = db.relationship('PrivateMessage', backref='receiver', lazy='dynamic',
                                        foreign_keys='PrivateMessage.receiver_id')
    hnr_violations = db.relationship('HnrViolation', backref='user', lazy='dynamic',
                                     foreign_keys='HnrViolation.user_id')
    forum_topics = db.relationship('ForumTopic', backref='author', lazy='dynamic')
    forum_posts = db.relationship('ForumPost', backref='author', lazy='dynamic')
    created_invites = db.relationship('Invite', backref='creator', lazy='dynamic',
                                      foreign_keys='Invite.creator_id')
    medals = db.relationship('UserMedal', backref='user', lazy='dynamic')

    @property
    def ratio(self):
        """Return upload/download ratio as a float."""
        if self.downloaded == 0:
            return float('inf') if self.uploaded > 0 else 0.0
        return round(self.uploaded / self.downloaded, 4)

    @property
    def real_ratio(self):
        """Return real ratio (actual bytes, ignoring freeleech)."""
        if self.real_downloaded == 0:
            return float('inf') if self.real_uploaded > 0 else 0.0
        return round(self.real_uploaded / self.real_downloaded, 4)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @staticmethod
    def generate_passkey():
        return secrets.token_hex(16)

    @classmethod
    def create_user(cls, username, email, password, role='User'):
        """Create a new user with generated passkey."""
        user = cls(
            username=username,
            email=email,
            passkey=cls.generate_passkey(),
            role=role,
        )
        user.set_password(password)
        return user

    def get_admin_permissions(self):
        """Return dict of admin permissions. Sysop implicitly has all."""
        import json
        if self.role == 'Sysop':
            from app.services.admin_permission_service import ADMIN_PERMISSIONS
            return {k: True for k in ADMIN_PERMISSIONS}
        if not self.admin_permissions:
            return {}
        try:
            return json.loads(self.admin_permissions)
        except (json.JSONDecodeError, TypeError):
            return {}

    def has_permission(self, permission_name):
        """Check if user has a specific admin permission. Sysop always True."""
        if self.role == 'Sysop':
            return True
        perms = self.get_admin_permissions()
        return perms.get(permission_name, False)

    def set_permission(self, permission_name, value):
        """Set a specific admin permission."""
        import json
        perms = self.get_admin_permissions()
        perms[permission_name] = bool(value)
        self.admin_permissions = json.dumps(perms, ensure_ascii=False)

    def set_all_permissions(self, value=True):
        """Grant or revoke all admin permissions."""
        import json
        from app.services.admin_permission_service import ADMIN_PERMISSIONS
        perms = {k: value for k in ADMIN_PERMISSIONS}
        self.admin_permissions = json.dumps(perms, ensure_ascii=False)

    def can_download(self):
        """Check if user can download based on ratio and status."""
        if self.is_banned:
            if self.ban_type in ('download_only', 'permanent', 'temporary'):
                return False
        if self.role in ('VIP', 'Moderator', 'Admin', 'Sysop'):
            return True
        if self.downloaded == 0:
            return True
        ratio = self.uploaded / self.downloaded if self.downloaded > 0 else float('inf')
        from config import Config
        return ratio >= Config.MIN_RATIO_TO_DOWNLOAD

    def can_announce(self):
        """Check if user can use tracker."""
        if not self.is_banned:
            return True
        if self.ban_type in ('tracker_only', 'permanent', 'temporary'):
            return False
        return True

    def can_post_forum(self):
        """Check if user can post in forums."""
        if not self.is_banned:
            return True
        if self.ban_type in ('forum_only', 'permanent', 'temporary'):
            return False
        return True

    def __repr__(self):
        return f'<User {self.username}>'


class Invite(db.Model):
    __tablename__ = 'invite'

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(64), unique=True, nullable=False, index=True)
    creator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False,
                           default=lambda: datetime.now(timezone.utc))
    used = db.Column(db.Boolean, nullable=False, default=False)
    used_by_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    used_at = db.Column(db.DateTime(timezone=True))
    expires_at = db.Column(db.DateTime(timezone=True))
    email = db.Column(db.String(128))
    note = db.Column(db.String(256))

    used_by = db.relationship('User', foreign_keys=[used_by_id])

    @staticmethod
    def generate_code():
        return secrets.token_hex(24)

    def is_expired(self):
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at

    def __repr__(self):
        return f'<Invite {self.code[:8]}...>'


class UserMedal(db.Model):
    __tablename__ = 'user_medal'

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), primary_key=True)
    medal_id = db.Column(db.Integer, db.ForeignKey('medal.id'), primary_key=True)
    awarded_at = db.Column(db.DateTime(timezone=True), nullable=False,
                           default=lambda: datetime.now(timezone.utc))
