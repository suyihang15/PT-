"""qBittorrent integration — API client for stat syncing."""

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def get_qb_session(config):
    """Create an authenticated requests session for qBittorrent Web API."""
    import requests
    session = requests.Session()
    protocol = 'https' if config.use_ssl else 'http'
    base_url = f'{protocol}://{config.host}:{config.port}'

    try:
        # Login
        resp = session.post(
            f'{base_url}/api/v2/auth/login',
            data={'username': config.username, 'password': config.password},
            timeout=10,
        )
        if resp.status_code != 200 or resp.text == 'Fails.':
            return None, 'Login failed: invalid credentials'
    except requests.exceptions.RequestException as e:
        return None, f'Connection failed: {str(e)}'

    return session, base_url


def test_connection(config):
    """Test if a qBittorrent config is valid and reachable."""
    session, error = get_qb_session(config)
    if session:
        session.post(f'{session.base_url}/api/v2/auth/logout')  # type: ignore
        return True, None
    return False, error


def fetch_torrent_list(config):
    """Fetch all torrents from a qBittorrent instance."""
    session, error_or_url = get_qb_session(config)
    if session is None:
        return None, error_or_url

    base_url = error_or_url
    try:
        resp = session.get(
            f'{base_url}/api/v2/torrents/info',
            timeout=30,
        )
        torrents = resp.json()
        session.post(f'{base_url}/api/v2/auth/logout')
        return torrents, None
    except Exception as e:
        return None, str(e)


def sync_user_stats(user):
    """Sync one user's qBittorrent stats to the site.

    Returns (success, message).
    """
    from app.models.qbittorrent import QBittorrentConfig, QBittorrentSyncLog
    from app.extensions import db

    config = QBittorrentConfig.query.filter_by(user_id=user.id, is_active=True).first()
    if not config:
        return False, 'No active QB config'

    torrents, error = fetch_torrent_list(config)
    if error:
        config.last_error = error
        db.session.commit()
        return False, error

    total_upload = 0
    total_download = 0

    for t in torrents:
        uploaded = t.get('uploaded', 0)
        downloaded = t.get('downloaded', 0)
        total_upload += uploaded
        total_download += downloaded

        # Log each torrent sync
        log_entry = QBittorrentSyncLog(
            user_id=user.id,
            torrent_hash=t.get('hash', ''),
            torrent_name=t.get('name', ''),
            upload_bytes=uploaded,
            download_bytes=downloaded,
            status=t.get('state', ''),
            sync_type='report',
        )
        db.session.add(log_entry)

    # Update user stats (additive from QB)
    user.uploaded = (user.uploaded or 0) + total_upload
    user.downloaded = (user.downloaded or 0) + total_download
    config.last_sync_at = datetime.now(timezone.utc)
    config.last_error = None

    db.session.commit()
    return True, f'Synced {len(torrents)} torrents, +{total_upload} upload, +{total_download} download'


def qb_sync_all_users():
    """Sync QB stats for all users with active configs. Called by scheduler."""
    from app.models.qbittorrent import QBittorrentConfig
    from app.models.user import User
    from app.extensions import db

    configs = QBittorrentConfig.query.filter_by(is_active=True, auto_report=True).all()
    success_count = 0
    fail_count = 0

    for config in configs:
        user = User.query.get(config.user_id)
        if not user or not user.is_active or user.is_banned:
            continue
        try:
            ok, _ = sync_user_stats(user)
            if ok:
                success_count += 1
            else:
                fail_count += 1
        except Exception as e:
            config.last_error = str(e)
            fail_count += 1

    db.session.commit()
    logger.info(f"QB sync: {success_count} success, {fail_count} failed")
    return success_count, fail_count
