"""News/Announcements management routes."""

from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.extensions import db
from app.blueprints.admin import admin_bp
from app.models.system import News
from app.helpers import permission_required, admin_action_log


@admin_bp.route('/news')
@login_required
@permission_required('can_manage_news')
def news_list():
    """News management list."""
    page = request.args.get('page', 1, type=int)
    paginated = News.query.order_by(News.created_at.desc())\
        .paginate(page=page, per_page=20, error_out=False)
    return render_template('admin/news_list.html',
                           title='新闻管理',
                           paginated=paginated)


@admin_bp.route('/news/create', methods=['GET', 'POST'])
@login_required
@permission_required('can_manage_news')
def news_create():
    """Create a news article."""
    if request.method == 'POST':
        article = News(
            title=request.form.get('title', ''),
            content=request.form.get('content', ''),
            content_html=request.form.get('content', ''),
            author_id=current_user.id,
            is_pinned='is_pinned' in request.form,
            is_published='is_published' in request.form,
        )
        db.session.add(article)
        admin_action_log(
            'create_news', target_type='news', target_id=article.id,
            details=f'发布新闻: {article.title[:50]}',
            severity='info',
        )
        db.session.commit()
        flash('新闻已发布。', 'success')
        return redirect(url_for('admin.news_list'))
    return render_template('admin/news_edit.html',
                           title='发布新闻',
                           article=None)


@admin_bp.route('/news/<int:news_id>/edit', methods=['GET', 'POST'])
@login_required
@permission_required('can_manage_news')
def news_edit(news_id):
    """Edit a news article."""
    article = News.query.get_or_404(news_id)
    if request.method == 'POST':
        article.title = request.form.get('title', article.title)
        article.content = request.form.get('content', article.content)
        article.content_html = request.form.get('content', article.content)
        article.is_pinned = 'is_pinned' in request.form
        article.is_published = 'is_published' in request.form
        admin_action_log(
            'edit_news', target_type='news', target_id=article.id,
            details=f'编辑新闻: {article.title[:50]}',
            severity='info',
        )
        db.session.commit()
        flash('新闻已更新。', 'success')
        return redirect(url_for('admin.news_list'))
    return render_template('admin/news_edit.html',
                           title=f'编辑新闻 {article.title[:30]}',
                           article=article)


@admin_bp.route('/news/<int:news_id>/delete', methods=['POST'])
@login_required
@permission_required('can_manage_news')
def news_delete(news_id):
    """Delete a news article."""
    article = News.query.get_or_404(news_id)
    admin_action_log(
        'delete_news', target_type='news', target_id=article.id,
        details=f'删除新闻: {article.title[:50]}',
        severity='danger',
    )
    db.session.delete(article)
    db.session.commit()
    flash('新闻已删除。', 'success')
    return redirect(url_for('admin.news_list'))
