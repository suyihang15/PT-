from datetime import datetime, timezone
from app.extensions import db


class BanLog(db.Model):
    """Records every ban/unban action for audit trail."""
    __tablename__ = 'ban_log'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    operator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    ban_type = db.Column(db.String(32), nullable=False)  # temporary, permanent, download_only, upload_only, forum_only, tracker_only, ip_ban
    reason = db.Column(db.String(512), nullable=False)
    duration_days = db.Column(db.Integer)  # NULL = permanent
    banned_until = db.Column(db.DateTime(timezone=True))
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    ip_banned = db.Column(db.String(45))  # Specific IP banned alongside user
    ip_range_banned = db.Column(db.String(45))  # CIDR range
    unban_reason = db.Column(db.String(512))
    unbanned_by_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    unbanned_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False,
                           default=lambda: datetime.now(timezone.utc))

    user = db.relationship('User', foreign_keys=[user_id], backref='ban_logs')
    operator = db.relationship('User', foreign_keys=[operator_id])
    unbanned_by = db.relationship('User', foreign_keys=[unbanned_by_id])

    @property
    def is_expired(self):
        if self.ban_type != 'temporary' or self.banned_until is None:
            return False
        return datetime.now(timezone.utc) > self.banned_until

    def __repr__(self):
        return f'<BanLog User {self.user_id} type={self.ban_type}>'


class IpLog(db.Model):
    """Records every IP event for multi-account detection and security."""
    __tablename__ = 'ip_log'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    ip = db.Column(db.String(45), nullable=False, index=True)
    event_type = db.Column(db.String(32), nullable=False)  # login, announce, register, api, scrape
    user_agent = db.Column(db.String(512))
    port = db.Column(db.Integer)
    geo_country = db.Column(db.String(64))
    geo_city = db.Column(db.String(128))
    geo_isp = db.Column(db.String(128))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False,
                           default=lambda: datetime.now(timezone.utc), index=True)

    __table_args__ = (
        db.Index('idx_ip_log_ip_time', 'ip', 'created_at'),
        db.Index('idx_ip_log_user_time', 'user_id', 'created_at'),
    )

    user = db.relationship('User', backref='ip_logs')

    def __repr__(self):
        return f'<IpLog User {self.user_id} IP={self.ip} event={self.event_type}>'


class IpBan(db.Model):
    """IP / CIDR range ban list."""
    __tablename__ = 'ip_ban'

    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(45), nullable=False)  # Single IP or CIDR like 192.168.1.0/24
    reason = db.Column(db.String(512), nullable=False)
    operator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False,
                           default=lambda: datetime.now(timezone.utc))
    expires_at = db.Column(db.DateTime(timezone=True))  # NULL = permanent

    operator = db.relationship('User', backref='ip_bans_issued')

    @property
    def is_expired(self):
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at

    def __repr__(self):
        return f'<IpBan {self.ip_address}>'


class IpWhitelist(db.Model):
    """IP whitelist for staff users."""
    __tablename__ = 'ip_whitelist'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    ip_address = db.Column(db.String(45), nullable=False)
    description = db.Column(db.String(256))
    added_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False,
                           default=lambda: datetime.now(timezone.utc))

    user = db.relationship('User', foreign_keys=[user_id], backref='ip_whitelist_entries')
    added_by = db.relationship('User', foreign_keys=[added_by_id])

    def __repr__(self):
        return f'<IpWhitelist {self.ip_address} for User {self.user_id}>'


class UserClass(db.Model):
    """Defines promotion/demotion criteria and privileges for each user class."""
    __tablename__ = 'user_class'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(32), nullable=False, unique=True)   # Maps to User.role: User, PowerUser, VIP, etc.
    display_name = db.Column(db.String(64), nullable=False)          # Chinese display name
    level = db.Column(db.Integer, nullable=False, unique=True)       # Numeric level for ordering

    # Promotion criteria (ALL must be met to promote INTO this class)
    min_upload_gb = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    min_ratio = db.Column(db.Numeric(8, 4), nullable=False, default=0)
    min_seed_hours = db.Column(db.Integer, nullable=False, default=0)
    min_account_age_days = db.Column(db.Integer, nullable=False, default=0)
    min_forum_posts = db.Column(db.Integer, nullable=False, default=0)
    min_snatches = db.Column(db.Integer, nullable=False, default=0)
    min_seed_bonus = db.Column(db.Numeric(12, 2), nullable=False, default=0)

    # Demotion criteria (if ANY fails, demote)
    keep_min_ratio = db.Column(db.Numeric(8, 4), nullable=False, default=0)
    keep_min_seed_hours = db.Column(db.Integer, nullable=False, default=0)

    # Privileges this class grants
    invite_tokens_per_month = db.Column(db.Integer, nullable=False, default=0)
    pm_inbox_size = db.Column(db.Integer, nullable=False, default=100)
    bonus_multiplier = db.Column(db.Numeric(6, 4), nullable=False, default=1.0)
    download_slots = db.Column(db.Integer, nullable=False, default=3)
    wait_time_seconds = db.Column(db.Integer, nullable=False, default=0)  # Download wait time
    can_view_peers = db.Column(db.Boolean, nullable=False, default=False)
    can_use_freeleech_tokens = db.Column(db.Boolean, nullable=False, default=False)
    can_view_nfo = db.Column(db.Boolean, nullable=False, default=False)
    can_upload_subtitles = db.Column(db.Boolean, nullable=False, default=False)
    exempt_from_hnr = db.Column(db.Boolean, nullable=False, default=False)
    exempt_from_wait_time = db.Column(db.Boolean, nullable=False, default=False)

    # Display
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    color = db.Column(db.String(7), nullable=False, default='#6c757d')  # Badge hex color
    icon = db.Column(db.String(64))  # Bootstrap icon name
    badge_text = db.Column(db.String(32))  # Short badge label

    def __repr__(self):
        return f'<UserClass {self.name} (L{self.level})>'


class PromotionLog(db.Model):
    """Audit trail for promotion/demotion events."""
    __tablename__ = 'promotion_log'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    from_class = db.Column(db.String(32), nullable=False)
    to_class = db.Column(db.String(32), nullable=False)
    triggered_by = db.Column(db.String(32), nullable=False)  # 'auto' or 'manual'
    operator_id = db.Column(db.Integer, db.ForeignKey('user.id'))  # NULL if auto
    reason = db.Column(db.String(512))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False,
                           default=lambda: datetime.now(timezone.utc))

    user = db.relationship('User', foreign_keys=[user_id], backref='promotion_logs')
    operator = db.relationship('User', foreign_keys=[operator_id])

    def __repr__(self):
        return f'<PromotionLog User {self.user_id}: {self.from_class} -> {self.to_class}>'
