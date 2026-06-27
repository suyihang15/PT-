"""Admin dashboard — overview and statistics."""

from flask import render_template, g
from flask_login import login_required, current_user
from app.extensions import db
from app.blueprints.admin import admin_bp
from app.models.user import User
from app.models.torrent import Torrent
from app.models.system import Report, Log
from app.models.tracker import Peer, HnrViolation
from app.helpers import role_required


@admin_bp.route('/')
@login_required
@role_required('Moderator')
def dashboard():
    """Admin dashboard with key statistics."""
    stats = {
        'total_users': User.query.count(),
        'active_users': User.query.filter_by(is_active=True).count(),
        'banned_users': User.query.filter_by(is_banned=True).count(),
        'total_torrents': Torrent.query.count(),
        'visible_torrents': Torrent.query.filter_by(visible=True).count(),
        'total_peers': Peer.query.count(),
        'active_seeders': Peer.query.filter_by(seeder=True).count(),
        'active_leechers': Peer.query.filter_by(seeder=False).count(),
        'pending_reports': Report.query.filter_by(resolved=False).count(),
        'pending_hnr': HnrViolation.query.filter_by(resolved=False).count(),
        'new_users_today': User.query.filter(
            db.func.date(User.registered_at) == db.func.date('now')
        ).count(),
        'new_torrents_today': Torrent.query.filter(
            db.func.date(Torrent.added_at) == db.func.date('now')
        ).count(),
    }

    # Recent activity
    recent_logs = Log.query.order_by(Log.created_at.desc()).limit(10).all()
    recent_users = User.query.order_by(User.registered_at.desc()).limit(5).all()

    # Pending reports count for sidebar badge
    g.pending_reports_count = stats['pending_reports']

    return render_template('admin/dashboard.html',
                           title='管理面板',
                           stats=stats,
                           recent_logs=recent_logs,
                           recent_users=recent_users)
