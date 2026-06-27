from flask import Blueprint, jsonify, request
from app.extensions import db
from app.models.torrent import Torrent
from app.models.user import User
from app.helpers import format_bytes

api_bp = Blueprint('api', __name__)


@api_bp.route('/search/autocomplete')
def search_autocomplete():
    """Search autocomplete endpoint."""
    q = request.args.get('q', '').strip()
    if len(q) < 2:
        return jsonify({'results': []})

    torrents = Torrent.query.filter_by(visible=True, banned=False)\
        .filter(Torrent.name.ilike(f'%{q}%'))\
        .order_by(Torrent.seeders.desc()).limit(8).all()

    results = [{
        'id': t.id,
        'name': t.name[:80],
        'size': format_bytes(t.size),
    } for t in torrents]

    return jsonify({'results': results})


@api_bp.route('/stats')
def stats():
    """Site stats JSON endpoint."""
    return jsonify({
        'total_torrents': Torrent.query.filter_by(visible=True, banned=False).count(),
        'total_seeders': db.session.query(db.func.sum(Torrent.seeders)).scalar() or 0,
        'total_leechers': db.session.query(db.func.sum(Torrent.leechers)).scalar() or 0,
        'total_users': User.query.filter_by(is_active=True).count(),
    })


@api_bp.route('/user/check-username')
def check_username():
    """Check username availability."""
    username = request.args.get('username', '').strip()
    if not username:
        return jsonify({'available': False})
    user = User.query.filter_by(username=username).first()
    return jsonify({'available': user is None})


@api_bp.route('/user/check-email')
def check_email():
    """Check email availability."""
    email = request.args.get('email', '').strip()
    if not email:
        return jsonify({'available': False})
    user = User.query.filter_by(email=email).first()
    return jsonify({'available': user is None})
