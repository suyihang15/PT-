"""Auto-promotion/demotion system based on UserClass criteria."""

from datetime import datetime, timezone
from app.extensions import db
from app.helpers import ROLE_HIERARCHY


def check_user_promotion(user):
    """Check if a user qualifies for promotion and execute it.

    Returns the PromotionLog if promoted, None otherwise.
    """
    from app.models.admin import UserClass, PromotionLog
    from app.models.message import PrivateMessage

    current_level = ROLE_HIERARCHY.get(user.role, 0)
    classes = UserClass.query.order_by(UserClass.level.asc()).all()

    # Find the highest class the user qualifies for
    target_class = None
    for uc in classes:
        if uc.level <= current_level:
            continue
        if _meets_criteria(user, uc):
            target_class = uc
        else:
            break  # Must qualify for each level in order

    if target_class is None:
        return None

    old_role = user.role
    user.role = target_class.name
    user.last_promotion_check_at = datetime.now(timezone.utc)

    log_entry = PromotionLog(
        user_id=user.id,
        from_class=old_role,
        to_class=target_class.name,
        triggered_by='auto',
        reason=f'自动升级: 满足 {target_class.display_name} 条件',
    )
    db.session.add(log_entry)

    # Send notification PM
    pm = PrivateMessage(
        sender_id=1,  # System/admin user
        receiver_id=user.id,
        subject=f'恭喜！您已升级为 {target_class.display_name}',
        content=f'亲爱的 {user.username}：\n\n'
                f'恭喜您！您的账号已自动升级为 {target_class.display_name}。\n\n'
                f'升级后将享有以下新特权：\n'
                f'- 每月邀请令牌: {target_class.invite_tokens_per_month} 个\n'
                f'- 积分倍率: x{float(target_class.bonus_multiplier):.1f}\n'
                f'- 下载槽位: {target_class.download_slots} 个\n'
                f'- 私信容量: {target_class.pm_inbox_size} 条\n\n'
                f'请继续保持良好的分享习惯！',
        content_html=f'<h4>恭喜您升级为 {target_class.display_name}！</h4>'
                     f'<p>升级后将享有新特权。请继续保持良好的分享习惯！</p>',
    )
    db.session.add(pm)

    return log_entry


def check_user_demotion(user):
    """Check if user should be demoted due to failing criteria.

    Returns the PromotionLog if demoted, None otherwise.
    """
    from app.models.admin import UserClass, PromotionLog
    from app.models.message import PrivateMessage

    current_class = UserClass.query.filter_by(name=user.role).first()
    if not current_class:
        return None

    upload_gb = float(user.uploaded) / (1024 ** 3)
    download_gb = float(user.downloaded) / (1024 ** 3)
    current_ratio = upload_gb / download_gb if download_gb > 0 else 999.0

    if current_ratio >= float(current_class.keep_min_ratio):
        return None  # Still meets criteria

    # Find lower class to demote to
    lower_class = UserClass.query.filter(
        UserClass.level < current_class.level
    ).order_by(UserClass.level.desc()).first()

    if not lower_class:
        return None

    old_role = user.role
    user.role = lower_class.name
    user.demotion_warning_count = (user.demotion_warning_count or 0) + 1
    user.last_promotion_check_at = datetime.now(timezone.utc)

    log_entry = PromotionLog(
        user_id=user.id,
        from_class=old_role,
        to_class=lower_class.name,
        triggered_by='auto',
        reason=f'自动降级: 分享率 {current_ratio:.2f} 低于要求 {float(current_class.keep_min_ratio):.2f}',
    )
    db.session.add(log_entry)

    # Send notification
    pm = PrivateMessage(
        sender_id=1,
        receiver_id=user.id,
        subject=f'账号降级通知 - 已降级为 {lower_class.display_name}',
        content=f'亲爱的 {user.username}：\n\n'
                f'很遗憾，由于您的分享率 ({current_ratio:.2f}) 低于 {current_class.display_name} '
                f'的最低要求 ({float(current_class.keep_min_ratio):.2f})，'
                f'您的账号已自动降级为 {lower_class.display_name}。\n\n'
                f'请通过多做种、多上传来恢复分享率。当您重新满足条件时，将会自动恢复等级。',
        content_html=f'<h4>账号降级通知</h4>'
                     f'<p>您的分享率 ({current_ratio:.2f}) 低于要求，已降级为 {lower_class.display_name}。</p>'
                     f'<p>请多做种、多上传来恢复。</p>',
    )
    db.session.add(pm)

    return log_entry


def _meets_criteria(user, uc):
    """Check if a user meets all criteria for a specific UserClass."""
    upload_gb = float(user.uploaded or 0) / (1024 ** 3)
    download_gb = float(user.downloaded or 0) / (1024 ** 3)
    ratio = upload_gb / download_gb if download_gb > 0 else 999.0
    account_age_days = (datetime.now(timezone.utc) - user.registered_at).days if user.registered_at else 0
    seed_hours = (user.total_seed_time_secs or 0) / 3600.0

    return (
        upload_gb >= float(uc.min_upload_gb) and
        ratio >= float(uc.min_ratio) and
        seed_hours >= uc.min_seed_hours and
        account_age_days >= uc.min_account_age_days and
        user.forum_post_count >= uc.min_forum_posts and
        user.snatched_count >= uc.min_snatches
    )


def auto_promotion_scan():
    """Scan all eligible users for promotion/demotion. Called by scheduler."""
    from app.models.user import User

    users = User.query.filter_by(is_active=True, is_banned=False, promotion_eligible=True).all()

    promoted = 0
    demoted = 0

    for user in users:
        try:
            if check_user_promotion(user):
                promoted += 1
        except Exception:
            pass

        try:
            if check_user_demotion(user):
                demoted += 1
        except Exception:
            pass

    if promoted or demoted:
        db.session.commit()

    return promoted, demoted
