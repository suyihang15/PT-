from flask import Blueprint

admin_bp = Blueprint('admin', __name__)

# Import route modules to register them on the blueprint
# Order matters for URL routing — more-specific routes first
from app.blueprints.admin import (
    routes_dashboard,
    routes_users,
    routes_torrents,
    routes_settings,
    routes_news,
    routes_reports,
    routes_logs,
    routes_categories,
    routes_medals,
    routes_bonus_shop,
    routes_invites,
    routes_hnr,
    routes_ip_management,
    routes_forum_mod,
    routes_stats,
    routes_announcements,
)
