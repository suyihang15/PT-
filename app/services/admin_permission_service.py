"""Admin permission system — granular permission definitions, decorator, and action logging."""

from functools import wraps
from flask import abort, request
from flask_login import current_user

# ── All available granular admin permissions ──────────────────────────
ADMIN_PERMISSIONS = {
    'can_manage_users': '用户管理 - 查看、编辑、封禁用户',
    'can_manage_torrents': '种子管理 - 编辑、删除、设置促销',
    'can_manage_forums': '论坛管理 - 编辑、锁定、删除帖子',
    'can_manage_bonus': '积分管理 - 手动调整积分、管理商品',
    'can_view_logs': '日志查看 - 查看操作日志和IP日志',
    'can_manage_settings': '站点设置 - 修改全局配置',
    'can_manage_invites': '邀请管理 - 生成、撤销邀请码',
    'can_ban_users': '封禁管理 - 封禁/解封用户',
    'can_view_ip': 'IP查看 - 查看用户IP和登录历史',
    'can_manage_categories': '分类管理 - 添加、编辑种子分类',
    'can_manage_medals': '勋章管理 - 创建和授予勋章',
    'can_manage_news': '公告管理 - 发布和编辑公告',
    'can_resolve_reports': '举报处理 - 处理用户举报',
    'can_manage_hnr': 'H&R管理 - 查看和处理H&R违规',
    'can_batch_operations': '批量操作 - 批量PM、批量封禁等',
    'can_manage_ip_bans': 'IP封禁 - 管理IP黑名单/白名单',
    'can_promote_users': '用户升级 - 手动升级/降级用户',
    'can_view_stats': '数据统计 - 查看站点流量统计',
}

# Pre-grouped permission sets for common roles
DEFAULT_MODERATOR_PERMISSIONS = [
    'can_manage_users',
    'can_manage_torrents',
    'can_manage_forums',
    'can_manage_news',
    'can_resolve_reports',
    'can_manage_hnr',
    'can_view_ip',
]

DEFAULT_ADMIN_PERMISSIONS = list(ADMIN_PERMISSIONS.keys())


def permission_required(permission_name):
    """Decorator: require a specific admin permission to access the route.

    Sysop role always has all permissions implicitly.
    Falls back to role-based check if no granular permissions are set.
    """
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            # Sysop bypasses all permission checks
            if current_user.role == 'Sysop':
                return f(*args, **kwargs)
            # Check granular permission
            if current_user.has_permission(permission_name):
                return f(*args, **kwargs)
            abort(403)
        return wrapped
    return decorator


def any_permission_required(*permission_names):
    """Decorator: require at least one of the given permissions."""
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if current_user.role == 'Sysop':
                return f(*args, **kwargs)
            for perm in permission_names:
                if current_user.has_permission(perm):
                    return f(*args, **kwargs)
            abort(403)
        return wrapped
    return decorator


def admin_action_log(action, target_type=None, target_id=None,
                     details=None, related_user_id=None,
                     old_value=None, new_value=None,
                     severity='info'):
    """Log an admin action to the database.

    Returns the Log object (already added to session, but NOT committed).
    Caller should commit the session.
    """
    from app.extensions import db
    from app.models.system import Log

    log = Log(
        user_id=current_user.id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        details=details,
        ip=request.remote_addr,
        severity=severity,
        related_user_id=related_user_id,
        old_value=old_value,
        new_value=new_value,
    )
    db.session.add(log)
    return log


def get_permission_description(permission_name):
    """Get the Chinese description of a permission."""
    return ADMIN_PERMISSIONS.get(permission_name, permission_name)


def get_permission_groups():
    """Return permissions grouped by category for UI display."""
    return {
        '用户与社区': [
            'can_manage_users', 'can_ban_users', 'can_promote_users',
            'can_manage_invites', 'can_batch_operations',
        ],
        '内容管理': [
            'can_manage_torrents', 'can_manage_categories',
            'can_manage_forums', 'can_manage_news',
            'can_manage_medals', 'can_resolve_reports',
        ],
        '安全与监控': [
            'can_view_ip', 'can_manage_ip_bans',
            'can_view_logs', 'can_manage_hnr',
            'can_view_stats',
        ],
        '系统配置': [
            'can_manage_settings', 'can_manage_bonus',
        ],
    }
