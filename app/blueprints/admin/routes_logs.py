"""Activity log viewer routes."""

from flask import render_template, request
from flask_login import login_required
from app.extensions import db
from app.blueprints.admin import admin_bp
from app.models.system import Log
from app.models.admin import IpLog
from app.helpers import permission_required


@admin_bp.route('/logs')
@login_required
@permission_required('can_view_logs')
def logs():
    """Admin activity log viewer."""
    page = request.args.get('page', 1, type=int)
    severity = request.args.get('severity', '')
    action = request.args.get('action', '')
    user_id = request.args.get('user_id', type=int)

    query = Log.query
    if severity:
        query = query.filter(Log.severity == severity)
    if action:
        query = query.filter(Log.action.ilike(f'%{action}%'))
    if user_id:
        query = query.filter(Log.user_id == user_id)

    paginated = query.order_by(Log.created_at.desc())\
        .paginate(page=page, per_page=50, error_out=False)

    # Get distinct actions for filter dropdown
    actions = [row[0] for row in db.session.query(Log.action).distinct().limit(50).all()]

    return render_template('admin/logs.html',
                           title='操作日志',
                           paginated=paginated,
                           actions=actions,
                           search_params=request.args)


@admin_bp.route('/logs/ip')
@login_required
@permission_required('can_view_logs')
def ip_logs():
    """IP activity log viewer."""
    page = request.args.get('page', 1, type=int)
    ip = request.args.get('ip', '')
    event_type = request.args.get('event_type', '')
    user_id = request.args.get('user_id', type=int)

    query = IpLog.query
    if ip:
        query = query.filter(IpLog.ip.ilike(f'%{ip}%'))
    if event_type:
        query = query.filter(IpLog.event_type == event_type)
    if user_id:
        query = query.filter(IpLog.user_id == user_id)

    paginated = query.order_by(IpLog.created_at.desc())\
        .paginate(page=page, per_page=50, error_out=False)

    return render_template('admin/ip_logs.html',
                           title='IP日志',
                           paginated=paginated,
                           search_params=request.args)
