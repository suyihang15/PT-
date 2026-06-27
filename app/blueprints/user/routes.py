from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.extensions import db
from app.models.user import User, Invite
from app.models.torrent import Torrent, Bookmark
from app.models.message import PrivateMessage
from app.models.tracker import Snatch, HnrViolation
from app.helpers import role_required

user_bp = Blueprint('user', __name__)


@user_bp.route('/<int:user_id>')
def profile(user_id):
    """Public user profile."""
    user = User.query.get_or_404(user_id)
    if not user.is_active:
        flash('该用户已被禁用。', 'warning')
        return redirect(url_for('main.index'))

    uploads = Torrent.query.filter_by(uploader_id=user.id, visible=True)\
        .order_by(Torrent.added_at.desc()).limit(10).all()
    snatches = Snatch.query.filter_by(user_id=user.id)\
        .order_by(Snatch.last_action_at.desc()).limit(10).all()

    return render_template('user/profile.html', user=user, uploads=uploads, snatches=snatches)


@user_bp.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    """User settings page."""
    if request.method == 'POST':
        current_user.theme = request.form.get('theme', 'light')
        current_user.signature = request.form.get('signature', '')[:512]
        current_user.info_text = request.form.get('info_text', '')
        current_user.items_per_page = int(request.form.get('items_per_page', 25))
        current_user.notify_comment = 'notify_comment' in request.form
        current_user.notify_pm = 'notify_pm' in request.form
        db.session.commit()
        flash('设置已保存。', 'success')
        return redirect(url_for('user.settings'))

    return render_template('user/settings.html')


@user_bp.route('/messages')
@login_required
def messages():
    """Inbox."""
    page = request.args.get('page', 1, type=int)
    pm_query = PrivateMessage.query.filter_by(receiver_id=current_user.id, receiver_deleted=False)\
        .order_by(PrivateMessage.sent_at.desc())
    paginated = pm_query.paginate(page=page, per_page=20, error_out=False)
    return render_template('user/messages_list.html', paginated=paginated, folder='inbox')


@user_bp.route('/messages/sent')
@login_required
def messages_sent():
    """Sent messages."""
    page = request.args.get('page', 1, type=int)
    pm_query = PrivateMessage.query.filter_by(sender_id=current_user.id, sender_deleted=False)\
        .order_by(PrivateMessage.sent_at.desc())
    paginated = pm_query.paginate(page=page, per_page=20, error_out=False)
    return render_template('user/messages_list.html', paginated=paginated, folder='sent')


@user_bp.route('/messages/<int:msg_id>')
@login_required
def view_message(msg_id):
    """View a single message."""
    msg = PrivateMessage.query.get_or_404(msg_id)
    if msg.receiver_id != current_user.id and msg.sender_id != current_user.id:
        flash('无权访问此消息。', 'danger')
        return redirect(url_for('user.messages'))
    if msg.receiver_id == current_user.id and not msg.is_read:
        msg.is_read = True
        db.session.commit()
    return render_template('user/message_view.html', message=msg)


@user_bp.route('/bookmarks')
@login_required
def bookmarks():
    """Bookmarked torrents."""
    page = request.args.get('page', 1, type=int)
    bookmark_query = Bookmark.query.filter_by(user_id=current_user.id)\
        .join(Torrent).filter(Torrent.visible == True)\
        .order_by(Bookmark.created_at.desc())
    paginated = bookmark_query.paginate(page=page, per_page=20, error_out=False)
    return render_template('user/bookmarks.html', paginated=paginated)


@user_bp.route('/invites')
@login_required
def invites():
    """Invite management."""
    invites = Invite.query.filter_by(creator_id=current_user.id)\
        .order_by(Invite.created_at.desc()).all()
    return render_template('user/invites.html', invites=invites)


@user_bp.route('/invites/create', methods=['POST'])
@login_required
def create_invite():
    """Create a new invite code."""
    if current_user.invite_tokens <= 0 and current_user.role not in ('VIP', 'Moderator', 'Admin', 'Sysop'):
        flash('您没有可用的邀请名额。', 'danger')
        return redirect(url_for('user.invites'))

    import secrets
    from datetime import datetime, timezone, timedelta
    invite = Invite(
        code=Invite.generate_code(),
        creator_id=current_user.id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db.session.add(invite)
    current_user.invite_tokens -= 1
    db.session.commit()
    flash('邀请码已生成，有效期为7天。', 'success')
    return redirect(url_for('user.invites'))
