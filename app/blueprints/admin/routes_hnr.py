"""H&R (Hit and Run) violation management routes."""

from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.extensions import db
from app.blueprints.admin import admin_bp
from app.models.tracker import HnrViolation
from app.helpers import permission_required, admin_action_log


@admin_bp.route('/hnr')
@login_required
@permission_required('can_manage_hnr')
def hnr():
    """H&R violation management."""
    page = request.args.get('page', 1, type=int)
    status = request.args.get('status', 'unresolved')

    query = HnrViolation.query
    if status == 'unresolved':
        query = query.filter_by(resolved=False)
    elif status == 'resolved':
        query = query.filter_by(resolved=True)

    paginated = query.order_by(HnrViolation.created_at.desc())\
        .paginate(page=page, per_page=30, error_out=False)
    return render_template('admin/hnr.html',
                           title='H&R违规管理',
                           paginated=paginated,
                           status=status)


@admin_bp.route('/hnr/<int:violation_id>/resolve', methods=['POST'])
@login_required
@permission_required('can_manage_hnr')
def hnr_resolve(violation_id):
    """Resolve or dismiss an H&R violation."""
    violation = HnrViolation.query.get_or_404(violation_id)
    if violation.resolved:
        flash('该违规已被处理。', 'warning')
        return redirect(url_for('admin.hnr'))

    action = request.form.get('action', 'resolve')
    note = request.form.get('note', '')

    violation.resolved = True
    violation.resolved_at = db.func.now()
    violation.resolved_by_id = current_user.id

    if violation.snatch:
        violation.snatch.hnr_resolved = True

    admin_action_log(
        f'hnr_{action}', target_type='hnr_violation', target_id=violation.id,
        details=f'处理H&R违规 #{violation.id}: {action}, 用户={violation.user.username if violation.user else "?"}, 备注={note}',
        related_user_id=violation.user_id, severity='info',
    )
    db.session.commit()
    flash('H&R违规已处理。', 'success')
    return redirect(url_for('admin.hnr'))
