from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.extensions import db
from app.models.bonus import SeedBonusLog, BonusShopItem, BonusPurchase
from app.models.tracker import Peer

bonus_bp = Blueprint('bonus', __name__)


@bonus_bp.route('/')
@login_required
def index():
    """Bonus points overview."""
    logs = SeedBonusLog.query.filter_by(user_id=current_user.id)\
        .order_by(SeedBonusLog.created_at.desc()).limit(20).all()
    active_peers = Peer.query.filter_by(user_id=current_user.id, seeder=True).all()
    return render_template('bonus/index.html', logs=logs, active_peers=active_peers)


@bonus_bp.route('/shop')
@login_required
def shop():
    """Bonus shop."""
    items = BonusShopItem.query.filter_by(is_active=True).order_by(BonusShopItem.price.asc()).all()
    return render_template('bonus/shop.html', items=items)


@bonus_bp.route('/shop/buy/<int:item_id>', methods=['POST'])
@login_required
def buy_item(item_id):
    """Purchase an item from the bonus shop."""
    item = BonusShopItem.query.get_or_404(item_id)
    flash('积分商城功能将在后续版本中完善。', 'info')
    return redirect(url_for('bonus.shop'))


@bonus_bp.route('/log')
@login_required
def log():
    """Bonus points history."""
    page = request.args.get('page', 1, type=int)
    paginated = SeedBonusLog.query.filter_by(user_id=current_user.id)\
        .order_by(SeedBonusLog.created_at.desc())\
        .paginate(page=page, per_page=30, error_out=False)
    return render_template('bonus/log.html', paginated=paginated)
