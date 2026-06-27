"""Comprehensive ban system — types, durations, auto-unban, audit trail."""

from datetime import datetime, timezone, timedelta
from app.extensions import db

BAN_TYPES = {
    'temporary': '临时封禁',
    'permanent': '永久封禁',
    'download_only': '禁止下载',
    'upload_only': '禁止上传',
    'forum_only': '禁止发帖',
    'tracker_only': '禁止Tracker',
}

BAN_DURATION_PRESETS = {
    1: '1 天',
    3: '3 天',
    7: '7 天',
    30: '30 天',
    90: '90 天',
    365: '365 天',
    -1: '永久',
}

BAN_REASON_TEMPLATES = [
    '分享率过低且长期不改善',
    '作弊/使用违规客户端',
    '注册多个账号',
    'H&R 违规累计超出限制',
    '发布违规内容',
    '违规交易/买卖账号',
    '使用代理/VPN规避IP检测',
    '其他违规行为',
]


def ban_user(user, operator, ban_type='temporary', reason='', duration_days=None, ban_ip=False):
    """Apply a ban with full audit trail.

    Args:
        user: User model instance
        operator: User model instance (admin performing the ban)
        ban_type: One of BAN_TYPES keys
        reason: Ban reason text
        duration_days: Integer days for temporary bans (None = permanent)
        ban_ip: If True, also ban the user's most recent IPs
    """
    from app.models.admin import BanLog, IpBan
    from app.services.ip_service import log_ip_event
    from app.models.message import PrivateMessage

    user.is_banned = True
    user.ban_type = ban_type
    user.banned_reason = reason

    if ban_type == 'temporary' and duration_days and duration_days > 0:
        user.banned_until = datetime.now(timezone.utc) + timedelta(days=duration_days)
    else:
        user.banned_until = None

    # Create BanLog
    ban_log = BanLog(
        user_id=user.id,
        operator_id=operator.id,
        ban_type=ban_type,
        reason=reason,
        duration_days=duration_days if ban_type == 'temporary' else None,
        banned_until=user.banned_until,
    )
    db.session.add(ban_log)

    # Optionally ban user's recent IPs
    if ban_ip:
        from app.models.admin import IpLog as IpLogModel
        recent_ips = db.session.query(IpLogModel.ip).filter(
            IpLogModel.user_id == user.id,
            IpLogModel.event_type == 'login',
        ).distinct().limit(5).all()
        for (ip,) in recent_ips:
            existing = IpBan.query.filter_by(ip_address=ip, is_active=True).first()
            if not existing:
                db.session.add(IpBan(
                    ip_address=ip,
                    reason=f'用户 {user.username} 被封禁，连带IP封禁: {reason}',
                    operator_id=operator.id,
                ))

    # Send PM notification to user
    pm = PrivateMessage(
        sender_id=operator.id,
        receiver_id=user.id,
        subject='账号封禁通知',
        content=f'您的账号已被封禁。\n\n封禁类型: {BAN_TYPES.get(ban_type, ban_type)}\n理由: {reason}\n'
                f'{"解封时间: " + user.banned_until.strftime("%Y-%m-%d %H:%M") if user.banned_until else "永久封禁"}'
                f'\n\n如有疑问，请联系管理员。',
        content_html=f'<p>您的账号已被封禁。</p><p><strong>封禁类型:</strong> {BAN_TYPES.get(ban_type, ban_type)}</p>'
                     f'<p><strong>理由:</strong> {reason}</p>'
                     f'{"<p><strong>解封时间:</strong> " + user.banned_until.strftime("%Y-%m-%d %H:%M") + "</p>" if user.banned_until else "<p><strong>永久封禁</strong></p>"}'
                     f'<p>如有疑问，请联系管理员。</p>',
    )
    db.session.add(pm)

    return ban_log


def unban_user(user, operator, reason=''):
    """Remove a ban and update audit trail."""
    from app.models.admin import BanLog

    # Update active BanLogs
    active_bans = BanLog.query.filter_by(user_id=user.id, is_active=True).all()
    for ban_log in active_bans:
        ban_log.is_active = False
        ban_log.unbanned_by_id = operator.id
        ban_log.unban_reason = reason
        ban_log.unbanned_at = datetime.now(timezone.utc)

    user.is_banned = False
    user.ban_type = None
    user.banned_reason = None
    user.banned_until = None


def auto_unban_check():
    """Check for expired temporary bans and unban users. Called by scheduler."""
    from app.models.user import User
    now = datetime.now(timezone.utc)

    expired_users = User.query.filter(
        User.is_banned == True,
        User.ban_type == 'temporary',
        User.banned_until != None,
        User.banned_until < now,
    ).all()

    count = 0
    for user in expired_users:
        # System auto-unban (no operator)
        active_bans = __import__('app.models.admin', fromlist=['BanLog']).BanLog.query.filter_by(
            user_id=user.id, is_active=True,
        ).all()
        for ban_log in active_bans:
            ban_log.is_active = False
            ban_log.unban_reason = '系统自动解封 (封禁到期)'
            ban_log.unbanned_at = now

        user.is_banned = False
        user.ban_type = None
        user.banned_reason = None
        user.banned_until = None
        count += 1

    if count > 0:
        db.session.commit()
    return count


def check_user_can_access(user):
    """Check if a banned user can perform a given action. Returns True if allowed."""
    if not user.is_banned:
        return True
    ban_type = user.ban_type
    # Permanent and temporary bans block everything
    if ban_type in ('permanent', 'temporary'):
        return False
    # Other ban types allow basic site access but block specific actions
    return True
