"""Hit & Run detection and resolution logic."""

from datetime import datetime, timezone, timedelta
from app.extensions import db
from app.models.tracker import Snatch, HnrViolation
from app.models.message import PrivateMessage


def check_for_hnr_violations(min_seed_hours=72, min_ratio=1.0, grace_hours=168):
    """Scan for new H&R violations."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=grace_hours)
    violations_found = 0

    snatches = Snatch.query.filter(
        Snatch.finished == True,
        Snatch.hit_and_run == False,
        Snatch.downloaded > 0,
    ).all()

    for snatch in snatches:
        if snatch.completed_at and snatch.completed_at >= cutoff:
            continue  # Still in grace period

        seed_hours = snatch.seed_time / 3600.0
        ratio = snatch.uploaded / snatch.downloaded if snatch.downloaded > 0 else 0

        if seed_hours < min_seed_hours and ratio < min_ratio:
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
                violations_found += 1

    if violations_found > 0:
        db.session.commit()

    return violations_found


def check_hnr_resolutions(min_seed_hours=72, min_ratio=1.0):
    """Check if any existing violations have been resolved by re-seeding."""
    violations = HnrViolation.query.filter_by(resolved=False).all()
    resolved_count = 0

    for violation in violations:
        snatch = violation.snatch
        if not snatch:
            continue

        # Check if user has re-seeded enough
        seed_hours = snatch.seed_time / 3600.0
        ratio = snatch.uploaded / snatch.downloaded if snatch.downloaded > 0 else 0

        if seed_hours >= min_seed_hours or ratio >= min_ratio:
            violation.resolved = True
            violation.resolved_at = datetime.now(timezone.utc)
            violation.resolved_by_id = None  # Auto-resolved
            snatch.hnr_resolved = True
            resolved_count += 1

    if resolved_count > 0:
        db.session.commit()

    return resolved_count
