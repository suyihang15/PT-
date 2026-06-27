"""Traffic statistics service — daily/weekly/monthly aggregates."""

from datetime import datetime, timezone, timedelta
from app.extensions import db


def get_daily_traffic(days=30):
    """Return daily upload/download aggregates for the last N days.

    Returns dict with labels (date strings), upload (bytes list), download (bytes list).
    """
    from app.models.tracker import Snatch

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
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

    return {'labels': labels, 'upload': upload_data, 'download': download_data}


def get_weekly_traffic(weeks=12):
    """Return weekly upload/download aggregates."""
    from app.models.tracker import Snatch

    cutoff = datetime.now(timezone.utc) - timedelta(weeks=weeks)
    rows = db.session.query(
        db.func.strftime('%Y-W%W', Snatch.last_action_at).label('week'),
        db.func.sum(Snatch.uploaded).label('upload'),
        db.func.sum(Snatch.downloaded).label('download'),
    ).filter(
        Snatch.last_action_at >= cutoff
    ).group_by('week').order_by('week').all()

    labels = []
    for row in rows:
        if row.week and '-W' in row.week:
            parts = row.week.split('-W')
            labels.append(f'第{parts[1]}周')
        else:
            labels.append(row.week or '?')

    upload_data = [int(row.upload or 0) for row in rows]
    download_data = [int(row.download or 0) for row in rows]

    return {'labels': labels, 'upload': upload_data, 'download': download_data}


def get_monthly_traffic(months=12):
    """Return monthly upload/download aggregates."""
    from app.models.tracker import Snatch

    cutoff = datetime.now(timezone.utc) - timedelta(days=months * 31)
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

    return {'labels': labels, 'upload': upload_data, 'download': download_data}


def get_site_summary():
    """Return total site-wide traffic statistics."""
    from app.models.user import User
    from app.models.torrent import Torrent
    from app.models.tracker import Snatch, Peer

    total_upload = db.session.query(db.func.sum(User.uploaded)).scalar() or 0
    total_download = db.session.query(db.func.sum(User.downloaded)).scalar() or 0

    return {
        'total_upload': total_upload,
        'total_download': total_download,
        'total_data': total_upload + total_download,
        'total_users': User.query.count(),
        'total_torrents': Torrent.query.count(),
        'total_snatches': Snatch.query.count(),
        'active_peers': Peer.query.count(),
    }
