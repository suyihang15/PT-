"""Forum moderation routes."""

from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.extensions import db
from app.blueprints.admin import admin_bp
from app.models.forum import Forum, ForumTopic, ForumPost
from app.helpers import permission_required, admin_action_log, ROLE_HIERARCHY


@admin_bp.route('/forums')
@login_required
@permission_required('can_manage_forums')
def forums():
    """Forum management list."""
    all_forums = Forum.query.order_by(Forum.sort_order).all()
    return render_template('admin/forums.html', title='论坛管理', forums=all_forums)


@admin_bp.route('/forums/add', methods=['GET', 'POST'])
@login_required
@permission_required('can_manage_forums')
def forum_add():
    """Add a new forum."""
    if request.method == 'POST':
        forum = Forum(
            name=request.form.get('name', ''),
            description=request.form.get('description', ''),
            slug=request.form.get('slug', ''),
            sort_order=int(request.form.get('sort_order', 0)),
            min_role_view=request.form.get('min_role_view', 'User'),
            min_role_post=request.form.get('min_role_post', 'User'),
        )
        db.session.add(forum)
        admin_action_log('create_forum', target_type='forum', details=f'创建论坛: {forum.name}', severity='info')
        db.session.commit()
        flash(f'论坛 {forum.name} 已创建。', 'success')
        return redirect(url_for('admin.forums'))
    return render_template('admin/forum_edit.html', title='添加论坛', forum=None, roles=ROLE_HIERARCHY)


@admin_bp.route('/forums/<int:forum_id>/edit', methods=['GET', 'POST'])
@login_required
@permission_required('can_manage_forums')
def forum_edit(forum_id):
    """Edit a forum."""
    forum = Forum.query.get_or_404(forum_id)
    if request.method == 'POST':
        forum.name = request.form.get('name', forum.name)
        forum.description = request.form.get('description', forum.description)
        forum.slug = request.form.get('slug', forum.slug)
        forum.sort_order = int(request.form.get('sort_order', forum.sort_order))
        forum.min_role_view = request.form.get('min_role_view', forum.min_role_view)
        forum.min_role_post = request.form.get('min_role_post', forum.min_role_post)
        admin_action_log('edit_forum', target_type='forum', target_id=forum.id, details=f'编辑论坛: {forum.name}', severity='info')
        db.session.commit()
        flash(f'论坛 {forum.name} 已更新。', 'success')
        return redirect(url_for('admin.forums'))
    return render_template('admin/forum_edit.html', title=f'编辑论坛 {forum.name}', forum=forum, roles=ROLE_HIERARCHY)


@admin_bp.route('/forums/<int:forum_id>/delete', methods=['POST'])
@login_required
@permission_required('can_manage_forums')
def forum_delete(forum_id):
    """Delete a forum."""
    forum = Forum.query.get_or_404(forum_id)
    admin_action_log('delete_forum', target_type='forum', target_id=forum.id, details=f'删除论坛: {forum.name}', severity='danger')
    db.session.delete(forum)
    db.session.commit()
    flash(f'论坛 {forum.name} 已删除。', 'success')
    return redirect(url_for('admin.forums'))
