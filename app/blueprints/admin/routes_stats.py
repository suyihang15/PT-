"""Traffic statistics routes."""

from flask import render_template, jsonify, request
from flask_login import login_required
from app.extensions import db
from app.blueprints.admin import admin_bp
from app.models.tracker import Snatch, Peer
from app.models.torrent import Torrent
from app.models.user import User
from app.helpers import permission_required
from datetime import datetime, timezone, timedelta


@admin_bp.route('/stats')
@login_required
@permission_required('can_view_stats')
def stats():
    """Statistics dashboard."""
    total_upload = db.session.query(db.func.sum(User.uploaded)).scalar() or 0
    total_download = db.session.query(db.func.sum(User.downloaded)).scalar() or 0
    total_data = total_upload + total_download

    return render_template('admin/stats.html',
                           title='数据统计',
                           total_upload=total_upload,
                           total_download=total_download,
                           total_data=total_data,
                           total_users=User.query.count(),
                           total_torrents=Torrent.query.count(),
                           total_snatches=Snatch.query.count(),
                           active_peers=Peer.query.count())


@admin_bp.route('/stats/traffic/data')
@login_required
@permission_required('can_view_stats')
def stats_traffic_data():
    """JSON API: Daily traffic data for charts."""
    period = request.args.get('period', 'daily')
    days = request.args.get('days', 30, type=int)

    if period == 'daily':
        # Group Peer data by day (last N days)
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        # Simpler approach: return snatch data grouped by date
        rows = db.session.query(
            db.func.date(Snatch.last_action_at).label('date'),
            db.func.sum(Snatch.uploaded).label('upload'),
            db.func.sum(Snatch.downloaded).label('download'),
        ).filter(
            Snatch.last_action_at >= cutoff
        ).group_by(
            db.func.date(Snatch.last_action_at)
        ).order_by('date').all()

        labels = [str(row.date) for row in rows]
        upload_data = [int(row.upload or 0) for row in rows]
        download_data = [int(row.download or 0) for row in rows]

    elif period == 'weekly':
        # Last 12 weeks
        cutoff = datetime.now(timezone.utc) - timedelta(weeks=12)
        rows = db.session.query(
            db.func.strftime('%Y-W%W', Snatch.last_action_at).label('week'),
            db.func.sum(Snatch.uploaded).label('upload'),
            db.func.sum(Snatch.downloaded).label('download'),
        ).filter(
            Snatch.last_action_at >= cutoff
        ).group_by('week').order_by('week').all()

        labels = [f'第{row.week.split("-W")[1]}周' for row in rows]
        upload_data = [int(row.upload or 0) for row in rows]
        download_data = [int(row.download or 0) for row in rows]

    elif period == 'monthly':
        # Last 12 months
        cutoff = datetime.now(timezone.utc) - timedelta(days=365)
        rows = db.session.query(
            db.func.strftime('%Y-%m', Snatch.last_action_at).label('month'),
            db.func.sum(Snatch.uploaded).label('upload'),
            db.func.sum(Snatch.downloaded).label('download'),
        ).filter(
            Snatch.last_action_at >= cutoff
        ).group_by('month').order_by('month').all()

        labels = [row.month for row in rows]
        upload_data = [int(row.upload or 0) for row in rows]
        download_data = [int(row.download or 0) for row in rows]

    else:
        return jsonify({'error': 'Invalid period'}), 400

    return jsonify({
        'labels': labels,
        'upload': upload_data,
        'download': download_data,
    })
