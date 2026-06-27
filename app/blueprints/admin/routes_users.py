"""User management routes — list, search, edit, ban, promote, IP history."""

from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.extensions import db
from app.blueprints.admin import admin_bp
from app.models.user import User
from app.models.system import Log
from app.models.admin import IpLog, BanLog, PromotionLog, UserClass
from app.helpers import permission_required, admin_action_log, ROLE_HIERARCHY, ROLE_DISPLAY


@admin_bp.route('/users')
@login_required
@permission_required('can_manage_users')
def users():
    """User management list with search and filters."""
    page = request.args.get('page', 1, type=int)
    q = request.args.get('q', '').strip()
    role_filter = request.args.get('role', '')
    status_filter = request.args.get('status', '')
    sort = request.args.get('sort', 'registered_at_desc')

    query = User.query

    if q:
        query = query.filter(db.or_(
            User.username.ilike(f'%{q}%'),
            User.email.ilike(f'%{q}%'),
        ))
    if role_filter:
        query = query.filter(User.role == role_filter)
    if status_filter == 'banned':
        query = query.filter(User.is_banned == True)
    elif status_filter == 'active':
        query = query.filter(User.is_banned == False, User.is_active == True)
    elif status_filter == 'disabled':
        query = query.filter(User.is_active == False)

    # Sort
    sort_map = {
        'registered_at_desc': User.registered_at.desc(),
        'registered_at_asc': User.registered_at.asc(),
        'uploaded_desc': User.uploaded.desc(),
        'downloaded_desc': User.downloaded.desc(),
        'seed_bonus_desc': User.seed_bonus.desc(),
        'username_asc': User.username.asc(),
    }
    query = query.order_by(sort_map.get(sort, User.registered_at.desc()))

    paginated = query.paginate(page=page, per_page=30, error_out=False)
    return render_template('admin/users.html',
                           title='用户管理',
                           paginated=paginated,
                           roles=ROLE_HIERARCHY,
                           role_display=ROLE_DISPLAY,
                           search_params=request.args)


@admin_bp.route('/users/<int:user_id>', methods=['GET', 'POST'])
@login_required
@permission_required('can_manage_users')
def user_edit(user_id):
    """Edit user details, role, ban status, and permissions."""
    user = User.query.get_or_404(user_id)
    user_classes = UserClass.query.order_by(UserClass.level.asc()).all()

    if user.role in ('Admin', 'Sysop') and current_user.role not in ('Sysop',):
        flash('您无权编辑高级管理员的账户。', 'danger')
        return redirect(url_for('admin.users'))

    if request.method == 'POST':
        action = request.form.get('action', 'save')

        if action == 'save':
            old_role = user.role
            user.role = request.form.get('role', user.role)
            user.seed_bonus = float(request.form.get('seed_bonus', user.seed_bonus or 0))
            user.invite_tokens = int(request.form.get('invite_tokens', user.invite_tokens or 0))
            user.warning_count = int(request.form.get('warning_count', user.warning_count or 0))
            user.uploaded = int(request.form.get('uploaded', user.uploaded or 0))
            user.downloaded = int(request.form.get('downloaded', user.downloaded or 0))
            user.title = request.form.get('title', user.title) or None
            user.signature = request.form.get('signature', user.signature) or None
            user.info_text = request.form.get('info_text', user.info_text) or None
            user.is_active = 'is_active' in request.form
            user.promotion_eligible = 'promotion_eligible' in request.form

            # Update admin permissions
            for perm_key in request.form:
                if perm_key.startswith('perm_'):
                    perm_name = perm_key[5:]
                    user.set_permission(perm_name, True)
            # Clear unchecked permissions
            from app.services.admin_permission_service import ADMIN_PERMISSIONS
            for perm_name in ADMIN_PERMISSIONS:
                if f'perm_{perm_name}' not in request.form:
                    user.set_permission(perm_name, False)

            admin_action_log(
                'edit_user', target_type='user', target_id=user.id,
                details=f'编辑用户 {user.username}',
                related_user_id=user.id,
                old_value=f'role={old_role}', new_value=f'role={user.role}',
                severity='info',
            )
            db.session.commit()
            flash(f'用户 {user.username} 已更新。', 'success')

        elif action == 'promote':
            new_role = request.form.get('promote_role')
            if new_role and new_role in ROLE_HIERARCHY:
                old_role = user.role
                user.role = new_role
                log_entry = PromotionLog(
                    user_id=user.id, from_class=old_role, to_class=new_role,
                    triggered_by='manual', operator_id=current_user.id,
                    reason=request.form.get('promote_reason', '管理员手动操作'),
                )
                db.session.add(log_entry)
                admin_action_log(
                    'promote_user', target_type='user', target_id=user.id,
                    details=f'{old_role} -> {new_role}',
                    related_user_id=user.id, severity='warning',
                )
                db.session.commit()
                flash(f'用户 {user.username} 已从 {ROLE_DISPLAY.get(old_role, old_role)} 升级为 {ROLE_DISPLAY.get(new_role, new_role)}。', 'success')
            else:
                flash('无效的角色。', 'danger')

        return redirect(url_for('admin.user_edit', user_id=user.id))

    # GET — load user data
    ip_history = IpLog.query.filter_by(user_id=user.id).order_by(IpLog.created_at.desc()).limit(50).all()
    ban_history = BanLog.query.filter_by(user_id=user.id).order_by(BanLog.created_at.desc()).limit(20).all()
    promotion_history = PromotionLog.query.filter_by(user_id=user.id).order_by(PromotionLog.created_at.desc()).limit(20).all()
    activity_logs = Log.query.filter(
        (Log.user_id == user.id) | (Log.related_user_id == user.id)
    ).order_by(Log.created_at.desc()).limit(30).all()

    return render_template('admin/user_edit.html',
                           title=f'编辑用户 {user.username}',
                           user=user,
                           roles=ROLE_HIERARCHY,
                           role_display=ROLE_DISPLAY,
                           user_classes=user_classes,
                           ip_history=ip_history,
                           ban_history=ban_history,
                           promotion_history=promotion_history,
                           activity_logs=activity_logs)


@admin_bp.route('/users/<int:user_id>/ip-history')
@login_required
@permission_required('can_view_ip')
def user_ip_history(user_id):
    """Detailed IP history for a user."""
    user = User.query.get_or_404(user_id)
    page = request.args.get('page', 1, type=int)
    paginated = IpLog.query.filter_by(user_id=user.id)\
        .order_by(IpLog.created_at.desc())\
        .paginate(page=page, per_page=50, error_out=False)
    return render_template('admin/user_ip_history.html',
                           title=f'{user.username} IP历史',
                           user=user,
                           paginated=paginated)


@admin_bp.route('/users/<int:user_id>/ban', methods=['POST'])
@login_required
@permission_required('can_ban_users')
def user_ban(user_id):
    """Ban a user with type, duration, and reason."""
    user = User.query.get_or_404(user_id)

    if user.role in ('Admin', 'Sysop') and current_user.role != 'Sysop':
        flash('您无权封禁高级管理员。', 'danger')
        return redirect(url_for('admin.users'))

    if user.is_banned:
        flash('该用户已被封禁。', 'warning')
        return redirect(url_for('admin.user_edit', user_id=user.id))

    from datetime import datetime, timezone, timedelta
    ban_type = request.form.get('ban_type', 'temporary')
    reason = request.form.get('reason', '')
    duration_days = request.form.get('duration_days', type=int)
    ban_ip = 'ban_ip' in request.form

    user.is_banned = True
    user.ban_type = ban_type
    user.banned_reason = reason

    if ban_type == 'temporary' and duration_days:
        user.banned_until = datetime.now(timezone.utc) + timedelta(days=duration_days)
    else:
        user.banned_until = None

    # Create BanLog
    ban_log = BanLog(
        user_id=user.id,
        operator_id=current_user.id,
        ban_type=ban_type,
        reason=reason,
        duration_days=duration_days if ban_type == 'temporary' else None,
        banned_until=user.banned_until,
    )
    db.session.add(ban_log)

    # Optionally ban user's IPs
    if ban_ip:
        from app.models.admin import IpBan
        recent_ips = db.session.query(IpLog.ip).filter(
            IpLog.user_id == user.id,
            IpLog.event_type == 'login',
        ).distinct().limit(5).all()
        for (ip,) in recent_ips:
            existing = IpBan.query.filter_by(ip_address=ip, is_active=True).first()
            if not existing:
                db.session.add(IpBan(
                    ip_address=ip,
                    reason=f'用户 {user.username} 被封禁，连带IP封禁: {reason}',
                    operator_id=current_user.id,
                ))

    admin_action_log(
        'ban_user', target_type='user', target_id=user.id,
        details=f'封禁用户 {user.username} (类型: {ban_type}, 理由: {reason})',
        related_user_id=user.id, severity='danger',
    )
    db.session.commit()
    flash(f'用户 {user.username} 已被封禁。', 'success')
    return redirect(url_for('admin.users'))


@admin_bp.route('/users/<int:user_id>/unban', methods=['POST'])
@login_required
@permission_required('can_ban_users')
def user_unban(user_id):
    """Unban a user."""
    user = User.query.get_or_404(user_id)

    if not user.is_banned:
        flash('该用户未被封禁。', 'warning')
        return redirect(url_for('admin.user_edit', user_id=user.id))

    unban_reason = request.form.get('unban_reason', '')

    # Update active BanLogs
    active_bans = BanLog.query.filter_by(user_id=user.id, is_active=True).all()
    for ban_log in active_bans:
        ban_log.is_active = False
        ban_log.unbanned_by_id = current_user.id
        ban_log.unban_reason = unban_reason
        ban_log.unbanned_at = db.func.now()

    user.is_banned = False
    user.ban_type = None
    user.banned_reason = None
    user.banned_until = None

    admin_action_log(
        'unban_user', target_type='user', target_id=user.id,
        details=f'解封用户 {user.username}: {unban_reason}',
        related_user_id=user.id, severity='warning',
    )
    db.session.commit()
    flash(f'用户 {user.username} 已解封。', 'success')
    return redirect(url_for('admin.users'))


@admin_bp.route('/users/batch', methods=['POST'])
@login_required
@permission_required('can_batch_operations')
def users_batch():
    """Batch operations on users."""
    user_ids = request.form.getlist('user_ids[]')
    action = request.form.get('batch_action')

    if not user_ids:
        flash('请选择至少一个用户。', 'warning')
        return redirect(url_for('admin.users'))

    users = User.query.filter(User.id.in_([int(uid) for uid in user_ids])).all()

    if action == 'send_pm':
        subject = request.form.get('pm_subject', '')
        content = request.form.get('pm_content', '')
        if not subject or not content:
            flash('请输入私信主题和内容。', 'warning')
            return redirect(url_for('admin.users'))
        from app.models.message import PrivateMessage
        count = 0
        for user in users:
            pm = PrivateMessage(
                sender_id=current_user.id,
                receiver_id=user.id,
                subject=subject,
                content=content,
                content_html=content,
            )
            db.session.add(pm)
            count += 1
        admin_action_log(
            'batch_pm', target_type='user',
            details=f'发送批量私信给 {count} 个用户: {subject}',
            severity='info',
        )
        db.session.commit()
        flash(f'已向 {count} 个用户发送私信。', 'success')

    elif action == 'add_bonus':
        points = request.form.get('bonus_points', type=float)
        reason = request.form.get('bonus_reason', '管理员批量调整')
        if not points:
            flash('请输入积分数量。', 'warning')
            return redirect(url_for('admin.users'))
        from app.models.bonus import SeedBonusLog
        from decimal import Decimal
        for user in users:
            user.seed_bonus = (user.seed_bonus or 0) + Decimal(str(points))
            db.session.add(SeedBonusLog(
                user_id=user.id,
                points_change=Decimal(str(points)),
                reason='admin_adjust',
                description=reason,
            ))
        admin_action_log(
            'batch_bonus', target_type='user',
            details=f'批量调整 {len(users)} 个用户积分 {points:+} 点: {reason}',
            severity='warning',
        )
        db.session.commit()
        flash(f'已为 {len(users)} 个用户调整积分。', 'success')

    return redirect(url_for('admin.users'))


# ── User Class / Rank management ──────────────────────────────────────

@admin_bp.route('/user-class')
@login_required
@permission_required('can_promote_users')
def user_class_list():
    """User class / rank management."""
    classes = UserClass.query.order_by(UserClass.level.asc()).all()
    return render_template('admin/user_class_list.html',
                           title='用户等级管理',
                           user_classes=classes)


@admin_bp.route('/user-class/add', methods=['GET', 'POST'])
@login_required
@permission_required('can_promote_users')
def user_class_add():
    """Add a new user class definition."""
    if request.method == 'POST':
        uc = UserClass(
            name=request.form.get('name', ''),
            display_name=request.form.get('display_name', ''),
            level=int(request.form.get('level', 0)),
            min_upload_gb=float(request.form.get('min_upload_gb', 0)),
            min_ratio=float(request.form.get('min_ratio', 0)),
            min_seed_hours=int(request.form.get('min_seed_hours', 0)),
            min_account_age_days=int(request.form.get('min_account_age_days', 0)),
            min_forum_posts=int(request.form.get('min_forum_posts', 0)),
            min_snatches=int(request.form.get('min_snatches', 0)),
            keep_min_ratio=float(request.form.get('keep_min_ratio', 0)),
            keep_min_seed_hours=int(request.form.get('keep_min_seed_hours', 0)),
            invite_tokens_per_month=int(request.form.get('invite_tokens_per_month', 0)),
            pm_inbox_size=int(request.form.get('pm_inbox_size', 100)),
            bonus_multiplier=float(request.form.get('bonus_multiplier', 1.0)),
            download_slots=int(request.form.get('download_slots', 3)),
            wait_time_seconds=int(request.form.get('wait_time_seconds', 0)),
            can_view_peers='can_view_peers' in request.form,
            can_use_freeleech_tokens='can_use_freeleech_tokens' in request.form,
            exempt_from_hnr='exempt_from_hnr' in request.form,
            exempt_from_wait_time='exempt_from_wait_time' in request.form,
            sort_order=int(request.form.get('sort_order', 0)),
            color=request.form.get('color', '#6c757d'),
            icon=request.form.get('icon', ''),
            badge_text=request.form.get('badge_text', ''),
        )
        db.session.add(uc)
        admin_action_log('create_user_class', target_type='user_class',
                         details=f'创建用户等级: {uc.display_name}', severity='warning')
        db.session.commit()
        flash(f'等级 {uc.display_name} 已创建。', 'success')
        return redirect(url_for('admin.user_class_list'))
    return render_template('admin/user_class_edit.html', title='添加用户等级', user_class=None)


@admin_bp.route('/user-class/<int:class_id>/edit', methods=['GET', 'POST'])
@login_required
@permission_required('can_promote_users')
def user_class_edit(class_id):
    """Edit a user class definition."""
    uc = UserClass.query.get_or_404(class_id)
    if request.method == 'POST':
        uc.name = request.form.get('name', uc.name)
        uc.display_name = request.form.get('display_name', uc.display_name)
        uc.level = int(request.form.get('level', uc.level))
        uc.min_upload_gb = float(request.form.get('min_upload_gb', uc.min_upload_gb))
        uc.min_ratio = float(request.form.get('min_ratio', uc.min_ratio))
        uc.min_seed_hours = int(request.form.get('min_seed_hours', uc.min_seed_hours))
        uc.min_account_age_days = int(request.form.get('min_account_age_days', uc.min_account_age_days))
        uc.min_forum_posts = int(request.form.get('min_forum_posts', uc.min_forum_posts))
        uc.min_snatches = int(request.form.get('min_snatches', uc.min_snatches))
        uc.keep_min_ratio = float(request.form.get('keep_min_ratio', uc.keep_min_ratio))
        uc.keep_min_seed_hours = int(request.form.get('keep_min_seed_hours', uc.keep_min_seed_hours))
        uc.invite_tokens_per_month = int(request.form.get('invite_tokens_per_month', uc.invite_tokens_per_month))
        uc.pm_inbox_size = int(request.form.get('pm_inbox_size', uc.pm_inbox_size))
        uc.bonus_multiplier = float(request.form.get('bonus_multiplier', uc.bonus_multiplier))
        uc.download_slots = int(request.form.get('download_slots', uc.download_slots))
        uc.wait_time_seconds = int(request.form.get('wait_time_seconds', uc.wait_time_seconds))
        uc.can_view_peers = 'can_view_peers' in request.form
        uc.can_use_freeleech_tokens = 'can_use_freeleech_tokens' in request.form
        uc.exempt_from_hnr = 'exempt_from_hnr' in request.form
        uc.exempt_from_wait_time = 'exempt_from_wait_time' in request.form
        uc.sort_order = int(request.form.get('sort_order', uc.sort_order))
        uc.color = request.form.get('color', uc.color)
        uc.icon = request.form.get('icon', uc.icon)
        uc.badge_text = request.form.get('badge_text', uc.badge_text)
        admin_action_log('edit_user_class', target_type='user_class', target_id=uc.id,
                         details=f'编辑用户等级: {uc.display_name}', severity='warning')
        db.session.commit()
        flash(f'等级 {uc.display_name} 已更新。', 'success')
        return redirect(url_for('admin.user_class_list'))
    return render_template('admin/user_class_edit.html', title=f'编辑等级 {uc.display_name}', user_class=uc)


@admin_bp.route('/user-class/<int:class_id>/delete', methods=['POST'])
@login_required
@permission_required('can_promote_users')
def user_class_delete(class_id):
    """Delete a user class definition."""
    uc = UserClass.query.get_or_404(class_id)
    admin_action_log('delete_user_class', target_type='user_class', target_id=uc.id,
                     details=f'删除用户等级: {uc.display_name}', severity='danger')
    db.session.delete(uc)
    db.session.commit()
    flash(f'等级 {uc.display_name} 已删除。', 'success')
    return redirect(url_for('admin.user_class_list'))


# ── QB Configuration ──────────────────────────────────────────────────

@admin_bp.route('/qb-config', methods=['GET', 'POST'])
@login_required
@permission_required('can_manage_settings')
def qb_config():
    """Global qBittorrent sync configuration."""
    from app.models.system import SiteSetting
    if request.method == 'POST':
        SiteSetting.set('qb_global_enabled', 'true' if request.form.get('qb_enabled') == 'on' else 'false', 'bool', '启用全局QB同步')
        SiteSetting.set('qb_sync_interval_minutes', request.form.get('qb_interval', '30'), 'int', 'QB同步间隔(分钟)')
        SiteSetting.set('qb_default_host', request.form.get('qb_host', ''), 'string', '默认QB主机地址')
        SiteSetting.set('qb_default_port', request.form.get('qb_port', '8080'), 'int', '默认QB端口')
        admin_action_log('update_qb_config', target_type='setting', details='更新QB全局配置', severity='warning')
        db.session.commit()
        flash('QB配置已保存。', 'success')
        return redirect(url_for('admin.qb_config'))

    return render_template('admin/qb_config.html',
                           title='QB同步配置',
                           qb_enabled=SiteSetting.get('qb_global_enabled', False),
                           qb_interval=SiteSetting.get('qb_sync_interval_minutes', '30'),
                           qb_host=SiteSetting.get('qb_default_host', ''),
                           qb_port=SiteSetting.get('qb_default_port', '8080'))
