"""Seed bonus point calculation logic."""

from datetime import datetime, timezone, timedelta
from decimal import Decimal
from app.extensions import db
from app.models.tracker import Peer
from app.models.bonus import SeedBonusRate, SeedBonusLog


def calculate_bonus_for_user(user):
    """Calculate seed bonus points for a single user's active seeds."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=30)
    active_peers = Peer.query.filter(
        Peer.user_id == user.id,
        Peer.seeder == True,
        Peer.last_announce_at >= cutoff,
    ).all()

    if not active_peers:
        return Decimal('0')

    rates = SeedBonusRate.query.order_by(SeedBonusRate.sort_order).all()
    if not rates:
        rates = [SeedBonusRate(
            min_size_gb=Decimal('0'),
            max_size_gb=None,
            points_per_hour=Decimal('1.0'),
            multiplier=Decimal('1.0'),
        )]

    total = Decimal('0')
    for peer in active_peers:
        torrent = peer.torrent
        if not torrent:
            continue

        # Find matching rate bracket
        rate = None
        for r in rates:
            if r.matches_size(torrent.size):
                rate = r
                break
        if rate is None:
            rate = rates[-1]

        points = Decimal(str(rate.points_per_hour)) * Decimal(str(rate.multiplier))
        total += points

    return total


def get_user_earning_rate(user):
    """Get the hourly earning rate for a user."""
    return calculate_bonus_for_user(user)
