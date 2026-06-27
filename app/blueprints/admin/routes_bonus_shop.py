"""Bonus shop management routes."""

from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.extensions import db
from app.blueprints.admin import admin_bp
from app.models.bonus import BonusShopItem, SeedBonusLog
from app.models.user import User
from app.helpers import permission_required, admin_action_log
from decimal import Decimal


@admin_bp.route('/bonus-shop')
@login_required
@permission_required('can_manage_bonus')
def bonus_shop():
    """Bonus shop item management."""
    items = BonusShopItem.query.order_by(BonusShopItem.created_at.desc()).all()
    return render_template('admin/bonus_shop.html', title='积分商店管理', items=items)


@admin_bp.route('/bonus-shop/add', methods=['GET', 'POST'])
@login_required
@permission_required('can_manage_bonus')
def bonus_shop_add():
    """Add a new shop item."""
    if request.method == 'POST':
        item = BonusShopItem(
            name=request.form.get('name', ''),
            description=request.form.get('description', ''),
            price=int(request.form.get('price', 0)),
            stock=request.form.get('stock', type=int),
            effect_type=request.form.get('effect_type', ''),
            effect_value=request.form.get('effect_value', '{}'),
            icon=request.form.get('icon', ''),
            is_active='is_active' in request.form,
            min_role=request.form.get('min_role', 'User'),
            max_purchases_per_user=request.form.get('max_purchases_per_user', type=int),
        )
        db.session.add(item)
        admin_action_log('create_shop_item', target_type='bonus_shop_item', details=f'创建商品: {item.name}', severity='info')
        db.session.commit()
        flash(f'商品 {item.name} 已创建。', 'success')
        return redirect(url_for('admin.bonus_shop'))
    return render_template('admin/bonus_shop_edit.html', title='添加商品', item=None)


@admin_bp.route('/bonus-shop/<int:item_id>/edit', methods=['GET', 'POST'])
@login_required
@permission_required('can_manage_bonus')
def bonus_shop_edit(item_id):
    """Edit a shop item."""
    item = BonusShopItem.query.get_or_404(item_id)
    if request.method == 'POST':
        item.name = request.form.get('name', item.name)
        item.description = request.form.get('description', item.description)
        item.price = int(request.form.get('price', item.price))
        item.stock = request.form.get('stock', type=int)
        item.effect_type = request.form.get('effect_type', item.effect_type)
        item.effect_value = request.form.get('effect_value', item.effect_value)
        item.icon = request.form.get('icon', item.icon)
        item.is_active = 'is_active' in request.form
        item.min_role = request.form.get('min_role', item.min_role)
        item.max_purchases_per_user = request.form.get('max_purchases_per_user', type=int)
        admin_action_log('edit_shop_item', target_type='bonus_shop_item', target_id=item.id, details=f'编辑商品: {item.name}', severity='info')
        db.session.commit()
        flash(f'商品 {item.name} 已更新。', 'success')
        return redirect(url_for('admin.bonus_shop'))
    return render_template('admin/bonus_shop_edit.html', title=f'编辑商品 {item.name}', item=item)


@admin_bp.route('/bonus-shop/<int:item_id>/delete', methods=['POST'])
@login_required
@permission_required('can_manage_bonus')
def bonus_shop_delete(item_id):
    """Delete a shop item."""
    item = BonusShopItem.query.get_or_404(item_id)
    admin_action_log('delete_shop_item', target_type='bonus_shop_item', target_id=item.id, details=f'删除商品: {item.name}', severity='danger')
    db.session.delete(item)
    db.session.commit()
    flash(f'商品 {item.name} 已删除。', 'success')
    return redirect(url_for('admin.bonus_shop'))


@admin_bp.route('/bonus-adjust', methods=['GET', 'POST'])
@login_required
@permission_required('can_manage_bonus')
def bonus_adjust():
    """Manually adjust a user's seed bonus."""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        points = request.form.get('points', type=float)
        reason = request.form.get('reason', '管理员手动调整')

        if not username or not points:
            flash('请输入用户名和积分数量。', 'danger')
            return redirect(url_for('admin.bonus_adjust'))

        user = User.query.filter_by(username=username).first()
        if not user:
            flash('未找到该用户。', 'danger')
            return redirect(url_for('admin.bonus_adjust'))

        old_bonus = user.seed_bonus or Decimal('0')
        user.seed_bonus = old_bonus + Decimal(str(points))

        log_entry = SeedBonusLog(
            user_id=user.id,
            points_change=Decimal(str(points)),
            reason='admin_adjust',
            description=reason,
        )
        db.session.add(log_entry)
        admin_action_log('adjust_bonus', target_type='user', target_id=user.id,
                         details=f'调整用户 {user.username} 积分 {points:+} ({old_bonus} -> {user.seed_bonus}): {reason}',
                         related_user_id=user.id, severity='warning')
        db.session.commit()
        flash(f'已调整用户 {username} 的积分 ({points:+})，当前积分: {user.seed_bonus}。', 'success')
        return redirect(url_for('admin.bonus_adjust'))

    return render_template('admin/bonus_adjust.html', title='积分调整')
