import os
import hashlib
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app, abort, Response
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app.extensions import db
from app.models.torrent import Torrent, Category, Comment, Bookmark, Thank, File as TorrentFile
from app.models.user import User
from app.services.bencode_service import parse_torrent_file, bencode_decode, bencode_encode

torrent_bp = Blueprint('torrent', __name__)


@torrent_bp.route('/<int:torrent_id>')
def detail(torrent_id):
    """Torrent detail page."""
    torrent = Torrent.query.get_or_404(torrent_id)
    if not torrent.visible and (not current_user.is_authenticated or current_user.role not in ('Admin', 'Sysop')):
        abort(404)

    torrent.view_count += 1
    db.session.commit()

    is_bookmarked = False
    is_thanked = False
    if current_user.is_authenticated:
        is_bookmarked = Bookmark.query.filter_by(user_id=current_user.id, torrent_id=torrent.id).first() is not None
        is_thanked = Thank.query.filter_by(user_id=current_user.id, torrent_id=torrent.id).first() is not None

    comments = Comment.query.filter_by(torrent_id=torrent.id)\
        .order_by(Comment.created_at.asc()).all()

    return render_template('torrent/detail.html',
                          torrent=torrent,
                          is_bookmarked=is_bookmarked,
                          is_thanked=is_thanked,
                          comments=comments)


@torrent_bp.route('/<int:torrent_id>/download')
@login_required
def download(torrent_id):
    """Download torrent file with user's passkey injected."""
    torrent = Torrent.query.get_or_404(torrent_id)
    if not torrent.visible:
        abort(404)

    torrent_path = torrent.storage_path()
    full_path = os.path.join(current_app.root_path, '..', torrent_path)

    if not os.path.exists(full_path):
        flash('种子文件不存在。', 'danger')
        return redirect(url_for('torrent.detail', torrent_id=torrent.id))

    with open(full_path, 'rb') as f:
        data = f.read()

    try:
        torrent_data = bencode_decode(data)[0]
        announce_url = request.url_root.rstrip('/') + '/announce/' + current_user.passkey
        torrent_data[b'announce'] = announce_url.encode('utf-8')
        if b'announce-list' in torrent_data:
            torrent_data[b'announce-list'] = [[announce_url.encode('utf-8')]]
        output = bencode_encode(torrent_data)
    except Exception:
        output = data

    filename = torrent.name.replace('/', '_').replace('\\', '_') + '.torrent'
    return Response(
        output,
        mimetype='application/x-bittorrent',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'},
    )


@torrent_bp.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    """Upload a new torrent."""
    categories = Category.query.order_by(Category.sort_order).all()

    if request.method == 'GET':
        return render_template('torrent/upload.html', categories=categories)

    # Handle POST
    torrent_file = request.files.get('torrent_file')
    if not torrent_file or not torrent_file.filename:
        flash('请选择种子文件。', 'danger')
        return render_template('torrent/upload.html', categories=categories)

    if not torrent_file.filename.endswith('.torrent'):
        flash('请上传有效的 .torrent 文件。', 'danger')
        return render_template('torrent/upload.html', categories=categories)

    try:
        file_data = torrent_file.read()
        metadata = parse_torrent_file(file_data)
    except Exception as e:
        flash(f'无法解析种子文件: {str(e)}', 'danger')
        return render_template('torrent/upload.html', categories=categories)

    # Check for duplicate info_hash
    existing = Torrent.query.filter_by(info_hash=metadata['info_hash']).first()
    if existing:
        flash(f'该种子已存在: <a href="{url_for("torrent.detail", torrent_id=existing.id)}">{existing.name}</a>', 'warning')
        return render_template('torrent/upload.html', categories=categories)

    # Get form data
    name = request.form.get('name', '').strip()
    if not name:
        name = metadata['name']

    description = request.form.get('description', '').strip()
    category_id = request.form.get('category_id', type=int)
    anonymous = 'anonymous' in request.form

    if not category_id:
        flash('请选择一个分类。', 'danger')
        return render_template('torrent/upload.html', categories=categories)

    # Create torrent record
    torrent = Torrent(
        info_hash=metadata['info_hash'],
        name=name[:512],
        description=description,
        description_html=description,
        category_id=category_id,
        uploader_id=current_user.id,
        size=metadata['size'],
        file_count=metadata['file_count'],
        piece_length=metadata['piece_length'],
        piece_count=metadata['piece_count'],
        is_private=metadata['is_private'],
        created_by=metadata['created_by'][:256] if metadata.get('created_by') else None,
        encoding=metadata.get('encoding', 'UTF-8')[:32],
        anonymous=anonymous,
        quality=request.form.get('quality'),
        medium=request.form.get('medium'),
        codec=request.form.get('codec'),
        audio_codec=request.form.get('audio_codec'),
        hdr=request.form.get('hdr'),
        scene_group=request.form.get('scene_group', '')[:128],
    )
    db.session.add(torrent)
    db.session.flush()  # Get torrent.id

    # Create file entries
    for f in metadata['files']:
        file_entry = TorrentFile(
            torrent_id=torrent.id,
            path=f['path'][:1024],
            size=f['size'],
        )
        db.session.add(file_entry)

    # Store .torrent file on disk
    storage_dir = os.path.join(current_app.root_path, '..', 'storage', 'torrents', metadata['info_hash'][:2].lower())
    os.makedirs(storage_dir, exist_ok=True)
    file_path = os.path.join(storage_dir, f"{metadata['info_hash']}.torrent")
    with open(file_path, 'wb') as f:
        f.write(file_data)

    # Update user stats
    current_user.uploaded = (current_user.uploaded or 0) + metadata['size']

    db.session.commit()

    flash('种子发布成功！', 'success')
    return redirect(url_for('torrent.detail', torrent_id=torrent.id))


@torrent_bp.route('/<int:torrent_id>/bookmark', methods=['POST'])
@login_required
def toggle_bookmark(torrent_id):
    """Toggle bookmark on a torrent."""
    torrent = Torrent.query.get_or_404(torrent_id)
    bookmark = Bookmark.query.filter_by(user_id=current_user.id, torrent_id=torrent.id).first()

    if bookmark:
        db.session.delete(bookmark)
        torrent.bookmark_count = max(0, torrent.bookmark_count - 1)
        db.session.commit()
        return jsonify({'bookmarked': False, 'count': torrent.bookmark_count})
    else:
        bookmark = Bookmark(user_id=current_user.id, torrent_id=torrent.id)
        db.session.add(bookmark)
        torrent.bookmark_count += 1
        db.session.commit()
        return jsonify({'bookmarked': True, 'count': torrent.bookmark_count})


@torrent_bp.route('/<int:torrent_id>/thank', methods=['POST'])
@login_required
def thank(torrent_id):
    """Thank the uploader."""
    torrent = Torrent.query.get_or_404(torrent_id)

    if torrent.uploader_id == current_user.id:
        return jsonify({'error': '不能感谢自己发布的种子。'}), 400

    existing = Thank.query.filter_by(user_id=current_user.id, torrent_id=torrent.id).first()
    if existing:
        return jsonify({'error': '您已经感谢过该种子。'}), 400

    thank = Thank(user_id=current_user.id, torrent_id=torrent.id)
    db.session.add(thank)
    torrent.thank_count += 1
    db.session.commit()

    return jsonify({'success': True, 'count': torrent.thank_count})


@torrent_bp.route('/<int:torrent_id>/comment', methods=['POST'])
@login_required
def add_comment(torrent_id):
    """Add a comment to a torrent."""
    torrent = Torrent.query.get_or_404(torrent_id)
    data = request.get_json()
    content = data.get('content', '').strip()

    if not content:
        return jsonify({'error': '评论内容不能为空'}), 400
    if len(content) > 10000:
        return jsonify({'error': '评论内容过长'}), 400

    comment = Comment(
        torrent_id=torrent.id,
        user_id=current_user.id,
        content=content,
        content_html=content,
    )
    db.session.add(comment)
    torrent.comment_count += 1
    db.session.commit()

    return jsonify({
        'success': True,
        'comment': {
            'id': comment.id,
            'user': current_user.username,
            'content': content,
            'time': comment.created_at.strftime('%Y-%m-%d %H:%M'),
        }
    })
