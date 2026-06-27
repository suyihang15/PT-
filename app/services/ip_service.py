"""IP management service — event logging, multi-account detection, IP ban checks."""

from datetime import datetime, timezone
from flask import request
from app.extensions import db


def log_ip_event(user_id, ip, event_type, user_agent=None, port=None):
    """Record an IP event to IpLog table."""
    from app.models.admin import IpLog
    entry = IpLog(
        user_id=user_id,
        ip=ip,
        event_type=event_type,
        user_agent=user_agent,
        port=port,
    )
    db.session.add(entry)
    return entry


def is_ip_banned(ip):
    """Check if an IP matches any active IP ban (including CIDR ranges)."""
    from app.models.admin import IpBan
    import ipaddress

    all_bans = IpBan.query.filter_by(is_active=True).all()
    for ban in all_bans:
        # Check for expiration
        if ban.is_expired:
            ban.is_active = False
            continue
        try:
            if '/' in ban.ip_address:
                # CIDR range check
                network = ipaddress.ip_network(ban.ip_address, strict=False)
                if ipaddress.ip_address(ip) in network:
                    return True
            else:
                if ban.ip_address == ip:
                    return True
        except ValueError:
            # Invalid IP or CIDR in DB, fall back to string comparison
            if ban.ip_address == ip:
                return True
    return False


def detect_multi_accounts(min_shared_ips=1):
    """Find IP addresses used by multiple different users for login events.

    Returns list of dicts with ip, user_count, and user list.
    """
    from app.models.admin import IpLog
    from app.models.user import User
    from sqlalchemy import func

    suspicious = db.session.query(
        IpLog.ip,
        func.count(func.distinct(IpLog.user_id)).label('user_count'),
    ).filter(
        IpLog.event_type == 'login'
    ).group_by(
        IpLog.ip
    ).having(
        func.count(func.distinct(IpLog.user_id)) > min_shared_ips
    ).order_by(
        func.count(func.distinct(IpLog.user_id)).desc()
    ).limit(100).all()

    results = []
    for ip, count in suspicious:
        user_ids = db.session.query(
            func.distinct(IpLog.user_id)
        ).filter(
            IpLog.ip == ip,
            IpLog.event_type == 'login',
        ).all()
        ids = [uid[0] for uid in user_ids]
        users = User.query.filter(User.id.in_(ids)).all()
        results.append({
            'ip': ip,
            'user_count': count,
            'users': users,
        })
    return results


def get_user_ip_history(user_id, limit=100):
    """Get recent IP history for a user."""
    from app.models.admin import IpLog
    return IpLog.query.filter_by(user_id=user_id)\
        .order_by(IpLog.created_at.desc())\
        .limit(limit).all()


def is_ip_whitelisted(user_id, ip):
    """Check if an IP is whitelisted for a specific user."""
    from app.models.admin import IpWhitelist
    entry = IpWhitelist.query.filter_by(
        user_id=user_id,
        ip_address=ip,
        is_active=True,
    ).first()
    return entry is not None
