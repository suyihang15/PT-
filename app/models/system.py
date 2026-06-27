from datetime import datetime, timezone
from app.extensions import db


class SiteSetting(db.Model):
    __tablename__ = 'site_setting'

    key = db.Column(db.String(64), primary_key=True)
    value = db.Column(db.Text)
    value_type = db.Column(db.String(16), nullable=False, default='string')
    description = db.Column(db.String(256))
    updated_at = db.Column(db.DateTime(timezone=True))

    def get_value(self):
        """Convert the stored string to the proper type."""
        import json
        if self.value_type == 'int':
            return int(self.value) if self.value else 0
        elif self.value_type == 'bool':
            return self.value.lower() in ('true', '1', 'yes') if self.value else False
        elif self.value_type == 'json':
            return json.loads(self.value) if self.value else {}
        return self.value or ''

    def set_value(self, val):
        """Convert to string for storage."""
        import json
        if self.value_type == 'json':
            self.value = json.dumps(val, ensure_ascii=False)
        else:
            self.value = str(val)

    @classmethod
    def get(cls, key, default=None):
        """Get a setting value by key."""
        setting = db.session.get(cls, key)
        if setting is None:
            return default
        return setting.get_value()

    @classmethod
    def set(cls, key, value, value_type='string', description=None):
        """Set a setting value. Creates if not exists."""
        setting = db.session.get(cls, key)
        if setting is None:
            setting = cls(key=key, value_type=value_type, description=description)
            db.session.add(setting)
        setting.set_value(value)
        setting.updated_at = datetime.now(timezone.utc)
        if description:
            setting.description = description
        return setting

    def __repr__(self):
        return f'<SiteSetting {self.key}>'


class News(db.Model):
    __tablename__ = 'news'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(256), nullable=False)
    content = db.Column(db.Text, nullable=False)
    content_html = db.Column(db.Text, nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    is_pinned = db.Column(db.Boolean, nullable=False, default=False)
    is_published = db.Column(db.Boolean, nullable=False, default=True)
    view_count = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False,
                           default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True))

    author = db.relationship('User', backref='news_articles')

    def __repr__(self):
        return f'<News {self.title[:40]}>'


class Report(db.Model):
    __tablename__ = 'report'

    id = db.Column(db.Integer, primary_key=True)
    reporter_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    torrent_id = db.Column(db.Integer, db.ForeignKey('torrent.id', ondelete='SET NULL'))
    comment_id = db.Column(db.Integer, db.ForeignKey('comment.id', ondelete='SET NULL'))
    pm_id = db.Column(db.Integer, db.ForeignKey('private_message.id', ondelete='SET NULL'))
    reason = db.Column(db.String(64), nullable=False)
    details = db.Column(db.Text)
    resolved = db.Column(db.Boolean, nullable=False, default=False)
    resolved_by_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    resolution_note = db.Column(db.Text)
    resolved_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False,
                           default=lambda: datetime.now(timezone.utc))

    reporter = db.relationship('User', foreign_keys=[reporter_id], backref='filed_reports')
    resolved_by = db.relationship('User', foreign_keys=[resolved_by_id], backref='resolved_reports')
    torrent = db.relationship('Torrent', backref='reports')
    comment = db.relationship('Comment', backref='reports')
    pm = db.relationship('PrivateMessage', backref='reports')

    @property
    def target_description(self):
        if self.torrent_id:
            return f'种子: {self.torrent.name if self.torrent else "已删除"}'
        if self.comment_id:
            return f'评论: #{self.comment_id}'
        if self.pm_id:
            return f'私信: #{self.pm_id}'
        return '未知'

    def __repr__(self):
        return f'<Report #{self.id} {self.reason}>'


class Log(db.Model):
    __tablename__ = 'log'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), index=True)
    action = db.Column(db.String(64), nullable=False)
    target_type = db.Column(db.String(32))
    target_id = db.Column(db.Integer)
    details = db.Column(db.Text)
    ip = db.Column(db.String(45))
    severity = db.Column(db.String(16), nullable=False, default='info')  # info, warning, danger, success
    related_user_id = db.Column(db.Integer)  # Target user (if action was on a user)
    old_value = db.Column(db.Text)  # Previous value for edit actions
    new_value = db.Column(db.Text)  # New value for edit actions
    created_at = db.Column(db.DateTime(timezone=True), nullable=False,
                           default=lambda: datetime.now(timezone.utc), index=True)

    actor = db.relationship('User', backref='activity_logs')

    def __repr__(self):
        return f'<Log {self.action} by User {self.user_id}>'


class Warning(db.Model):
    """User warning records."""
    __tablename__ = 'warning'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    operator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    reason = db.Column(db.String(512), nullable=False)
    points_deducted = db.Column(db.Numeric(12, 2))
    auto_pm_sent = db.Column(db.Boolean, nullable=False, default=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False,
                           default=lambda: datetime.now(timezone.utc))
    expires_at = db.Column(db.DateTime(timezone=True))

    user = db.relationship('User', foreign_keys=[user_id], backref='warnings')
    operator = db.relationship('User', foreign_keys=[operator_id])

    def __repr__(self):
        return f'<Warning User {self.user_id} reason={self.reason[:30]}>'


class Announcement(db.Model):
    """System-wide announcements / notifications."""
    __tablename__ = 'announcement'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(256), nullable=False)
    content = db.Column(db.Text, nullable=False)
    content_html = db.Column(db.Text, nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    target_role = db.Column(db.String(16))  # NULL = all users, else specific role
    is_pinned = db.Column(db.Boolean, nullable=False, default=False)
    is_published = db.Column(db.Boolean, nullable=False, default=True)
    show_until = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False,
                           default=lambda: datetime.now(timezone.utc))

    author = db.relationship('User', backref='announcements')

    @property
    def is_visible(self):
        if not self.is_published:
            return False
        if self.show_until and datetime.now(timezone.utc) > self.show_until:
            return False
        return True

    def __repr__(self):
        return f'<Announcement {self.title[:40]}>'


class Medal(db.Model):
    __tablename__ = 'medal'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    description = db.Column(db.String(512))
    icon = db.Column(db.String(64))
    condition_type = db.Column(db.String(32), nullable=False)
    condition_value = db.Column(db.Numeric(12, 2), nullable=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    users = db.relationship('UserMedal', backref='medal', lazy='dynamic')

    def __repr__(self):
        return f'<Medal {self.name}>'
