from datetime import datetime, timezone
from app.extensions import db


class Category(db.Model):
    __tablename__ = 'category'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False)
    slug = db.Column(db.String(64), unique=True, nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('category.id'))
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    icon = db.Column(db.String(64))
    min_role_view = db.Column(db.String(16), nullable=False, default='User')

    parent = db.relationship('Category', remote_side=[id], backref='children')
    torrents = db.relationship('Torrent', backref='category', lazy='dynamic')

    def __repr__(self):
        return f'<Category {self.name}>'


class Tag(db.Model):
    __tablename__ = 'tag'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False)
    slug = db.Column(db.String(64), unique=True, nullable=False)
    color = db.Column(db.String(7), nullable=False, default='#6c757d')
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    torrents = db.relationship('TorrentTag', backref='tag', lazy='dynamic')

    def __repr__(self):
        return f'<Tag {self.name}>'


class TorrentTag(db.Model):
    __tablename__ = 'torrent_tag'

    torrent_id = db.Column(db.Integer, db.ForeignKey('torrent.id', ondelete='CASCADE'), primary_key=True)
    tag_id = db.Column(db.Integer, db.ForeignKey('tag.id', ondelete='CASCADE'), primary_key=True)


class Torrent(db.Model):
    __tablename__ = 'torrent'

    id = db.Column(db.Integer, primary_key=True)
    info_hash = db.Column(db.String(40), unique=True, nullable=False, index=True)
    name = db.Column(db.String(512), nullable=False)
    description = db.Column(db.Text)
    description_html = db.Column(db.Text)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    uploader_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    # Torrent metadata
    size = db.Column(db.BigInteger, nullable=False)
    file_count = db.Column(db.Integer, nullable=False, default=1)
    piece_length = db.Column(db.Integer, nullable=False)
    piece_count = db.Column(db.Integer, nullable=False)
    created_at_torrent = db.Column(db.DateTime(timezone=True))
    created_by = db.Column(db.String(256))
    encoding = db.Column(db.String(32), nullable=False, default='UTF-8')
    is_private = db.Column(db.Boolean, nullable=False, default=True)

    # Seed/leech snapshot
    seeders = db.Column(db.Integer, nullable=False, default=0)
    leechers = db.Column(db.Integer, nullable=False, default=0)
    times_completed = db.Column(db.Integer, nullable=False, default=0)
    balance = db.Column(db.BigInteger, nullable=False, default=0)

    # Flags
    visible = db.Column(db.Boolean, nullable=False, default=True)
    banned = db.Column(db.Boolean, nullable=False, default=False)
    banned_reason = db.Column(db.String(512))
    anonymous = db.Column(db.Boolean, nullable=False, default=False)
    sticky_until = db.Column(db.DateTime(timezone=True))
    freeleech = db.Column(db.Boolean, nullable=False, default=False)
    freeleech_until = db.Column(db.DateTime(timezone=True))
    double_upload = db.Column(db.Boolean, nullable=False, default=False)
    double_upload_until = db.Column(db.DateTime(timezone=True))
    half_download = db.Column(db.Boolean, nullable=False, default=False)
    half_download_until = db.Column(db.DateTime(timezone=True))

    # Media metadata
    imdb_id = db.Column(db.String(16))
    douban_id = db.Column(db.String(16))
    tmdb_id = db.Column(db.String(16))
    quality = db.Column(db.String(32))
    medium = db.Column(db.String(32))
    codec = db.Column(db.String(32))
    audio_codec = db.Column(db.String(32))
    hdr = db.Column(db.String(16))
    scene_group = db.Column(db.String(128))
    season = db.Column(db.String(16))
    episode = db.Column(db.String(16))

    # Moderation
    moderation_note = db.Column(db.Text)
    sticky_set_by_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    freeleech_set_by_id = db.Column(db.Integer, db.ForeignKey('user.id'))

    # Counters
    comment_count = db.Column(db.Integer, nullable=False, default=0)
    bookmark_count = db.Column(db.Integer, nullable=False, default=0)
    thank_count = db.Column(db.Integer, nullable=False, default=0)
    view_count = db.Column(db.Integer, nullable=False, default=0)

    # Timestamps
    added_at = db.Column(db.DateTime(timezone=True), nullable=False,
                         default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True))
    last_checked_at = db.Column(db.DateTime(timezone=True))

    # Relationships
    files = db.relationship('File', backref='torrent', lazy='dynamic',
                            cascade='all, delete-orphan')
    comments = db.relationship('Comment', backref='torrent', lazy='dynamic',
                               cascade='all, delete-orphan')
    bookmarks = db.relationship('Bookmark', backref='torrent', lazy='dynamic',
                                cascade='all, delete-orphan')
    thanks = db.relationship('Thank', backref='torrent', lazy='dynamic',
                             cascade='all, delete-orphan')
    peers = db.relationship('Peer', backref='torrent', lazy='dynamic',
                            cascade='all, delete-orphan')
    snatches = db.relationship('Snatch', backref='torrent', lazy='dynamic')
    tags_rel = db.relationship('TorrentTag', backref='torrent', lazy='dynamic',
                               cascade='all, delete-orphan')

    @property
    def is_sticky(self):
        if self.sticky_until is None:
            return False
        return datetime.now(timezone.utc) < self.sticky_until

    @property
    def is_freeleech(self):
        if self.freeleech and self.freeleech_until is None:
            return True
        if self.freeleech and self.freeleech_until:
            return datetime.now(timezone.utc) < self.freeleech_until
        return False

    @property
    def is_double_upload(self):
        if self.double_upload and self.double_upload_until is None:
            return True
        if self.double_upload and self.double_upload_until:
            return datetime.now(timezone.utc) < self.double_upload_until
        return False

    @property
    def is_half_download(self):
        if self.half_download and self.half_download_until is None:
            return True
        if self.half_download and self.half_download_until:
            return datetime.now(timezone.utc) < self.half_download_until
        return False

    def storage_path(self):
        """Return the filesystem path for the .torrent file."""
        prefix = self.info_hash[:2].lower()
        return f'storage/torrents/{prefix}/{self.info_hash}.torrent'

    def __repr__(self):
        return f'<Torrent {self.name[:50]}>'


class File(db.Model):
    __tablename__ = 'file'

    id = db.Column(db.Integer, primary_key=True)
    torrent_id = db.Column(db.Integer, db.ForeignKey('torrent.id', ondelete='CASCADE'), nullable=False)
    path = db.Column(db.String(1024), nullable=False)
    size = db.Column(db.BigInteger, nullable=False)

    def __repr__(self):
        return f'<File {self.path}>'


class Comment(db.Model):
    __tablename__ = 'comment'

    id = db.Column(db.Integer, primary_key=True)
    torrent_id = db.Column(db.Integer, db.ForeignKey('torrent.id', ondelete='CASCADE'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    content_html = db.Column(db.Text, nullable=False)
    anonymous = db.Column(db.Boolean, nullable=False, default=False)
    upvotes = db.Column(db.Integer, nullable=False, default=0)
    downvotes = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False,
                           default=lambda: datetime.now(timezone.utc))
    edited_at = db.Column(db.DateTime(timezone=True))

    def __repr__(self):
        return f'<Comment {self.id} on Torrent {self.torrent_id}>'


class Bookmark(db.Model):
    __tablename__ = 'bookmark'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    torrent_id = db.Column(db.Integer, db.ForeignKey('torrent.id', ondelete='CASCADE'), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False,
                           default=lambda: datetime.now(timezone.utc))

    __table_args__ = (db.UniqueConstraint('user_id', 'torrent_id'),)

    def __repr__(self):
        return f'<Bookmark User {self.user_id} Torrent {self.torrent_id}>'


class Thank(db.Model):
    __tablename__ = 'thank'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    torrent_id = db.Column(db.Integer, db.ForeignKey('torrent.id', ondelete='CASCADE'), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False,
                           default=lambda: datetime.now(timezone.utc))

    __table_args__ = (db.UniqueConstraint('user_id', 'torrent_id'),)

    def __repr__(self):
        return f'<Thank User {self.user_id} Torrent {self.torrent_id}>'
