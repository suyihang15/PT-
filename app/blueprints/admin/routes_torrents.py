"""Torrent management routes — list, edit, batch operations, freeleech/sticky."""

from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.extensions import db
from app.blueprints.admin import admin_bp
from app.models.torrent import Torrent, Category
from app.helpers import permission_required, admin_action_log
from datetime import datetime, timezone, timedelta


@admin_bp.route('/torrents')
@login_required
@permission_required('can_manage_torrents')
def torrents():
    """Torrent management list with filters."""
    page = request.args.get('page', 1, type=int)
    q = request.args.get('q', '').strip()
    category_filter = request.args.get('category', type=int)
    status = request.args.get('status', '')  # visible, banned, freeleech
    sort = request.args.get('sort', 'added_at_desc')

    query = Torrent.query

    if q:
        query = query.filter(Torrent.name.ilike(f'%{q}%'))
    if category_filter:
        query = query.filter(Torrent.category_id == category_filter)
    if status == 'visible':
        query = query.filter(Torrent.visible == True, Torrent.banned == False)
    elif status == 'banned':
        query = query.filter(Torrent.banned == True)
    elif status == 'freeleech':
        query = query.filter(Torrent.freeleech == True)
    elif status == 'sticky':
        query = query.filter(Torrent.sticky_until > datetime.now(timezone.utc))

    sort_map = {
        'added_at_desc': Torrent.added_at.desc(),
        'added_at_asc': Torrent.added_at.asc(),
        'size_desc': Torrent.size.desc(),
        'seeders_desc': Torrent.seeders.desc(),
        'name_asc': Torrent.name.asc(),
    }
    query = query.order_by(sort_map.get(sort, Torrent.added_at.desc()))

    categories = Category.query.order_by(Category.sort_order).all()
    paginated = query.paginate(page=page, per_page=30, error_out=False)
    return render_template('admin/torrents.html',
                           title='种子管理',
                           paginated=paginated,
                           categories=categories,
                           search_params=request.args)


@admin_bp.route('/torrents/<int:torrent_id>', methods=['GET', 'POST'])
@login_required
@permission_required('can_manage_torrents')
def torrent_edit(torrent_id):
    """Edit torrent properties."""
    torrent = Torrent.query.get_or_404(torrent_id)
    categories = Category.query.order_by(Category.sort_order).all()

    if request.method == 'POST':
        action = request.form.get('action', 'save')

        if action == 'save':
            torrent.name = request.form.get('name', torrent.name)
            torrent.description = request.form.get('description', torrent.description)
            torrent.description_html = request.form.get('description', torrent.description)
            torrent.category_id = int(request.form.get('category_id', torrent.category_id))
            torrent.visible = 'visible' in request.form
            torrent.anonymous = 'anonymous' in request.form
            torrent.moderation_note = request.form.get('moderation_note', '') or None

            # Freeleech
            fl_days = request.form.get('freeleech_days', type=int)
            if fl_days and fl_days > 0:
                torrent.freeleech = True
                torrent.freeleech_until = datetime.now(timezone.utc) + timedelta(days=fl_days)
                torrent.freeleech_set_by_id = current_user.id
            elif 'freeleech_unlimited' in request.form:
                torrent.freeleech = True
                torrent.freeleech_until = None
                torrent.freeleech_set_by_id = current_user.id
            else:
                torrent.freeleech = False
                torrent.freeleech_until = None

            # Double upload
            du_days = request.form.get('double_upload_days', type=int)
            if du_days and du_days > 0:
                torrent.double_upload = True
                torrent.double_upload_until = datetime.now(timezone.utc) + timedelta(days=du_days)
            elif 'double_upload_unlimited' in request.form:
                torrent.double_upload = True
                torrent.double_upload_until = None
            else:
                torrent.double_upload = False
                torrent.double_upload_until = None

            # Half download
            hd_days = request.form.get('half_download_days', type=int)
            if hd_days and hd_days > 0:
                torrent.half_download = True
                torrent.half_download_until = datetime.now(timezone.utc) + timedelta(days=hd_days)
            elif 'half_download_unlimited' in request.form:
                torrent.half_download = True
                torrent.half_download_until = None
            else:
                torrent.half_download = False
                torrent.half_download_until = None

            # Sticky
            sticky_days = request.form.get('sticky_days', type=int)
            if sticky_days and sticky_days > 0:
                torrent.sticky_until = datetime.now(timezone.utc) + timedelta(days=sticky_days)
                torrent.sticky_set_by_id = current_user.id
            else:
                torrent.sticky_until = None

            admin_action_log(
                'edit_torrent', target_type='torrent', target_id=torrent.id,
                details=f'编辑种子: {torrent.name[:50]}',
                severity='info',
            )
            db.session.commit()
            flash(f'种子 {torrent.name[:50]} 已更新。', 'success')

        elif action == 'ban':
            torrent.banned = True
            torrent.banned_reason = request.form.get('banned_reason', '')
            torrent.visible = False
            admin_action_log(
                'ban_torrent', target_type='torrent', target_id=torrent.id,
                details=f'禁用种子: {torrent.name[:50]}, 理由: {torrent.banned_reason}',
                severity='danger',
            )
            db.session.commit()
            flash(f'种子已被禁用。', 'success')

        elif action == 'unban':
            torrent.banned = False
            torrent.banned_reason = None
            torrent.visible = True
            admin_action_log(
                'unban_torrent', target_type='torrent', target_id=torrent.id,
                details=f'恢复种子: {torrent.name[:50]}',
                severity='warning',
            )
            db.session.commit()
            flash(f'种子已恢复。', 'success')

        elif action == 'delete':
            admin_action_log(
                'delete_torrent', target_type='torrent', target_id=torrent.id,
                details=f'删除种子: {torrent.name[:50]}',
                severity='danger',
            )
            db.session.delete(torrent)
            db.session.commit()
            flash(f'种子已删除。', 'success')
            return redirect(url_for('admin.torrents'))

        return redirect(url_for('admin.torrent_edit', torrent_id=torrent.id))

    return render_template('admin/torrent_edit.html',
                           title=f'编辑种子 {torrent.name[:30]}',
                           torrent=torrent,
                           categories=categories)


@admin_bp.route('/torrents/batch', methods=['POST'])
@login_required
@permission_required('can_manage_torrents')
def torrents_batch():
    """Batch operations on torrents."""
    torrent_ids = request.form.getlist('torrent_ids[]')
    action = request.form.get('batch_action')

    if not torrent_ids:
        flash('请选择至少一个种子。', 'warning')
        return redirect(url_for('admin.torrents'))

    torrents = Torrent.query.filter(Torrent.id.in_([int(tid) for tid in torrent_ids])).all()

    if action == 'set_freeleech':
        days = request.form.get('freeleech_days', type=int, default=7)
        for t in torrents:
            t.freeleech = True
            t.freeleech_until = datetime.now(timezone.utc) + timedelta(days=days)
            t.freeleech_set_by_id = current_user.id
        admin_action_log(
            'batch_freeleech', target_type='torrent',
            details=f'批量设置 {len(torrents)} 个种子为免费 (时长: {days}天)',
            severity='info',
        )
    elif action == 'set_sticky':
        days = request.form.get('sticky_days', type=int, default=3)
        for t in torrents:
            t.sticky_until = datetime.now(timezone.utc) + timedelta(days=days)
            t.sticky_set_by_id = current_user.id
        admin_action_log(
            'batch_sticky', target_type='torrent',
            details=f'批量置顶 {len(torrents)} 个种子 (时长: {days}天)',
            severity='info',
        )
    elif action == 'delete':
        for t in torrents:
            admin_action_log(
                'batch_delete_torrent', target_type='torrent', target_id=t.id,
                details=f'批量删除种子: {t.name[:50]}',
                severity='danger',
            )
            db.session.delete(t)

    db.session.commit()
    flash(f'已对 {len(torrents)} 个种子执行操作。', 'success')
    return redirect(url_for('admin.torrents'))
