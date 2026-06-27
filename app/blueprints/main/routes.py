from datetime import datetime, timezone
from flask import Blueprint, render_template, request, url_for
from flask_login import current_user
from app.extensions import db, cache
from app.models.torrent import Torrent, Category, Comment, Bookmark, Thank
from app.models.user import User
from app.models.system import News, SiteSetting
from app.models.tracker import Peer

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    """Homepage with stats, latest torrents, announcements."""
    # Site stats (cached for 5 minutes)
    stats = {
        'total_users': User.query.filter_by(is_active=True).count(),
        'total_torrents': Torrent.query.filter_by(visible=True, banned=False).count(),
        'total_peers': Peer.query.count(),
        'total_seeders': db.session.query(db.func.sum(Torrent.seeders)).scalar() or 0,
        'total_leechers': db.session.query(db.func.sum(Torrent.leechers)).scalar() or 0,
        'total_completed': db.session.query(db.func.sum(Torrent.times_completed)).scalar() or 0,
        'total_size': db.session.query(db.func.sum(Torrent.size)).scalar() or 0,
    }

    # Latest torrents
    latest_torrents = Torrent.query.filter_by(visible=True, banned=False)\
        .order_by(Torrent.added_at.desc()).limit(10).all()

    # Latest news
    latest_news = News.query.filter_by(is_published=True)\
        .order_by(News.is_pinned.desc(), News.created_at.desc()).limit(5).all()

    # Latest comments
    latest_comments = Comment.query\
        .join(Torrent, Torrent.id == Comment.torrent_id)\
        .filter(Torrent.visible == True)\
        .order_by(Comment.created_at.desc()).limit(5).all()

    return render_template('main/index.html',
                          stats=stats,
                          latest_torrents=latest_torrents,
                          latest_news=latest_news,
                          latest_comments=latest_comments)


@main_bp.route('/browse')
@main_bp.route('/browse/<category_slug>')
def browse(category_slug=None):
    """Browse torrents with filters."""
    page = request.args.get('page', 1, type=int)
    per_page = current_user.items_per_page if current_user.is_authenticated else 25
    sort = request.args.get('sort', 'added_at')

    query = Torrent.query.filter_by(visible=True, banned=False)

    # Filter by category
    if category_slug:
        category = Category.query.filter_by(slug=category_slug).first_or_404()
        # Include subcategories
        cat_ids = [category.id]
        for child in category.children:
            cat_ids.append(child.id)
        query = query.filter(Torrent.category_id.in_(cat_ids))
        current_category = category
    else:
        current_category = None

    # Additional filters
    freeleech_only = request.args.get('freeleech', type=bool)
    if freeleech_only:
        query = query.filter_by(freeleech=True)

    quality = request.args.get('quality')
    if quality:
        query = query.filter_by(quality=quality)

    medium = request.args.get('medium')
    if medium:
        query = query.filter_by(medium=medium)

    # Sort
    sort_map = {
        'added_at': Torrent.added_at.desc(),
        'seeders': Torrent.seeders.desc(),
        'leechers': Torrent.leechers.desc(),
        'size': Torrent.size.desc(),
        'times_completed': Torrent.times_completed.desc(),
        'name': Torrent.name.asc(),
    }
    order_by = sort_map.get(sort, Torrent.added_at.desc())

    # Sticky torrents first
    paginated = query.order_by(Torrent.sticky_until.desc().nullslast(), order_by)\
        .paginate(page=page, per_page=per_page, error_out=False)

    # Get all categories for sidebar
    categories = Category.query.order_by(Category.sort_order).all()

    return render_template('main/browse.html',
                          paginated=paginated,
                          categories=categories,
                          current_category=current_category,
                          sort=sort,
                          freeleech_only=freeleech_only,
                          quality=quality,
                          medium=medium)


@main_bp.route('/search')
def search():
    """Search torrents."""
    page = request.args.get('page', 1, type=int)
    per_page = current_user.items_per_page if current_user.is_authenticated else 25
    q = request.args.get('q', '').strip()

    query = Torrent.query.filter_by(visible=True, banned=False)

    if q:
        query = query.filter(
            db.or_(
                Torrent.name.ilike(f'%{q}%'),
                Torrent.description.ilike(f'%{q}%'),
                Torrent.scene_group.ilike(f'%{q}%'),
            )
        )

    # Apply same filters as browse
    category_slug = request.args.get('category')
    if category_slug:
        category = Category.query.filter_by(slug=category_slug).first()
        if category:
            cat_ids = [category.id]
            for child in category.children:
                cat_ids.append(child.id)
            query = query.filter(Torrent.category_id.in_(cat_ids))

    quality = request.args.get('quality')
    if quality:
        query = query.filter_by(quality=quality)

    freeleech_only = request.args.get('freeleech', type=bool)
    if freeleech_only:
        query = query.filter_by(freeleech=True)

    sort = request.args.get('sort', 'added_at')
    sort_map = {
        'added_at': Torrent.added_at.desc(),
        'seeders': Torrent.seeders.desc(),
        'size': Torrent.size.desc(),
        'times_completed': Torrent.times_completed.desc(),
    }
    order_by = sort_map.get(sort, Torrent.added_at.desc())

    paginated = query.order_by(order_by).paginate(page=page, per_page=per_page, error_out=False)

    categories = Category.query.order_by(Category.sort_order).all()

    return render_template('main/browse.html',
                          paginated=paginated,
                          categories=categories,
                          current_category=None,
                          search_query=q,
                          sort=sort,
                          freeleech_only=freeleech_only,
                          quality=quality)


@main_bp.route('/rules')
def rules():
    return render_template('main/rules.html')


@main_bp.route('/faq')
def faq():
    return render_template('main/faq.html')


@main_bp.route('/staff')
def staff():
    staff_users = User.query.filter(
        User.role.in_(['Moderator', 'Admin', 'Sysop'])
    ).order_by(User.role.desc()).all()
    return render_template('main/staff.html', staff_users=staff_users)


@main_bp.route('/news')
def news_list():
    page = request.args.get('page', 1, type=int)
    paginated = News.query.filter_by(is_published=True)\
        .order_by(News.is_pinned.desc(), News.created_at.desc())\
        .paginate(page=page, per_page=15, error_out=False)
    return render_template('main/news_list.html', paginated=paginated)


@main_bp.route('/news/<int:news_id>')
def news_detail(news_id):
    article = News.query.get_or_404(news_id)
    article.view_count += 1
    db.session.commit()
    return render_template('main/news_detail.html', article=article)
