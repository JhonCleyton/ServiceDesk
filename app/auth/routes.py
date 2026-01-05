from flask import Blueprint, render_template, redirect, url_for, flash, request, session, current_app
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timedelta
from .. import db
from ..models import User, Company, OTPCode
from ..email import send_confirmation_email, send_otp_email, send_password_reset_email
from .forms import LoginForm, RegisterForm, OTPForm, ForgotPasswordForm, ResetPasswordForm


auth_bp = Blueprint('auth', __name__, template_folder='../templates')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower()).first()
        # Lockout check
        if user and user.locked_until and user.locked_until > datetime.utcnow():
            remaining = int((user.locked_until - datetime.utcnow()).total_seconds() // 60) + 1
            flash(f'Conta bloqueada. Tente novamente em aproximadamente {remaining} minutos.', 'danger')
            return render_template('auth/login.html', form=form)
        if user and user.check_password(form.password.data):
            # IP allowlist check
            from ..utils import ip_allowed
            remote_ip = request.headers.get('X-Forwarded-For', request.remote_addr or '')
            remote_ip = (remote_ip.split(',')[0] or '').strip()
            if not ip_allowed(user.company, remote_ip):
                flash('Acesso não permitido a partir deste IP.', 'danger')
                return render_template('auth/login.html', form=form)
            if not user.confirmed:
                flash('Confirme seu e-mail antes de acessar.', 'warning')
                return redirect(url_for('auth.resend_confirmation', email=user.email))
            # reset attempts
            user.failed_attempts = 0
            user.locked_until = None
            db.session.commit()
            # 2FA if enforced
            if user.force_2fa:
                # create OTP
                code = f"{__import__('random').randint(0, 999999):06d}"
                otp = OTPCode(user_id=user.id, code=code, created_at=datetime.utcnow(), expires_at=datetime.utcnow()+timedelta(minutes=10))
                db.session.add(otp)
                db.session.commit()
                try:
                    send_otp_email(user, code)
                except Exception:
                    pass
                session['pending_otp_user'] = user.id
                session['remember_me'] = form.remember.data
                flash('Enviamos um código de verificação para seu e-mail.', 'info')
                return redirect(url_for('auth.otp'))
            # direct login
            login_user(user, remember=form.remember.data)
            session.permanent = True
            user.last_login_at = datetime.utcnow()
            db.session.commit()
            next_page = request.args.get('next') or url_for('main.dashboard')
            return redirect(next_page)
        flash('Credenciais inválidas.', 'danger')
        if user:
            user.failed_attempts = (user.failed_attempts or 0) + 1
            # lock after 5 failed attempts for 15 minutes
            if user.failed_attempts >= 5:
                user.locked_until = datetime.utcnow() + timedelta(minutes=15)
                user.failed_attempts = 0
            db.session.commit()
    return render_template('auth/login.html', form=form)


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Sessão encerrada.', 'success')
    return redirect(url_for('auth.login'))


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    form = RegisterForm()
    companies = Company.query.order_by(Company.name).all()
    def _label(c):
        tag = ' — aceita qualquer domínio' if getattr(c, 'accept_any_domain', False) else ''
        return f"{c.name} ({c.domain}){tag}"
    form.company_id.choices = [(c.id, _label(c)) for c in companies]
    if form.validate_on_submit():
        company = Company.query.get(form.company_id.data)
        email = form.email.data.lower()
        domain = email.split('@')[-1]
        if company and not getattr(company, 'accept_any_domain', False) and company.domain.lower() != domain:
            flash('O e-mail deve possuir o domínio da empresa selecionada.', 'danger')
            return render_template('auth/register.html', form=form)
        if company and company.consent_required and not form.agree.data:
            flash('É necessário concordar com os Termos para prosseguir.', 'danger')
            return render_template('auth/register.html', form=form)
        user = User(email=email, name=form.name.data, role='client', company_id=company.id)
        user.set_password(form.password.data)
        try:
            db.session.add(user)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash('E-mail já cadastrado.', 'danger')
            return render_template('auth/register.html', form=form)
        token = user.generate_confirmation_token()
        try:
            send_confirmation_email(user, token)
            flash('Cadastro criado. Enviamos um link de confirmação para seu e-mail.', 'success')
        except Exception as e:
            current_app.logger.exception('Falha ao enviar e-mail de confirmação no cadastro')
            flash('Cadastro criado, mas não foi possível enviar o e-mail de confirmação agora. Tente reenviar mais tarde ou peça confirmação ao admin.', 'warning')
        return redirect(url_for('auth.login'))
    return render_template('auth/register.html', form=form)


@auth_bp.route('/confirm/<token>')
def confirm_email(token):
    try:
        data = User.verify_confirmation_token(token)
    except Exception:
        flash('Token inválido ou expirado.', 'danger')
        return redirect(url_for('auth.login'))
    user = User.query.filter_by(id=data.get('user_id'), email=data.get('email')).first()
    if not user:
        flash('Token inválido.', 'danger')
        return redirect(url_for('auth.login'))
    if not user.confirmed:
        user.confirmed = True
        user.confirmed_at = datetime.utcnow()
        db.session.commit()
        flash('E-mail confirmado com sucesso. Faça login.', 'success')
    else:
        flash('E-mail já confirmado. Faça login.', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/resend-confirmation')
def resend_confirmation():
    email = request.args.get('email')
    user = User.query.filter_by(email=email).first()
    if not user:
        flash('Usuário não encontrado.', 'danger')
        return redirect(url_for('auth.login'))
    if user.confirmed:
        flash('Usuário já confirmado.', 'info')
        return redirect(url_for('auth.login'))
    token = user.generate_confirmation_token()
    try:
        send_confirmation_email(user, token)
        flash('Reenviamos o e-mail de confirmação.', 'success')
    except Exception as e:
        current_app.logger.exception('Falha ao reenviar e-mail de confirmação')
        flash('Não foi possível reenviar o e-mail agora. Tente novamente mais tarde.', 'warning')
    return redirect(url_for('auth.login'))


@auth_bp.route('/otp', methods=['GET','POST'])
def otp():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    user_id = session.get('pending_otp_user')
    user = User.query.get(user_id) if user_id else None
    if not user:
        flash('Sessão de verificação expirada. Faça login novamente.', 'warning')
        return redirect(url_for('auth.login'))
    form = OTPForm(email=user.email)
    if form.validate_on_submit():
        code = form.code.data
        otp = OTPCode.query.filter_by(user_id=user.id, code=code, consumed=False).order_by(OTPCode.created_at.desc()).first()
        if otp and otp.expires_at >= datetime.utcnow():
            otp.consumed = True
            db.session.commit()
            login_user(user, remember=session.get('remember_me', False))
            session.pop('pending_otp_user', None)
            session.pop('remember_me', None)
            session.permanent = True
            user.last_login_at = datetime.utcnow()
            db.session.commit()
            return redirect(url_for('main.dashboard'))
        flash('Código inválido ou expirado.', 'danger')
    return render_template('auth/otp.html', form=form)


@auth_bp.route('/forgot', methods=['GET','POST'])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    form = ForgotPasswordForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        user = User.query.filter_by(email=email).first()
        if user:
            # generate token using existing confirmation serializer with a different purpose
            try:
                s = current_app.config['SECRET_KEY']
                from itsdangerous import URLSafeTimedSerializer
                ts = URLSafeTimedSerializer(s)
                token = ts.dumps({'user_id': user.id, 'email': user.email, 'purpose': 'reset'})
                send_password_reset_email(user, token)
            except Exception:
                current_app.logger.exception('Falha ao enviar e-mail de reset de senha')
        flash('Se o e-mail estiver cadastrado, enviaremos instruções para redefinir a senha.', 'info')
        return redirect(url_for('auth.login'))
    return render_template('auth/forgot.html', form=form)


@auth_bp.route('/reset/<token>', methods=['GET','POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    form = ResetPasswordForm()
    if form.validate_on_submit():
        # verify token with 2-hour expiry
        try:
            from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
            ts = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
            data = ts.loads(token, max_age=7200)
            if data.get('purpose') != 'reset':
                raise BadSignature('wrong purpose')
        except Exception:
            flash('Link inválido ou expirado.', 'danger')
            return redirect(url_for('auth.forgot_password'))
        user = User.query.filter_by(id=data.get('user_id'), email=data.get('email')).first()
        if not user:
            flash('Usuário não encontrado.', 'danger')
            return redirect(url_for('auth.forgot_password'))
        user.set_password(form.password.data)
        db.session.commit()
        flash('Senha redefinida com sucesso. Faça login.', 'success')
        return redirect(url_for('auth.login'))
    return render_template('auth/reset.html', form=form)
