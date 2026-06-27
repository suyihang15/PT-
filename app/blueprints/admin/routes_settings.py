"""Site settings management."""

from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.extensions import db
from app.blueprints.admin import admin_bp
from app.models.system import SiteSetting
from app.models.admin import UserClass
from app.helpers import permission_required, admin_action_log


@admin_bp.route('/settings', methods=['GET', 'POST'])
@login_required
@permission_required('can_manage_settings')
def settings():
    """Site-wide settings management."""
    if request.method == 'POST':
        section = request.form.get('section', 'basic')

        if section == 'basic':
            settings_map = {
                'site_name': ('string', '站点名称'),
                'site_description': ('string', '站点描述'),
                'invite_only': ('bool', '是否仅允许邀请注册'),
                'register_open': ('bool', '是否开放注册'),
                'maintenance_mode': ('bool', '维护模式'),
                'maintenance_message': ('string', '维护模式消息'),
            }
        elif section == 'tracker':
            settings_map = {
                'announce_interval': ('int', 'Tracker汇报间隔(秒)'),
                'announce_min_interval': ('int', '最小汇报间隔(秒)'),
                'peer_expire_seconds': ('int', 'Peer过期时间(秒)'),
                'peer_limit': ('int', '最大返回Peer数'),
            }
        elif section == 'ratio':
            settings_map = {
                'min_ratio_to_download': ('float', '最低下载分享率'),
                'hnr_min_seed_hours': ('int', 'H&R最低做种时间(小时)'),
                'hnr_min_ratio': ('float', 'H&R最低分享率'),
                'hnr_grace_hours': ('int', 'H&R豁免期(小时)'),
                'default_bonus_per_hour': ('float', '默认积分率(每小时)'),
            }
        elif section == 'user_class':
            # Handled separately via UserClass routes
            pass
        else:
            flash('未知设置分类。', 'danger')
            return redirect(url_for('admin.settings'))

        for key, (vtype, desc) in settings_map.items():
            if key in request.form:
                val = request.form[key]
                if vtype == 'bool':
                    val = 'true' if val in ('true', '1', 'on', 'yes') else 'false'
                SiteSetting.set(key, val, value_type=vtype, description=desc)

        admin_action_log(
            'update_settings', target_type='setting',
            details=f'更新站点设置 (分类: {section})',
            severity='warning',
        )
        db.session.commit()
        flash('设置已保存。', 'success')
        return redirect(url_for('admin.settings'))

    settings_list = SiteSetting.query.order_by(SiteSetting.key).all()
    return render_template('admin/settings.html',
                           title='站点设置',
                           settings_list=settings_list)
