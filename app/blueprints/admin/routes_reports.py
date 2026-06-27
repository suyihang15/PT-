"""Report handling routes."""

from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.extensions import db
from app.blueprints.admin import admin_bp
from app.models.system import Report
from app.models.message import PrivateMessage
from app.helpers import permission_required, admin_action_log


@admin_bp.route('/reports')
@login_required
@permission_required('can_resolve_reports')
def reports():
    """Report management queue."""
    page = request.args.get('page', 1, type=int)
    status = request.args.get('status', 'pending')

    query = Report.query
    if status == 'pending':
        query = query.filter_by(resolved=False)
    elif status == 'resolved':
        query = query.filter_by(resolved=True)
    # 'all' - no filter

    paginated = query.order_by(Report.created_at.desc())\
        .paginate(page=page, per_page=20, error_out=False)
    return render_template('admin/reports.html',
                           title='举报处理',
                           paginated=paginated,
                           status=status)


@admin_bp.route('/reports/<int:report_id>/resolve', methods=['POST'])
@login_required
@permission_required('can_resolve_reports')
def report_resolve(report_id):
    """Resolve a report."""
    report = Report.query.get_or_404(report_id)
    if report.resolved:
        flash('该举报已被处理。', 'warning')
        return redirect(url_for('admin.reports'))

    action = request.form.get('action', 'dismiss')  # resolve or dismiss
    note = request.form.get('resolution_note', '')
    send_pm = 'send_pm' in request.form
    pm_message = request.form.get('pm_message', '')

    report.resolved = True
    report.resolved_by_id = current_user.id
    report.resolution_note = note
    report.resolved_at = db.func.now()

    if send_pm and report.reporter_id and pm_message:
        pm = PrivateMessage(
            sender_id=current_user.id,
            receiver_id=report.reporter_id,
            subject='举报处理结果通知',
            content=pm_message,
            content_html=pm_message,
        )
        db.session.add(pm)

    admin_action_log(
        f'resolve_report_{action}', target_type='report', target_id=report.id,
        details=f'处理举报 #{report.id}: {action}, 备注: {note}',
        severity='info',
    )
    db.session.commit()
    flash('举报已处理。', 'success')
    return redirect(url_for('admin.reports'))
