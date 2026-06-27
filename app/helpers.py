import os
from functools import wraps
from datetime import datetime, timezone, timedelta
from flask import abort, request, url_for
from flask_login import current_user
from markupsafe import Markup

# Role hierarchy for permission checks
ROLE_HIERARCHY = {
    'User': 0,
    'PowerUser': 1,
    'VIP': 2,
    'Moderator': 3,
    'Admin': 4,
    'Sysop': 5,
}

ROLE_DISPLAY = {
    'User': '普通用户',
    'PowerUser': '高级用户',
    'VIP': 'VIP会员',
    'Moderator': '版主',
    'Admin': '管理员',
    'Sysop': '系统管理员',
}

# Re-export permission system for convenience
from app.services.admin_permission_service import (
    ADMIN_PERMISSIONS,
    permission_required,
    any_permission_required,
    admin_action_log,
    get_permission_description,
    get_permission_groups,
    DEFAULT_MODERATOR_PERMISSIONS,
    DEFAULT_ADMIN_PERMISSIONS,
)


def role_required(min_role):
    """Decorator to require a minimum role for access."""
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            user_level = ROLE_HIERARCHY.get(current_user.role, 0)
            required_level = ROLE_HIERARCHY.get(min_role, 5)
            if user_level < required_level:
                abort(403)
            return f(*args, **kwargs)
        return wrapped
    return decorator


def format_bytes(size, precision=2):
    """Format bytes to human-readable string."""
    if size is None or size == 0:
        return '0 B'
    size = float(size)
    suffixes = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
    i = 0
    while size >= 1024 and i < len(suffixes) - 1:
        size /= 1024
        i += 1
    return f'{size:.{precision}f} {suffixes[i]}'


def format_ratio(ratio):
    """Format ratio for display."""
    if ratio == float('inf'):
        return '∞'
    if ratio is None:
        return '---'
    return f'{ratio:.3f}'


def format_ratio_class(ratio):
    """Return CSS class for ratio coloring."""
    if ratio == float('inf'):
        return 'text-success'
    if ratio is None:
        return 'text-muted'
    if ratio >= 2.0:
        return 'text-success'
    if ratio >= 1.0:
        return 'text-primary'
    if ratio >= 0.5:
        return 'text-warning'
    return 'text-danger'


def time_ago(dt):
    """Return a human-readable 'time ago' string."""
    if dt is None:
        return '从未'
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    diff = now - dt
    seconds = int(diff.total_seconds())

    if seconds < 10:
        return '刚刚'
    if seconds < 60:
        return f'{seconds} 秒前'
    minutes = seconds // 60
    if minutes < 60:
        return f'{minutes} 分钟前'
    hours = minutes // 60
    if hours < 24:
        return f'{hours} 小时前'
    days = hours // 24
    if days < 30:
        return f'{days} 天前'
    months = days // 30
    if months < 12:
        return f'{months} 个月前'
    years = months // 12
    return f'{years} 年前'


def format_duration(seconds):
    """Format seconds to human-readable duration."""
    if seconds is None or seconds == 0:
        return '0 秒'
    seconds = int(seconds)
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    parts = []
    if days > 0:
        parts.append(f'{days} 天')
    if hours > 0:
        parts.append(f'{hours} 小时')
    if minutes > 0:
        parts.append(f'{minutes} 分')
    if seconds > 0 and not parts:
        parts.append(f'{seconds} 秒')
    return ' '.join(parts)


def get_quality_badge(quality):
    """Return Bootstrap badge class for quality."""
    badges = {
        '2160p': 'badge-danger',
        '1080p': 'badge-success',
        '720p': 'badge-primary',
        '480p': 'badge-secondary',
        '4K': 'badge-danger',
        '8K': 'badge-dark',
    }
    return badges.get(quality, 'badge-info')


def nl2br(text):
    """Convert newlines to <br> tags."""
    if text is None:
        return ''
    from markupsafe import Markup, escape
    text = escape(text)
    return Markup(text.replace('\n', '<br>\n'))


def register_template_filters(app):
    """Register custom Jinja2 template filters."""
    app.jinja_env.filters['format_bytes'] = format_bytes
    app.jinja_env.filters['format_ratio'] = format_ratio
    app.jinja_env.filters['format_ratio_class'] = format_ratio_class
    app.jinja_env.filters['time_ago'] = time_ago
    app.jinja_env.filters['format_duration'] = format_duration
    app.jinja_env.filters['nl2br'] = nl2br


def register_context_processors(app):
    """Register template context processors."""
    from app.models.system import SiteSetting
    from app.models.message import PrivateMessage
    from app.extensions import db

    @app.context_processor
    def inject_globals():
        ctx = {
            'site_name': 'BT种子管理系统',
            'current_year': datetime.now().year,
            'unread_pm_count': 0,
        }
        if current_user.is_authenticated:
            ctx['unread_pm_count'] = PrivateMessage.query.filter_by(
                receiver_id=current_user.id,
                is_read=False,
                receiver_deleted=False,
            ).count()
        return ctx


def register_error_handlers(app):
    """Register custom error pages."""
    from flask import render_template

    @app.errorhandler(400)
    def bad_request(e):
        return render_template('errors/400.html'), 400

    @app.errorhandler(403)
    def forbidden(e):
        return render_template('errors/403.html'), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_error(e):
        return render_template('errors/500.html'), 500
