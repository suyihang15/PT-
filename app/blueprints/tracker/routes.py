from flask import Blueprint, request, jsonify, abort, current_app
from flask_login import current_user
from app.extensions import db
from app.models.user import User
from app.models.torrent import Torrent
from app.models.tracker import Peer, Snatch
from datetime import datetime, timezone, timedelta
import logging

logger = logging.getLogger(__name__)
tracker_bp = Blueprint('tracker', __name__)


@tracker_bp.route('/announce/<passkey>')
def announce(passkey):
    """BitTorrent announce endpoint."""
    from app.services.tracker_logic import process_announce, build_error_response

    # Resolve passkey to user
    user = db.session.execute(db.select(User).filter_by(passkey=passkey)).scalar_one_or_none()

    if not user:
        return build_error_response('passkey not found')

    if user.is_banned:
        return build_error_response('user is banned')

    # Parse required parameters
    info_hash = request.args.get('info_hash', '')
    peer_id = request.args.get('peer_id', '')
    port = request.args.get('port', 0, type=int)
    uploaded = request.args.get('uploaded', 0, type=int)
    downloaded = request.args.get('downloaded', 0, type=int)
    left = request.args.get('left', 0, type=int)
    event = request.args.get('event', '')
    ip = request.args.get('ip', request.remote_addr)
    numwant = request.args.get('numwant', 50, type=int)
    compact = request.args.get('compact', 1, type=int)

    if not info_hash:
        return build_error_response('missing info_hash')

    # URL decode info_hash (could be raw hex or URL-encoded hex)
    from urllib.parse import unquote
    info_hash = unquote(info_hash)

    # Find torrent
    torrent = db.session.execute(
        db.select(Torrent).filter_by(info_hash=info_hash.upper())
    ).scalar_one_or_none()

    if not torrent:
        return build_error_response('torrent not registered')

    if torrent.banned:
        return build_error_response('torrent is banned')

    # Process announce
    result = process_announce(user, torrent, {
        'peer_id': peer_id,
        'ip': ip,
        'port': port,
        'uploaded': uploaded,
        'downloaded': downloaded,
        'left': left,
        'event': event,
        'numwant': min(numwant, 50),
        'compact': compact,
        'user_agent': request.headers.get('User-Agent', ''),
        'key': request.args.get('key', ''),
    })

    return result


@tracker_bp.route('/scrape')
def scrape():
    """BitTorrent scrape endpoint."""
    from app.services.bencode_service import bencode_encode

    info_hashes = request.args.getlist('info_hash')

    if not info_hashes:
        return bencode_encode({b'files': {}}), 200, {'Content-Type': 'text/plain'}

    from urllib.parse import unquote
    files = {}
    for ih in info_hashes[:100]:  # Limit to 100 hashes
        ih = unquote(ih).upper()
        torrent = db.session.execute(
            db.select(Torrent).filter_by(info_hash=ih)
        ).scalar_one_or_none()

        if torrent:
            files[ih.encode()] = {
                b'complete': torrent.seeders,
                b'incomplete': torrent.leechers,
                b'downloaded': torrent.times_completed,
            }

    response_data = {b'files': files}
    return bencode_encode(response_data), 200, {'Content-Type': 'text/plain'}
