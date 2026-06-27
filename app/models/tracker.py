from datetime import datetime, timezone
from app.extensions import db


class Peer(db.Model):
    __tablename__ = 'peer'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    torrent_id = db.Column(db.Integer, db.ForeignKey('torrent.id', ondelete='CASCADE'), nullable=False, index=True)
    info_hash = db.Column(db.String(40), nullable=False, index=True)
    peer_id = db.Column(db.String(40))
    ip = db.Column(db.String(45), nullable=False)
    port = db.Column(db.Integer, nullable=False)
    uploaded = db.Column(db.BigInteger, nullable=False, default=0)
    downloaded = db.Column(db.BigInteger, nullable=False, default=0)
    left = db.Column(db.BigInteger, nullable=False, default=0)
    seeder = db.Column(db.Boolean, nullable=False, default=False)
    user_agent = db.Column(db.String(256))
    key = db.Column(db.String(64))
    started_at = db.Column(db.DateTime(timezone=True), nullable=False,
                           default=lambda: datetime.now(timezone.utc))
    last_announce_at = db.Column(db.DateTime(timezone=True), nullable=False,
                                 default=lambda: datetime.now(timezone.utc), index=True)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'torrent_id', 'peer_id'),
    )

    def is_stale(self, expire_seconds=1800):
        """Check if peer hasn't announced within expiration window."""
        from datetime import timedelta
        if self.last_announce_at is None:
            return True
        return datetime.now(timezone.utc) - self.last_announce_at > timedelta(seconds=expire_seconds)

    def __repr__(self):
        return f'<Peer {self.ip}:{self.port} on Torrent {self.torrent_id}>'


class Snatch(db.Model):
    __tablename__ = 'snatch'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    torrent_id = db.Column(db.Integer, db.ForeignKey('torrent.id'), nullable=False, index=True)
    uploaded = db.Column(db.BigInteger, nullable=False, default=0)
    downloaded = db.Column(db.BigInteger, nullable=False, default=0)
    left = db.Column(db.BigInteger, nullable=False, default=0)
    seed_time = db.Column(db.Integer, nullable=False, default=0)  # seconds
    leech_time = db.Column(db.Integer, nullable=False, default=0)  # seconds
    seed_bonus_earned = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    finished = db.Column(db.Boolean, nullable=False, default=False)
    hit_and_run = db.Column(db.Boolean, nullable=False, default=False)
    hnr_resolved = db.Column(db.Boolean, nullable=False, default=False)
    completed_at = db.Column(db.DateTime(timezone=True))
    started_at = db.Column(db.DateTime(timezone=True), nullable=False,
                           default=lambda: datetime.now(timezone.utc))
    last_action_at = db.Column(db.DateTime(timezone=True), nullable=False,
                               default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        db.UniqueConstraint('user_id', 'torrent_id'),
    )

    @property
    def ratio(self):
        if self.downloaded == 0:
            return float('inf') if self.uploaded > 0 else 0.0
        return round(self.uploaded / self.downloaded, 4)

    def __repr__(self):
        return f'<Snatch User {self.user_id} Torrent {self.torrent_id}>'


class HnrViolation(db.Model):
    __tablename__ = 'hnr_violation'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    torrent_id = db.Column(db.Integer, db.ForeignKey('torrent.id'), nullable=False)
    snatch_id = db.Column(db.Integer, db.ForeignKey('snatch.id'), nullable=False)
    seed_time_secs = db.Column(db.Integer, nullable=False)
    ratio_achieved = db.Column(db.Numeric(8, 4), nullable=False)
    warning_sent = db.Column(db.Boolean, nullable=False, default=False)
    warning_sent_at = db.Column(db.DateTime(timezone=True))
    resolved = db.Column(db.Boolean, nullable=False, default=False)
    resolved_at = db.Column(db.DateTime(timezone=True))
    resolved_by_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False,
                           default=lambda: datetime.now(timezone.utc))

    snatch = db.relationship('Snatch', backref='violations')
    resolved_by = db.relationship('User', foreign_keys=[resolved_by_id])

    def __repr__(self):
        return f'<HnrViolation User {self.user_id} Torrent {self.torrent_id}>'
