"""System announcement routes."""

from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.extensions import db
from app.blueprints.admin import admin_bp
from app.models.system import Announcement
from app.helpers import permission_required, admin_action_log, ROLE_HIERARCHY


@admin_bp.route('/announcements')
@login_required
@permission_required('can_manage_news')
def announcements():
    """System announcements list."""
    page = request.args.get('page', 1, type=int)
    paginated = Announcement.query.order_by(Announcement.created_at.desc())\
        .paginate(page=page, per_page=20, error_out=False)
    return render_template('admin/announcements.html',
                           title='系统公告管理',
                           paginated=paginated)


@admin_bp.route('/announcements/create', methods=['GET', 'POST'])
@login_required
@permission_required('can_manage_news')
def announcement_create():
    """Create a system announcement."""
    if request.method == 'POST':
        from datetime import datetime, timezone, timedelta
        days = request.form.get('show_days', type=int)

        announcement = Announcement(
            title=request.form.get('title', ''),
            content=request.form.get('content', ''),
            content_html=request.form.get('content', ''),
            author_id=current_user.id,
            target_role=request.form.get('target_role') or None,
            is_pinned='is_pinned' in request.form,
            is_published='is_published' in request.form,
            show_until=datetime.now(timezone.utc) + timedelta(days=days) if days else None,
        )
        db.session.add(announcement)
        admin_action_log('create_announcement', target_type='announcement',
                         details=f'发布系统公告: {announcement.title[:50]}', severity='info')
        db.session.commit()
        flash('系统公告已发布。', 'success')
        return redirect(url_for('admin.announcements'))

    return render_template('admin/announcement_create.html',
                           title='发布系统公告',
                           roles=ROLE_HIERARCHY)


@admin_bp.route('/announcements/<int:ann_id>/edit', methods=['GET', 'POST'])
@login_required
@permission_required('can_manage_news')
def announcement_edit(ann_id):
    """Edit a system announcement."""
    ann = Announcement.query.get_or_404(ann_id)
    if request.method == 'POST':
        from datetime import datetime, timezone, timedelta
        days = request.form.get('show_days', type=int)

        ann.title = request.form.get('title', ann.title)
        ann.content = request.form.get('content', ann.content)
        ann.content_html = request.form.get('content', ann.content)
        ann.target_role = request.form.get('target_role') or None
        ann.is_pinned = 'is_pinned' in request.form
        ann.is_published = 'is_published' in request.form
        ann.show_until = datetime.now(timezone.utc) + timedelta(days=days) if days else None
        admin_action_log('edit_announcement', target_type='announcement', target_id=ann.id,
                         details=f'编辑系统公告: {ann.title[:50]}', severity='info')
        db.session.commit()
        flash('系统公告已更新。', 'success')
        return redirect(url_for('admin.announcements'))

    return render_template('admin/announcement_create.html',
                           title=f'编辑公告 {ann.title[:30]}',
                           announcement=ann,
                           roles=ROLE_HIERARCHY)


@admin_bp.route('/announcements/<int:ann_id>/delete', methods=['POST'])
@login_required
@permission_required('can_manage_news')
def announcement_delete(ann_id):
    """Delete a system announcement."""
    ann = Announcement.query.get_or_404(ann_id)
    admin_action_log('delete_announcement', target_type='announcement', target_id=ann.id,
                     details=f'删除系统公告: {ann.title[:50]}', severity='danger')
    db.session.delete(ann)
    db.session.commit()
    flash('系统公告已删除。', 'success')
    return redirect(url_for('admin.announcements'))
