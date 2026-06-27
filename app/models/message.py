from datetime import datetime, timezone
from app.extensions import db


class PrivateMessage(db.Model):
    __tablename__ = 'private_message'

    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    subject = db.Column(db.String(256), nullable=False)
    content = db.Column(db.Text, nullable=False)
    content_html = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, nullable=False, default=False)
    read_at = db.Column(db.DateTime(timezone=True))
    sender_deleted = db.Column(db.Boolean, nullable=False, default=False)
    receiver_deleted = db.Column(db.Boolean, nullable=False, default=False)
    sent_at = db.Column(db.DateTime(timezone=True), nullable=False,
                        default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        db.Index('idx_pm_receiver', 'receiver_id', 'is_read', 'receiver_deleted'),
        db.Index('idx_pm_sender', 'sender_id', 'sender_deleted'),
    )

    def __repr__(self):
        return f'<PM {self.id}: {self.subject[:30]}>'
