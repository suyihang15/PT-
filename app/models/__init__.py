# Import order matters for SQLAlchemy relationship resolution
from app.models.user import User, Invite, UserMedal
from app.models.system import SiteSetting, News, Report, Log, Medal, Warning, Announcement
from app.models.torrent import Category, Tag, TorrentTag, Torrent, File, Comment, Bookmark, Thank
from app.models.tracker import Peer, Snatch, HnrViolation
from app.models.bonus import SeedBonusRate, SeedBonusLog, BonusShopItem, BonusPurchase
from app.models.message import PrivateMessage
from app.models.forum import Forum, ForumTopic, ForumPost
from app.models.admin import BanLog, IpLog, IpBan, IpWhitelist, UserClass, PromotionLog
from app.models.qbittorrent import QBittorrentConfig, QBittorrentSyncLog

__all__ = [
    'User', 'Invite', 'UserMedal',
    'SiteSetting', 'News', 'Report', 'Log', 'Medal', 'Warning', 'Announcement',
    'Category', 'Tag', 'TorrentTag', 'Torrent', 'File', 'Comment', 'Bookmark', 'Thank',
    'Peer', 'Snatch', 'HnrViolation',
    'SeedBonusRate', 'SeedBonusLog', 'BonusShopItem', 'BonusPurchase',
    'PrivateMessage',
    'Forum', 'ForumTopic', 'ForumPost',
    'BanLog', 'IpLog', 'IpBan', 'IpWhitelist', 'UserClass', 'PromotionLog',
    'QBittorrentConfig', 'QBittorrentSyncLog',
]
