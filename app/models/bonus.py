from datetime import datetime, timezone
from decimal import Decimal
from app.extensions import db


class SeedBonusRate(db.Model):
    __tablename__ = 'seed_bonus_rate'

    id = db.Column(db.Integer, primary_key=True)
    min_size_gb = db.Column(db.Numeric(10, 2), nullable=False)
    max_size_gb = db.Column(db.Numeric(10, 2))  # NULL = no upper bound
    points_per_hour = db.Column(db.Numeric(10, 4), nullable=False)
    multiplier = db.Column(db.Numeric(6, 4), nullable=False, default=Decimal('1.0'))
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    def matches_size(self, size_bytes):
        """Check if a torrent size falls in this bracket."""
        size_gb = float(size_bytes) / (1024 ** 3)
        min_ok = float(self.min_size_gb) <= size_gb
        max_ok = self.max_size_gb is None or size_gb <= float(self.max_size_gb)
        return min_ok and max_ok

    def __repr__(self):
        return f'<SeedBonusRate {self.min_size_gb}-{self.max_size_gb or "∞"}GB: {self.points_per_hour}/hr>'


class SeedBonusLog(db.Model):
    __tablename__ = 'seed_bonus_log'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    points_change = db.Column(db.Numeric(12, 2), nullable=False)
    reason = db.Column(db.String(32), nullable=False)
    related_torrent_id = db.Column(db.Integer)
    related_item_id = db.Column(db.Integer)
    description = db.Column(db.String(256))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False,
                           default=lambda: datetime.now(timezone.utc), index=True)

    __table_args__ = (
        db.Index('idx_bonus_log_user_time', 'user_id', 'created_at'),
    )

    def __repr__(self):
        return f'<SeedBonusLog User {self.user_id} {self.points_change} {self.reason}>'


class BonusShopItem(db.Model):
    __tablename__ = 'bonus_shop_item'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Numeric(12, 2), nullable=False)
    stock = db.Column(db.Integer)  # NULL = unlimited
    sold_count = db.Column(db.Integer, nullable=False, default=0)
    effect_type = db.Column(db.String(32), nullable=False)
    effect_value = db.Column(db.Text, nullable=False)
    icon = db.Column(db.String(64))
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    min_role = db.Column(db.String(16), nullable=False, default='User')
    max_purchases_per_user = db.Column(db.Integer)  # NULL = unlimited
    created_at = db.Column(db.DateTime(timezone=True), nullable=False,
                           default=lambda: datetime.now(timezone.utc))

    def is_in_stock(self):
        if self.stock is None:
            return True
        return self.sold_count < self.stock

    def __repr__(self):
        return f'<BonusShopItem {self.name} {self.price}pts>'


class BonusPurchase(db.Model):
    __tablename__ = 'bonus_purchase'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('bonus_shop_item.id'), nullable=False)
    price_paid = db.Column(db.Numeric(12, 2), nullable=False)
    used = db.Column(db.Boolean, nullable=False, default=False)
    used_at = db.Column(db.DateTime(timezone=True))
    purchased_at = db.Column(db.DateTime(timezone=True), nullable=False,
                             default=lambda: datetime.now(timezone.utc))

    item = db.relationship('BonusShopItem', backref='purchases')

    def __repr__(self):
        return f'<BonusPurchase User {self.user_id} Item {self.item_id}>'
