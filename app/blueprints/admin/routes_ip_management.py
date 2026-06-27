"""IP management routes — IP bans, whitelist, multi-account detection."""

from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.extensions import db
from app.blueprints.admin import admin_bp
from app.models.admin import IpBan, IpWhitelist, IpLog
from app.models.user import User
from app.helpers import permission_required, admin_action_log


@admin_bp.route('/ip-bans')
@login_required
@permission_required('can_manage_ip_bans')
def ip_bans():
    """IP ban management."""
    page = request.args.get('page', 1, type=int)
    paginated = IpBan.query.order_by(IpBan.created_at.desc())\
        .paginate(page=page, per_page=30, error_out=False)
    return render_template('admin/ip_bans.html',
                           title='IP封禁管理',
                           paginated=paginated)


@admin_bp.route('/ip-bans/add', methods=['POST'])
@login_required
@permission_required('can_manage_ip_bans')
def ip_ban_add():
    """Add an IP ban."""
    ip = request.form.get('ip_address', '').strip()
    reason = request.form.get('reason', '')
    duration_days = request.form.get('duration_days', type=int)

    if not ip or not reason:
        flash('请输入IP地址和封禁理由。', 'danger')
        return redirect(url_for('admin.ip_bans'))

    from datetime import datetime, timezone, timedelta
    ban = IpBan(
        ip_address=ip,
        reason=reason,
        operator_id=current_user.id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=duration_days) if duration_days else None,
    )
    db.session.add(ban)
    admin_action_log('add_ip_ban', target_type='ip_ban',
                     details=f'IP封禁: {ip}, 理由: {reason}', severity='danger')
    db.session.commit()
    flash(f'IP {ip} 已被封禁。', 'success')
    return redirect(url_for('admin.ip_bans'))


@admin_bp.route('/ip-bans/<int:ban_id>/delete', methods=['POST'])
@login_required
@permission_required('can_manage_ip_bans')
def ip_ban_delete(ban_id):
    """Remove an IP ban."""
    ban = IpBan.query.get_or_404(ban_id)
    ban.is_active = False
    admin_action_log('remove_ip_ban', target_type='ip_ban', target_id=ban.id,
                     details=f'解除IP封禁: {ban.ip_address}', severity='warning')
    db.session.commit()
    flash(f'IP {ban.ip_address} 封禁已解除。', 'success')
    return redirect(url_for('admin.ip_bans'))


@admin_bp.route('/ip-whitelist')
@login_required
@permission_required('can_manage_ip_bans')
def ip_whitelist():
    """IP whitelist management."""
    page = request.args.get('page', 1, type=int)
    paginated = IpWhitelist.query.order_by(IpWhitelist.created_at.desc())\
        .paginate(page=page, per_page=30, error_out=False)
    return render_template('admin/ip_whitelist.html',
                           title='IP白名单管理',
                           paginated=paginated)


@admin_bp.route('/ip-whitelist/add', methods=['POST'])
@login_required
@permission_required('can_manage_ip_bans')
def ip_whitelist_add():
    """Add an IP whitelist entry."""
    username = request.form.get('username', '').strip()
    ip = request.form.get('ip_address', '').strip()
    description = request.form.get('description', '')

    user = User.query.filter_by(username=username).first()
    if not user:
        flash('未找到该用户。', 'danger')
        return redirect(url_for('admin.ip_whitelist'))

    entry = IpWhitelist(
        user_id=user.id,
        ip_address=ip,
        description=description,
        added_by_id=current_user.id,
    )
    db.session.add(entry)
    admin_action_log('add_ip_whitelist', target_type='ip_whitelist',
                     details=f'IP白名单: {ip} for {user.username}, {description}', severity='info')
    db.session.commit()
    flash(f'IP {ip} 已加入 {user.username} 的白名单。', 'success')
    return redirect(url_for('admin.ip_whitelist'))


@admin_bp.route('/ip-whitelist/<int:entry_id>/delete', methods=['POST'])
@login_required
@permission_required('can_manage_ip_bans')
def ip_whitelist_delete(entry_id):
    """Remove an IP whitelist entry."""
    entry = IpWhitelist.query.get_or_404(entry_id)
    entry.is_active = False
    admin_action_log('remove_ip_whitelist', target_type='ip_whitelist', target_id=entry.id,
                     details=f'移除白名单: {entry.ip_address}', severity='warning')
    db.session.commit()
    flash(f'IP {entry.ip_address} 白名单已移除。', 'success')
    return redirect(url_for('admin.ip_whitelist'))


@admin_bp.route('/multi-accounts')
@login_required
@permission_required('can_view_ip')
def multi_accounts():
    """Detect potential multi-account users by shared IPs."""
    from sqlalchemy import func
    # Find IPs used by multiple distinct users for login events
    suspicious = db.session.query(
        IpLog.ip,
        func.count(func.distinct(IpLog.user_id)).label('user_count'),
        func.group_concat(func.distinct(IpLog.user_id)).label('user_ids'),
    ).filter(
        IpLog.event_type == 'login'
    ).group_by(
        IpLog.ip
    ).having(
        func.count(func.distinct(IpLog.user_id)) > 1
    ).order_by(
        func.count(func.distinct(IpLog.user_id)).desc()
    ).limit(100).all()

    results = []
    for ip, count, user_ids in suspicious:
        ids = [int(uid) for uid in user_ids.split(',')]
        users = User.query.filter(User.id.in_(ids)).all()
        results.append({
            'ip': ip,
            'user_count': count,
            'users': users,
        })

    return render_template('admin/multi_accounts.html',
                           title='多账号检测',
                           results=results)
