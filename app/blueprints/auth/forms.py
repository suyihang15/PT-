from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, HiddenField
from wtforms.validators import DataRequired, Email, Length, EqualTo, ValidationError, Optional
from app.models.user import User
from app.extensions import db


class LoginForm(FlaskForm):
    username = StringField('用户名', validators=[
        DataRequired(message='请输入用户名'),
        Length(min=2, max=32, message='用户名长度为2-32个字符'),
    ])
    password = PasswordField('密码', validators=[
        DataRequired(message='请输入密码'),
    ])
    remember = BooleanField('记住我')
    submit = SubmitField('登录')


class RegisterForm(FlaskForm):
    username = StringField('用户名', validators=[
        DataRequired(message='请输入用户名'),
        Length(min=2, max=32, message='用户名长度为2-32个字符'),
    ])
    email = StringField('邮箱', validators=[
        DataRequired(message='请输入邮箱'),
        Email(message='请输入有效的邮箱地址'),
        Length(max=128),
    ])
    password = PasswordField('密码', validators=[
        DataRequired(message='请输入密码'),
        Length(min=6, max=128, message='密码长度至少6个字符'),
    ])
    password_confirm = PasswordField('确认密码', validators=[
        DataRequired(message='请确认密码'),
        EqualTo('password', message='两次输入的密码不一致'),
    ])
    invite_code = StringField('邀请码', validators=[
        Optional(),
        Length(max=64),
    ])
    submit = SubmitField('注册')

    def validate_username(self, field):
        user = db.session.execute(
            db.select(User).filter_by(username=field.data)
        ).scalar_one_or_none()
        if user:
            raise ValidationError('该用户名已被注册')

    def validate_email(self, field):
        user = db.session.execute(
            db.select(User).filter_by(email=field.data)
        ).scalar_one_or_none()
        if user:
            raise ValidationError('该邮箱已被注册')


class InviteRegisterForm(RegisterForm):
    """Registration form that requires a valid invite code."""
    invite_code = StringField('邀请码', validators=[
        DataRequired(message='请输入邀请码'),
        Length(min=16, max=64),
    ])


class ResetPasswordForm(FlaskForm):
    email = StringField('邮箱', validators=[
        DataRequired(message='请输入邮箱'),
        Email(message='请输入有效的邮箱'),
    ])
    submit = SubmitField('发送重置链接')
