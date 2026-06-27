"""Medal management routes."""

from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.extensions import db
from app.blueprints.admin import admin_bp
from app.models.system import Medal
from app.models.user import User, UserMedal
from app.helpers import permission_required, admin_action_log


@admin_bp.route('/medals')
@login_required
@permission_required('can_manage_medals')
def medals():
    """Medal management list."""
    all_medals = Medal.query.order_by(Medal.sort_order).all()
    return render_template('admin/medals.html', title='勋章管理', medals=all_medals)


@admin_bp.route('/medals/add', methods=['GET', 'POST'])
@login_required
@permission_required('can_manage_medals')
def medal_add():
    """Add a new medal."""
    if request.method == 'POST':
        medal = Medal(
            name=request.form.get('name', ''),
            description=request.form.get('description', ''),
            icon=request.form.get('icon', ''),
            condition_type=request.form.get('condition_type', 'manual'),
            condition_value=float(request.form.get('condition_value', 0)),
            sort_order=int(request.form.get('sort_order', 0)),
        )
        db.session.add(medal)
        admin_action_log('create_medal', target_type='medal', details=f'创建勋章: {medal.name}', severity='info')
        db.session.commit()
        flash(f'勋章 {medal.name} 已创建。', 'success')
        return redirect(url_for('admin.medals'))
    return render_template('admin/medal_edit.html', title='添加勋章', medal=None)


@admin_bp.route('/medals/<int:medal_id>/edit', methods=['GET', 'POST'])
@login_required
@permission_required('can_manage_medals')
def medal_edit(medal_id):
    """Edit a medal."""
    medal = Medal.query.get_or_404(medal_id)
    if request.method == 'POST':
        medal.name = request.form.get('name', medal.name)
        medal.description = request.form.get('description', medal.description)
        medal.icon = request.form.get('icon', medal.icon)
        medal.condition_type = request.form.get('condition_type', medal.condition_type)
        medal.condition_value = float(request.form.get('condition_value', medal.condition_value))
        medal.sort_order = int(request.form.get('sort_order', medal.sort_order))
        admin_action_log('edit_medal', target_type='medal', target_id=medal.id, details=f'编辑勋章: {medal.name}', severity='info')
        db.session.commit()
        flash(f'勋章 {medal.name} 已更新。', 'success')
        return redirect(url_for('admin.medals'))
    return render_template('admin/medal_edit.html', title=f'编辑勋章 {medal.name}', medal=medal)


@admin_bp.route('/medals/<int:medal_id>/delete', methods=['POST'])
@login_required
@permission_required('can_manage_medals')
def medal_delete(medal_id):
    """Delete a medal."""
    medal = Medal.query.get_or_404(medal_id)
    admin_action_log('delete_medal', target_type='medal', target_id=medal.id, details=f'删除勋章: {medal.name}', severity='danger')
    db.session.delete(medal)
    db.session.commit()
    flash(f'勋章 {medal.name} 已删除。', 'success')
    return redirect(url_for('admin.medals'))


@admin_bp.route('/medals/grant', methods=['POST'])
@login_required
@permission_required('can_manage_medals')
def medal_grant():
    """Grant a medal to a user."""
    medal_id = request.form.get('medal_id', type=int)
    username = request.form.get('username', '').strip()
    user = User.query.filter_by(username=username).first()
    if not user:
        flash('未找到该用户。', 'danger')
        return redirect(url_for('admin.medals'))
    medal = Medal.query.get_or_404(medal_id)
    existing = UserMedal.query.filter_by(user_id=user.id, medal_id=medal.id).first()
    if existing:
        flash(f'用户 {user.username} 已拥有该勋章。', 'warning')
        return redirect(url_for('admin.medals'))
    um = UserMedal(user_id=user.id, medal_id=medal.id)
    db.session.add(um)
    admin_action_log('grant_medal', target_type='medal', target_id=medal.id,
                     details=f'授予用户 {user.username} 勋章: {medal.name}', related_user_id=user.id, severity='info')
    db.session.commit()
    flash(f'已向用户 {user.username} 授予勋章 {medal.name}。', 'success')
    return redirect(url_for('admin.medals'))
