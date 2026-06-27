"""Category and tag management routes."""

from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.extensions import db
from app.blueprints.admin import admin_bp
from app.models.torrent import Category, Tag
from app.helpers import permission_required, admin_action_log


@admin_bp.route('/categories')
@login_required
@permission_required('can_manage_categories')
def categories():
    """Category management list."""
    cats = Category.query.order_by(Category.sort_order).all()
    return render_template('admin/categories.html', title='分类管理', categories=cats)


@admin_bp.route('/categories/add', methods=['GET', 'POST'])
@login_required
@permission_required('can_manage_categories')
def category_add():
    """Add a new category."""
    parents = Category.query.filter(Category.parent_id == None).order_by(Category.sort_order).all()
    if request.method == 'POST':
        cat = Category(
            name=request.form.get('name', ''),
            slug=request.form.get('slug', ''),
            sort_order=int(request.form.get('sort_order', 0)),
            icon=request.form.get('icon', ''),
            min_role_view=request.form.get('min_role_view', 'User'),
            parent_id=request.form.get('parent_id', type=int) or None,
        )
        db.session.add(cat)
        admin_action_log('create_category', target_type='category', details=f'创建分类: {cat.name}', severity='info')
        db.session.commit()
        flash(f'分类 {cat.name} 已创建。', 'success')
        return redirect(url_for('admin.categories'))
    return render_template('admin/category_edit.html', title='添加分类', category=None, parents=parents)


@admin_bp.route('/categories/<int:cat_id>/edit', methods=['GET', 'POST'])
@login_required
@permission_required('can_manage_categories')
def category_edit(cat_id):
    """Edit a category."""
    cat = Category.query.get_or_404(cat_id)
    parents = Category.query.filter(Category.parent_id == None, Category.id != cat.id).order_by(Category.sort_order).all()
    if request.method == 'POST':
        cat.name = request.form.get('name', cat.name)
        cat.slug = request.form.get('slug', cat.slug)
        cat.sort_order = int(request.form.get('sort_order', cat.sort_order))
        cat.icon = request.form.get('icon', cat.icon)
        cat.min_role_view = request.form.get('min_role_view', cat.min_role_view)
        cat.parent_id = request.form.get('parent_id', type=int) or None
        admin_action_log('edit_category', target_type='category', target_id=cat.id, details=f'编辑分类: {cat.name}', severity='info')
        db.session.commit()
        flash(f'分类 {cat.name} 已更新。', 'success')
        return redirect(url_for('admin.categories'))
    return render_template('admin/category_edit.html', title=f'编辑分类 {cat.name}', category=cat, parents=parents)


@admin_bp.route('/categories/<int:cat_id>/delete', methods=['POST'])
@login_required
@permission_required('can_manage_categories')
def category_delete(cat_id):
    """Delete a category."""
    cat = Category.query.get_or_404(cat_id)
    if cat.torrents.count() > 0:
        flash(f'分类 {cat.name} 下有 {cat.torrents.count()} 个种子，无法删除。', 'danger')
        return redirect(url_for('admin.categories'))
    admin_action_log('delete_category', target_type='category', target_id=cat.id, details=f'删除分类: {cat.name}', severity='danger')
    db.session.delete(cat)
    db.session.commit()
    flash(f'分类 {cat.name} 已删除。', 'success')
    return redirect(url_for('admin.categories'))


@admin_bp.route('/tags')
@login_required
@permission_required('can_manage_categories')
def tags():
    """Tag management list."""
    all_tags = Tag.query.order_by(Tag.sort_order).all()
    return render_template('admin/tags.html', title='标签管理', tags=all_tags)


@admin_bp.route('/tags/add', methods=['POST'])
@login_required
@permission_required('can_manage_categories')
def tag_add():
    """Add a new tag."""
    tag = Tag(
        name=request.form.get('name', ''),
        slug=request.form.get('slug', ''),
        color=request.form.get('color', '#6c757d'),
        sort_order=int(request.form.get('sort_order', 0)),
    )
    db.session.add(tag)
    admin_action_log('create_tag', target_type='tag', details=f'创建标签: {tag.name}', severity='info')
    db.session.commit()
    flash(f'标签 {tag.name} 已创建。', 'success')
    return redirect(url_for('admin.tags'))


@admin_bp.route('/tags/<int:tag_id>/edit', methods=['POST'])
@login_required
@permission_required('can_manage_categories')
def tag_edit(tag_id):
    """Edit a tag."""
    tag = Tag.query.get_or_404(tag_id)
    tag.name = request.form.get('name', tag.name)
    tag.slug = request.form.get('slug', tag.slug)
    tag.color = request.form.get('color', tag.color)
    tag.sort_order = int(request.form.get('sort_order', tag.sort_order))
    admin_action_log('edit_tag', target_type='tag', target_id=tag.id, details=f'编辑标签: {tag.name}', severity='info')
    db.session.commit()
    flash(f'标签 {tag.name} 已更新。', 'success')
    return redirect(url_for('admin.tags'))


@admin_bp.route('/tags/<int:tag_id>/delete', methods=['POST'])
@login_required
@permission_required('can_manage_categories')
def tag_delete(tag_id):
    """Delete a tag."""
    tag = Tag.query.get_or_404(tag_id)
    admin_action_log('delete_tag', target_type='tag', target_id=tag.id, details=f'删除标签: {tag.name}', severity='danger')
    db.session.delete(tag)
    db.session.commit()
    flash(f'标签 {tag.name} 已删除。', 'success')
    return redirect(url_for('admin.tags'))
