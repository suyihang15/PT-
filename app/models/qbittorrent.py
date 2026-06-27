from datetime import datetime, timezone
from app.extensions import db


class QBittorrentConfig(db.Model):
    """Per-user qBittorrent connection configuration."""
    __tablename__ = 'qbittorrent_config'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, unique=True)
    host = db.Column(db.String(256), nullable=False)
    port = db.Column(db.Integer, nullable=False, default=8080)
    username = db.Column(db.String(128), nullable=False)
    password = db.Column(db.String(256), nullable=False)  # Stored as plaintext (consider encryption in production)
    use_ssl = db.Column(db.Boolean, nullable=False, default=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    auto_report = db.Column(db.Boolean, nullable=False, default=True)  # Auto-report stats from QB
    last_sync_at = db.Column(db.DateTime(timezone=True))
    last_error = db.Column(db.String(512))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False,
                           default=lambda: datetime.now(timezone.utc))

    user = db.relationship('User', backref='qb_config')

    def __repr__(self):
        return f'<QBittorrentConfig User {self.user_id} {self.host}:{self.port}>'


class QBittorrentSyncLog(db.Model):
    """Log of qBittorrent stat sync events."""
    __tablename__ = 'qbittorrent_sync_log'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    torrent_hash = db.Column(db.String(40))
    torrent_name = db.Column(db.String(512))
    upload_bytes = db.Column(db.BigInteger, nullable=False, default=0)
    download_bytes = db.Column(db.BigInteger, nullable=False, default=0)
    status = db.Column(db.String(32))  # seeding, downloading, paused, completed, etc.
    sync_type = db.Column(db.String(32))  # 'report' = QB->site stats, 'bind' = seeding status update
    created_at = db.Column(db.DateTime(timezone=True), nullable=False,
                           default=lambda: datetime.now(timezone.utc), index=True)

    __table_args__ = (
        db.Index('idx_qb_sync_user_time', 'user_id', 'created_at'),
    )

    user = db.relationship('User', backref='qb_sync_logs')

    def __repr__(self):
        return f'<QBittorrentSyncLog User {self.user_id} hash={self.torrent_hash}>'
