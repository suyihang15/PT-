"""Invite management routes."""

from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.extensions import db
from app.blueprints.admin import admin_bp
from app.models.user import Invite, User
from app.helpers import permission_required, admin_action_log


@admin_bp.route('/invites')
@login_required
@permission_required('can_manage_invites')
def invites():
    """Invite code management."""
    page = request.args.get('page', 1, type=int)
    status = request.args.get('status', '')  # used, unused, expired, all

    query = Invite.query
    if status == 'used':
        query = query.filter_by(used=True)
    elif status == 'unused':
        query = query.filter_by(used=False)
    elif status == 'expired':
        from datetime import datetime, timezone
        query = query.filter(Invite.expires_at != None, Invite.expires_at < datetime.now(timezone.utc), Invite.used == False)

    paginated = query.order_by(Invite.created_at.desc())\
        .paginate(page=page, per_page=30, error_out=False)
    return render_template('admin/invites.html',
                           title='邀请管理',
                           paginated=paginated,
                           status=status)


@admin_bp.route('/invites/generate', methods=['POST'])
@login_required
@permission_required('can_manage_invites')
def invites_generate():
    """Generate invite codes for a user."""
    username = request.form.get('username', '').strip()
    count = request.form.get('count', 1, type=int)
    user = User.query.filter_by(username=username).first()
    if not user:
        flash('未找到该用户。', 'danger')
        return redirect(url_for('admin.invites'))
    if count < 1 or count > 100:
        flash('数量必须在1-100之间。', 'danger')
        return redirect(url_for('admin.invites'))

    for _ in range(count):
        invite = Invite(
            code=Invite.generate_code(),
            creator_id=user.id,
            expires_at=None,  # No expiration
        )
        db.session.add(invite)

    admin_action_log('generate_invites', target_type='user', target_id=user.id,
                     details=f'为用户 {user.username} 生成 {count} 个邀请码',
                     related_user_id=user.id, severity='warning')
    db.session.commit()
    flash(f'已为 {user.username} 生成 {count} 个邀请码。', 'success')
    return redirect(url_for('admin.invites'))


@admin_bp.route('/invites/<int:invite_id>/revoke', methods=['POST'])
@login_required
@permission_required('can_manage_invites')
def invites_revoke(invite_id):
    """Revoke an invite code."""
    invite = Invite.query.get_or_404(invite_id)
    if invite.used:
        flash('该邀请码已被使用，无法撤销。', 'danger')
        return redirect(url_for('admin.invites'))
    admin_action_log('revoke_invite', target_type='invite', target_id=invite.id,
                     details=f'撤销邀请码: {invite.code[:12]}...', severity='warning')
    db.session.delete(invite)
    db.session.commit()
    flash('邀请码已撤销。', 'success')
    return redirect(url_for('admin.invites'))
