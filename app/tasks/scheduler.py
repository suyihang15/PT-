"""Scheduled background tasks using APScheduler."""

import logging
from datetime import datetime, timezone, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from flask import current_app

logger = logging.getLogger(__name__)
scheduler = BackgroundScheduler()


def init_scheduler(app):
    """Initialize and start the background scheduler."""
    if scheduler.running:
        return

    scheduler.add_job(
        func=lambda: peer_cleanup(app),
        trigger='interval',
        minutes=10,
        id='peer_cleanup',
        name='Clean up stale peers',
    )

    scheduler.add_job(
        func=lambda: bonus_reward(app),
        trigger='interval',
        minutes=60,
        id='bonus_reward',
        name='Credit seed bonus points',
    )

    scheduler.add_job(
        func=lambda: daily_reset(app),
        trigger='cron',
        hour=0,
        minute=5,
        id='daily_reset',
        name='Reset daily counters',
    )

    scheduler.add_job(
        func=lambda: hnr_scan(app),
        trigger='interval',
        hours=6,
        id='hnr_scan',
        name='H&R violation scan',
    )

    scheduler.add_job(
        func=lambda: auto_unban_check(app),
        trigger='interval',
        hours=1,
        id='auto_unban',
        name='Auto-unban expired bans',
    )

    scheduler.add_job(
        func=lambda: auto_promotion_scan(app),
        trigger='interval',
        hours=3,
        id='auto_promotion',
        name='Auto promotion/demotion check',
    )

    try:
        import requests
        scheduler.add_job(
            func=lambda: qb_sync_all(app),
            trigger='interval',
            minutes=30,
            id='qb_sync',
            name='QBittorrent stat sync',
        )
    except ImportError:
        pass

    scheduler.start()
    logger.info("Scheduler started with all jobs")


def peer_cleanup(app):
    """Remove peers that haven't announced in 30 minutes and update torrent counts."""
    with app.app_context():
        from app.extensions import db
        from app.models.tracker import Peer
        from app.models.torrent import Torrent
        from app.models.user import User

        cutoff = datetime.now(timezone.utc) - timedelta(seconds=app.config.get('PEER_EXPIRE_SECONDS', 1800))

        stale_peers = Peer.query.filter(Peer.last_announce_at < cutoff).all()

        if not stale_peers:
            return

        # Group by torrent for counter updates
        torrent_updates = {}

        for peer in stale_peers:
            # Update user counts
            user = peer.user
            if user:
                if peer.seeder:
                    user.seeding_count = max(0, user.seeding_count - 1)
                else:
                    user.leeching_count = max(0, user.leeching_count - 1)

            # Track torrent updates
            torrent_updates.setdefault(peer.torrent_id, {'seeders': 0, 'leechers': 0})
            if peer.seeder:
                torrent_updates[peer.torrent_id]['seeders'] += 1
            else:
                torrent_updates[peer.torrent_id]['leechers'] += 1

            db.session.delete(peer)

        # Update torrent counts
        for torrent_id, delta in torrent_updates.items():
            torrent = db.session.get(Torrent, torrent_id)
            if torrent:
                torrent.seeders = max(0, torrent.seeders - delta['seeders'])
                torrent.leechers = max(0, torrent.leechers - delta['leechers'])

        db.session.commit()
        logger.info(f"Peer cleanup: removed {len(stale_peers)} stale peers")


def bonus_reward(app):
    """Calculate and credit seed bonus points for active seeders."""
    with app.app_context():
        from app.extensions import db
        from app.models.tracker import Peer
        from app.models.torrent import Torrent
        from app.models.bonus import SeedBonusRate, SeedBonusLog
        from app.models.user import User
        from decimal import Decimal

        cutoff = datetime.now(timezone.utc) - timedelta(minutes=30)
        active_peers = Peer.query.filter(
            Peer.seeder == True,
            Peer.last_announce_at >= cutoff,
        ).all()

        rates = SeedBonusRate.query.order_by(SeedBonusRate.sort_order).all()
        if not rates:
            rates = [SeedBonusRate(min_size_gb=Decimal('0'), max_size_gb=None,
                                   points_per_hour=Decimal('1.0'), multiplier=Decimal('1.0'))]

        count = 0
        for peer in active_peers:
            user = peer.user
            torrent = peer.torrent

            if not user or not torrent:
                continue

            # Find matching rate bracket
            rate = None
            for r in rates:
                if r.matches_size(torrent.size):
                    rate = r
                    break

            if rate is None:
                rate = rates[-1]

            points = float(rate.points_per_hour) * float(rate.multiplier)

            user.seed_bonus = (Decimal(str(user.seed_bonus)) + Decimal(str(points)))

            log_entry = SeedBonusLog(
                user_id=user.id,
                points_change=Decimal(str(points)),
                reason='seeding_reward',
                related_torrent_id=torrent.id,
                description=f'做种积分: {torrent.name[:50]}',
            )
            db.session.add(log_entry)
            count += 1

        db.session.commit()
        logger.info(f"Bonus reward: credited {count} active seeders")


def daily_reset(app):
    """Reset daily upload/download counters."""
    with app.app_context():
        from app.extensions import db
        from app.models.user import User

        db.session.execute(
            db.update(User).values(uploaded_today=0, downloaded_today=0)
        )
        db.session.commit()
        logger.info("Daily reset: cleared today's upload/download counters")


def hnr_scan(app):
    """Scan for Hit & Run violations."""
    with app.app_context():
        from app.extensions import db
        from app.models.tracker import Snatch, HnrViolation
        from app.models.user import User
        from datetime import datetime, timezone, timedelta

        min_seed_hours = app.config.get('HNR_MIN_SEED_HOURS', 72)
        min_ratio = app.config.get('HNR_MIN_RATIO', 1.0)
        grace_hours = app.config.get('HNR_GRACE_HOURS', 168)

        cutoff = datetime.now(timezone.utc) - timedelta(hours=grace_hours)

        # Find snatches that are finished but not yet checked for H&R
        snatches = Snatch.query.filter(
            Snatch.finished == True,
            Snatch.hit_and_run == False,
            Snatch.leech_time > 0,
        ).all()

        violations = 0
        for snatch in snatches:
            if snatch.completed_at and snatch.completed_at < cutoff:
                seed_hours = snatch.seed_time / 3600.0
                ratio = snatch.ratio

                if seed_hours < min_seed_hours and ratio < min_ratio:
                    # Check if already has a violation
                    existing = HnrViolation.query.filter_by(
                        user_id=snatch.user_id,
                        torrent_id=snatch.torrent_id,
                        resolved=False,
                    ).first()

                    if not existing:
                        violation = HnrViolation(
                            user_id=snatch.user_id,
                            torrent_id=snatch.torrent_id,
                            snatch_id=snatch.id,
                            seed_time_secs=snatch.seed_time,
                            ratio_achieved=ratio,
                        )
                        db.session.add(violation)
                        snatch.hit_and_run = True
                        violations += 1

        db.session.commit()
        logger.info(f"H&R scan: found {violations} new violations")


def auto_unban_check(app):
    """Auto-unban users whose temporary bans have expired."""
    with app.app_context():
        from app.services.ban_service import auto_unban_check as run_unban
        count = run_unban()
        if count:
            logger.info(f"Auto-unban: {count} users unbanned")


def auto_promotion_scan(app):
    """Auto promotion/demotion check for all eligible users."""
    with app.app_context():
        from app.services.promotion_service import auto_promotion_scan as run_promo
        promoted, demoted = run_promo()
        if promoted or demoted:
            logger.info(f"Auto-promotion: {promoted} promoted, {demoted} demoted")


def qb_sync_all(app):
    """Sync QB stats for all users with active QB configs."""
    with app.app_context():
        try:
            from app.services.qbittorrent_service import qb_sync_all_users
            ok, fail = qb_sync_all_users()
            if ok or fail:
                logger.info(f"QB sync: {ok} success, {fail} failed")
        except Exception as e:
            logger.error(f"QB sync error: {e}")


def seed_time_accumulate(app):
    """Accumulate seed/leech time for all active peers."""
    with app.app_context():
        from app.extensions import db
        from app.models.tracker import Peer
        from app.models.user import User
        from datetime import datetime, timezone, timedelta

        cutoff = datetime.now(timezone.utc) - timedelta(minutes=15)
        active_peers = Peer.query.filter(Peer.last_announce_at >= cutoff).all()

        for peer in active_peers:
            user = peer.user
            if not user:
                continue
            # Approximate: each minute in announce window = 60 seconds
            time_diff = (datetime.now(timezone.utc) - peer.last_announce_at).total_seconds()
            if peer.seeder:
                user.total_seed_time_secs = (user.total_seed_time_secs or 0) + int(time_diff)
            else:
                user.total_leech_time_secs = (user.total_leech_time_secs or 0) + int(time_diff)

        db.session.commit()
