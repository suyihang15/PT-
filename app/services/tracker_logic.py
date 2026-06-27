"""Tracker announce logic - processes BT announce requests."""

import struct
import socket
import logging
from datetime import datetime, timezone, timedelta
from flask import current_app
from app.extensions import db
from app.models.torrent import Torrent
from app.models.tracker import Peer, Snatch
from app.services.bencode_service import bencode_encode

logger = logging.getLogger(__name__)


def build_error_response(message):
    """Build a bencoded error response."""
    data = {b'failure reason': message.encode('utf-8')}
    return bencode_encode(data), 200, {'Content-Type': 'text/plain'}


def build_compact_peer_list(peers):
    """Build compact 6-byte-per-peer format (4 bytes IP + 2 bytes port)."""
    compact = b''
    for peer in peers:
        try:
            ip_bytes = socket.inet_aton(peer.ip)
            port_bytes = struct.pack('!H', peer.port)
            compact += ip_bytes + port_bytes
        except OSError:
            continue
    return compact


def build_peer_dict_list(peers):
    """Build non-compact peer list (list of dicts with peer id, ip, port)."""
    result = []
    for peer in peers:
        peer_dict = {
            b'peer id': peer.peer_id.encode('utf-8') if peer.peer_id else b'',
            b'ip': peer.ip.encode('utf-8'),
            b'port': peer.port,
        }
        result.append(peer_dict)
    return result


def process_announce(user, torrent, params):
    """Process a BT announce request and return bencoded response."""
    peer_id = params.get('peer_id', '')
    ip = params.get('ip', '0.0.0.0')
    port = params.get('port', 0)
    uploaded = params.get('uploaded', 0)
    downloaded = params.get('downloaded', 0)
    left = params.get('left', 0)
    event = params.get('event', '')
    numwant = params.get('numwant', 50)
    compact = params.get('compact', 1)
    user_agent = params.get('user_agent', '')
    key = params.get('key', '')

    now = datetime.now(timezone.utc)
    is_seeder = (left == 0)

    # Find or create peer entry
    existing_peer = Peer.query.filter_by(
        user_id=user.id,
        torrent_id=torrent.id,
        peer_id=peer_id,
    ).first()

    if existing_peer:
        # Update existing peer
        delta_up = max(0, uploaded - existing_peer.uploaded)
        delta_down = max(0, downloaded - existing_peer.downloaded)

        existing_peer.uploaded = uploaded
        existing_peer.downloaded = downloaded
        existing_peer.left = left
        existing_peer.seeder = is_seeder
        existing_peer.ip = ip
        existing_peer.port = port
        existing_peer.user_agent = user_agent
        existing_peer.last_announce_at = now
    else:
        # New peer
        delta_up = uploaded
        delta_down = downloaded

        existing_peer = Peer(
            user_id=user.id,
            torrent_id=torrent.id,
            info_hash=torrent.info_hash,
            peer_id=peer_id,
            ip=ip,
            port=port,
            uploaded=uploaded,
            downloaded=downloaded,
            left=left,
            seeder=is_seeder,
            user_agent=user_agent,
            key=key,
            last_announce_at=now,
        )
        db.session.add(existing_peer)

    # Apply promotional flags
    effective_up = delta_up
    effective_down = delta_down

    if torrent.is_freeleech:
        effective_down = 0
    if torrent.is_double_upload:
        effective_up *= 2
    if torrent.is_half_download:
        effective_down //= 2

    # Update user stats
    user.uploaded += effective_up
    user.real_uploaded += delta_up
    user.downloaded += effective_down
    user.real_downloaded += delta_down
    user.uploaded_today += effective_up
    user.downloaded_today += effective_down
    user.last_announce_at = now
    user.last_ip = ip

    # Update snatch record
    snatch = Snatch.query.filter_by(user_id=user.id, torrent_id=torrent.id).first()
    if not snatch:
        snatch = Snatch(user_id=user.id, torrent_id=torrent.id)
        db.session.add(snatch)
        user.snatched_count += 1

    snatch.uploaded += effective_up
    snatch.downloaded += effective_down
    snatch.left = left
    snatch.last_action_at = now

    # Track seed/leech time
    if is_seeder:
        snatch.seed_time += int((now - snatch.last_action_at).total_seconds()) if snatch.last_action_at else 0
        user.seeding_count += 1
    else:
        snatch.leech_time += int((now - snatch.last_action_at).total_seconds()) if snatch.last_action_at else 0
        user.leeching_count += 1

    # Handle BT events
    if event == 'completed':
        snatch.finished = True
        snatch.completed_at = now
        torrent.times_completed += 1
        user.completed_count += 1

    if event == 'stopped':
        # Remove peer entry
        db.session.delete(existing_peer)
        if is_seeder:
            user.seeding_count = max(0, user.seeding_count - 1)
        else:
            user.leeching_count = max(0, user.leeching_count - 1)

    db.session.commit()

    # Get peer list for response
    if event != 'stopped':
        cutoff = now - timedelta(seconds=current_app.config.get('ANNOUNCE_INTERVAL', 1800))
        peers_query = Peer.query.filter(
            Peer.torrent_id == torrent.id,
            Peer.last_announce_at >= cutoff,
            Peer.id != existing_peer.id,
        ).limit(numwant).all()

        # Build peer list
        if compact:
            peers_data = build_compact_peer_list(peers_query)
        else:
            peers_data = build_peer_dict_list(peers_query)
    else:
        peers_data = b'' if compact else []

    # Build response
    interval = current_app.config.get('ANNOUNCE_INTERVAL', 1800)
    min_interval = current_app.config.get('ANNOUNCE_MIN_INTERVAL', 900)

    response = {
        b'interval': interval,
        b'min interval': min_interval,
        b'tracker id': b'BT-01',
        b'complete': torrent.seeders,
        b'incomplete': torrent.leechers,
    }

    if compact:
        response[b'peers'] = peers_data
    else:
        response[b'peers'] = peers_data

    return bencode_encode(response), 200, {'Content-Type': 'text/plain'}
