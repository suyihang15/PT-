from flask import Blueprint, Response, request, url_for
from app.extensions import db
from app.models.torrent import Torrent, Category
from app.models.user import User
from app.helpers import format_bytes
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

rss_bp = Blueprint('rss', __name__)


def build_rss_xml(torrents, title, description, passkey=None):
    """Build RSS 2.0 XML feed."""
    rss = ET.Element('rss', version='2.0')
    channel = ET.SubElement(rss, 'channel')
    ET.SubElement(channel, 'title').text = title
    ET.SubElement(channel, 'description').text = description
    ET.SubElement(channel, 'link').text = request.url_root

    for torrent in torrents:
        item = ET.SubElement(channel, 'item')
        ET.SubElement(item, 'title').text = torrent.name
        ET.SubElement(item, 'description').text = (
            f'Size: {format_bytes(torrent.size)} | '
            f'Seeders: {torrent.seeders} | '
            f'Leechers: {torrent.leechers}'
        )
        download_passkey = passkey or '%PASSKEY%'
        dl_url = request.url_root.rstrip('/') + url_for('torrent.download', torrent_id=torrent.id)
        ET.SubElement(item, 'enclosure', {
            'url': dl_url,
            'length': str(torrent.size),
            'type': 'application/x-bittorrent',
        })
        ET.SubElement(item, 'guid').text = torrent.info_hash
        if torrent.added_at:
            ET.SubElement(item, 'pubDate').text = torrent.added_at.strftime('%a, %d %b %Y %H:%M:%S +0000')

    return ET.tostring(rss, encoding='unicode')


@rss_bp.route('/')
def global_rss():
    """Global RSS feed of latest torrents."""
    torrents = Torrent.query.filter_by(visible=True, banned=False)\
        .order_by(Torrent.added_at.desc()).limit(50).all()
    xml = build_rss_xml(torrents, '最新种子', 'BT种子管理系统 - 最新种子列表')
    return Response(xml, mimetype='application/rss+xml')


@rss_bp.route('/<passkey>')
def personal_rss(passkey):
    """Personal RSS feed with passkey for auto-download."""
    user = User.query.filter_by(passkey=passkey).first()
    if not user:
        return Response('Invalid passkey', status=403)

    torrents = Torrent.query.filter_by(visible=True, banned=False)\
        .order_by(Torrent.added_at.desc()).limit(50).all()
    xml = build_rss_xml(torrents, '个性化种子列表', f'{user.username}的个人RSS', passkey=user.passkey)
    return Response(xml, mimetype='application/rss+xml')


@rss_bp.route('/category/<slug>')
def category_rss(slug):
    """Category-specific RSS feed."""
    category = Category.query.filter_by(slug=slug).first_or_404()
    torrents = Torrent.query.filter_by(category_id=category.id, visible=True, banned=False)\
        .order_by(Torrent.added_at.desc()).limit(50).all()
    xml = build_rss_xml(torrents, f'{category.name} - 最新种子', f'分类: {category.name}')
    return Response(xml, mimetype='application/rss+xml')
