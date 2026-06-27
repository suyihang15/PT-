from datetime import datetime, timezone
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app.extensions import db
from app.models.user import User, Invite
from app.models.system import SiteSetting, Log
from app.blueprints.auth.forms import LoginForm, RegisterForm

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    form = LoginForm()
    if form.validate_on_submit():
        user = db.session.execute(
            db.select(User).filter_by(username=form.username.data)
        ).scalar_one_or_none()

        if user and user.check_password(form.password.data):
            if user.is_banned:
                flash('您的账号已被禁用。原因: ' + (user.banned_reason or '违反规则'), 'danger')
                return render_template('auth/login.html', form=form)

            login_user(user, remember=form.remember.data)
            user.last_ip = request.remote_addr
            user.last_active_at = datetime.now(timezone.utc)
            db.session.commit()

            flash(f'欢迎回来，{user.username}！', 'success')
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            return redirect(url_for('main.index'))
        else:
            flash('用户名或密码错误，请重试。', 'danger')

    return render_template('auth/login.html', form=form)


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('您已成功退出登录。', 'info')
    return redirect(url_for('main.index'))


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    # Check if registration is open
    invite_only = SiteSetting.get('invite_only', False)
    form = RegisterForm()

    if form.validate_on_submit():
        # Check invite code if invite-only
        if invite_only:
            invite_code = form.invite_code.data
            if not invite_code:
                flash('当前仅允许邀请注册，请提供有效的邀请码。', 'danger')
                return render_template('auth/register.html', form=form, invite_only=invite_only)

            invite = db.session.execute(
                db.select(Invite).filter_by(code=invite_code, used=False)
            ).scalar_one_or_none()

            if not invite or invite.is_expired():
                flash('邀请码无效或已过期。', 'danger')
                return render_template('auth/register.html', form=form, invite_only=invite_only)

            # Mark invite as used
            invite.used = True
            invite.used_at = datetime.now(timezone.utc)

        # Create user
        user = User.create_user(
            username=form.username.data,
            email=form.email.data,
            password=form.password.data,
        )

        if invite_only and invite:
            user.invite_tokens = 0
            invite.used_by = user

        db.session.add(user)
        db.session.commit()

        flash('注册成功！欢迎加入，请登录。', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/register.html', form=form, invite_only=invite_only)


@auth_bp.route('/register/<invite_code>', methods=['GET', 'POST'])
def register_with_invite(invite_code):
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    invite = db.session.execute(
        db.select(Invite).filter_by(code=invite_code, used=False)
    ).scalar_one_or_none()

    if not invite or invite.is_expired():
        flash('邀请码无效或已过期。', 'danger')
        return redirect(url_for('auth.register'))

    form = RegisterForm()
    form.invite_code.data = invite_code
    form.invite_code.render_kw = {'readonly': True}

    if form.validate_on_submit():
        user = User.create_user(
            username=form.username.data,
            email=form.email.data,
            password=form.password.data,
        )

        invite.used = True
        invite.used_at = datetime.now(timezone.utc)
        invite.used_by = user

        db.session.add(user)
        db.session.commit()

        flash('注册成功！欢迎加入，请登录。', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/invite_register.html', form=form, invite=invite)
