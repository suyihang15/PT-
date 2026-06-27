from datetime import datetime, timezone
from app.extensions import db


class Forum(db.Model):
    __tablename__ = 'forum'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    description = db.Column(db.String(512))
    slug = db.Column(db.String(64), unique=True, nullable=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    min_role_view = db.Column(db.String(16), nullable=False, default='User')
    min_role_post = db.Column(db.String(16), nullable=False, default='User')
    topic_count = db.Column(db.Integer, nullable=False, default=0)
    post_count = db.Column(db.Integer, nullable=False, default=0)

    topics = db.relationship('ForumTopic', backref='forum', lazy='dynamic')

    def __repr__(self):
        return f'<Forum {self.name}>'


class ForumTopic(db.Model):
    __tablename__ = 'forum_topic'

    id = db.Column(db.Integer, primary_key=True)
    forum_id = db.Column(db.Integer, db.ForeignKey('forum.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(256), nullable=False)
    is_locked = db.Column(db.Boolean, nullable=False, default=False)
    is_pinned = db.Column(db.Boolean, nullable=False, default=False)
    view_count = db.Column(db.Integer, nullable=False, default=0)
    reply_count = db.Column(db.Integer, nullable=False, default=0)
    first_post_id = db.Column(db.Integer)
    last_post_id = db.Column(db.Integer)
    last_post_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False,
                           default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True))

    posts = db.relationship('ForumPost', backref='topic', lazy='dynamic',
                            order_by='ForumPost.created_at')

    def __repr__(self):
        return f'<ForumTopic {self.title[:40]}>'


class ForumPost(db.Model):
    __tablename__ = 'forum_post'

    id = db.Column(db.Integer, primary_key=True)
    topic_id = db.Column(db.Integer, db.ForeignKey('forum_topic.id', ondelete='CASCADE'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    content_html = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False,
                           default=lambda: datetime.now(timezone.utc))
    edited_at = db.Column(db.DateTime(timezone=True))

    def __repr__(self):
        return f'<ForumPost {self.id} in Topic {self.topic_id}>'
