from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.extensions import db
from app.models.forum import Forum, ForumTopic, ForumPost
from app.helpers import role_required

forum_bp = Blueprint('forum', __name__)


@forum_bp.route('/')
def index():
    """Forum listing."""
    forums = Forum.query.order_by(Forum.sort_order).all()
    return render_template('forum/index.html', forums=forums)


@forum_bp.route('/<slug>')
def forum_view(slug):
    """View topics in a forum."""
    forum = Forum.query.filter_by(slug=slug).first_or_404()
    page = request.args.get('page', 1, type=int)
    paginated = ForumTopic.query.filter_by(forum_id=forum.id)\
        .order_by(ForumTopic.is_pinned.desc(), ForumTopic.last_post_at.desc().nullslast())\
        .paginate(page=page, per_page=25, error_out=False)
    return render_template('forum/forum.html', forum=forum, paginated=paginated)


@forum_bp.route('/<slug>/new', methods=['GET', 'POST'])
@login_required
def new_topic(slug):
    """Create a new topic."""
    forum = Forum.query.filter_by(slug=slug).first_or_404()
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        content = request.form.get('content', '').strip()
        if not title or not content:
            flash('标题和内容不能为空。', 'danger')
            return render_template('forum/new_topic.html', forum=forum)

        topic = ForumTopic(
            forum_id=forum.id,
            user_id=current_user.id,
            title=title,
        )
        db.session.add(topic)
        db.session.flush()

        post = ForumPost(
            topic_id=topic.id,
            user_id=current_user.id,
            content=content,
            content_html=content,
        )
        db.session.add(post)
        db.session.flush()

        topic.first_post_id = post.id
        topic.last_post_id = post.id
        topic.last_post_at = post.created_at
        forum.topic_count += 1
        forum.post_count += 1
        db.session.commit()

        flash('话题已发布。', 'success')
        return redirect(url_for('forum.topic_view', topic_id=topic.id))

    return render_template('forum/new_topic.html', forum=forum)


@forum_bp.route('/topic/<int:topic_id>')
def topic_view(topic_id):
    """View a topic with its posts."""
    topic = ForumTopic.query.get_or_404(topic_id)
    topic.view_count += 1
    db.session.commit()

    page = request.args.get('page', 1, type=int)
    paginated = ForumPost.query.filter_by(topic_id=topic.id)\
        .order_by(ForumPost.created_at.asc())\
        .paginate(page=page, per_page=20, error_out=False)
    return render_template('forum/topic.html', topic=topic, paginated=paginated)


@forum_bp.route('/topic/<int:topic_id>/reply', methods=['POST'])
@login_required
def reply(topic_id):
    """Reply to a topic."""
    topic = ForumTopic.query.get_or_404(topic_id)
    if topic.is_locked and current_user.role not in ('Moderator', 'Admin', 'Sysop'):
        flash('该话题已被锁定。', 'danger')
        return redirect(url_for('forum.topic_view', topic_id=topic.id))

    content = request.form.get('content', '').strip()
    if not content:
        flash('内容不能为空。', 'danger')
        return redirect(url_for('forum.topic_view', topic_id=topic.id))

    post = ForumPost(
        topic_id=topic.id,
        user_id=current_user.id,
        content=content,
        content_html=content,
    )
    db.session.add(post)
    db.session.flush()

    topic.last_post_id = post.id
    topic.last_post_at = post.created_at
    topic.reply_count += 1
    topic.forum.post_count += 1
    db.session.commit()

    flash('回复成功。', 'success')
    return redirect(url_for('forum.topic_view', topic_id=topic.id))
