import os
from datetime import datetime, timedelta, timezone
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_mail import Mail
from flask_wtf import CSRFProtect
try:
    # Load .env variables if available
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass
try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None


db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
mail = Mail()
csrf = CSRFProtect()


def create_app():
    app = Flask(__name__, instance_relative_config=False)
    app.config.from_object('app.config.DevelopmentConfig')

    os.makedirs(os.path.join(app.root_path, 'uploads'), exist_ok=True)
    os.makedirs(os.path.join(app.root_path, 'static', 'uploads', 'avatars'), exist_ok=True)
    os.makedirs(os.path.join(app.root_path, 'static', 'uploads', 'logos'), exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    mail.init_app(app)
    csrf.init_app(app)

    login_manager.login_view = 'auth.login'

    from .models import User, Company  # noqa: F401

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    from .auth.routes import auth_bp
    from .tickets.routes import tickets_bp
    from .main.routes import main_bp
    # New blueprints
    from .admin.routes import admin_bp
    from .kb.routes import kb_bp
    from .reports.routes import reports_bp
    from .notifications.routes import notify_bp
    from .chat.routes import chat_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(tickets_bp, url_prefix='/tickets')
    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(kb_bp, url_prefix='/kb')
    app.register_blueprint(reports_bp, url_prefix='/reports')
    app.register_blueprint(chat_bp, url_prefix='/chat')
    app.register_blueprint(notify_bp)

    # Jinja filter para converter UTC -> timezone configurado
    def _localtime(value, fmt='%d/%m/%Y %H:%M'):
        if not value:
            return ''
        tzname = app.config.get('TIMEZONE', 'America/Sao_Paulo')
        # Tentar ZoneInfo (Python 3.9+). Se não disponível, usar offset -03:00 como fallback.
        try:
            if ZoneInfo is not None:
                tz = ZoneInfo(tzname)
                dt = value
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(tz).strftime(fmt)
        except Exception:
            pass
        try:
            # Fallback: assume UTC e subtrai 3 horas
            base = value
            if isinstance(base, datetime):
                return (base - timedelta(hours=3)).strftime(fmt)
        except Exception:
            pass
        return str(value)

    app.jinja_env.filters['localtime'] = _localtime
    # Simple split filter for templates
    def _split(value, sep=' '):
        try:
            return (value or '').split(sep)
        except Exception:
            return []
    app.jinja_env.filters['split'] = _split

    # Format datetime (safe if value already string). Useful for templates using '|format_datetime'.
    def _format_datetime(value, fmt='%d/%m/%Y %H:%M'):
        try:
            if isinstance(value, datetime):
                return value.strftime(fmt)
            # If already formatted by 'localtime' or a string, just return as-is
            return str(value)
        except Exception:
            return str(value)
    app.jinja_env.filters['format_datetime'] = _format_datetime

    # Conveniência: criar tabelas e uma empresa exemplo em dev
    with app.app_context():
        from .models import Company, User, EmailTemplate
        db.create_all()
        # Light-touch schema ensure for optional branding columns
        try:
            from sqlalchemy import inspect, text
            inspector = inspect(db.engine)
            cols = {c['name'] for c in inspector.get_columns('company')}
            stmts = []
            if 'brand_primary' not in cols:
                stmts.append("ALTER TABLE company ADD COLUMN brand_primary VARCHAR(16)")
            if 'brand_primary_dark' not in cols:
                stmts.append("ALTER TABLE company ADD COLUMN brand_primary_dark VARCHAR(16)")
            if 'brand_primary_light' not in cols:
                stmts.append("ALTER TABLE company ADD COLUMN brand_primary_light VARCHAR(16)")
            if 'logo_url' not in cols:
                stmts.append("ALTER TABLE company ADD COLUMN logo_url VARCHAR(255)")
            if 'accept_any_domain' not in cols:
                stmts.append("ALTER TABLE company ADD COLUMN accept_any_domain BOOLEAN DEFAULT 0")
            for s in stmts:
                try:
                    db.session.execute(text(s))
                except Exception:
                    pass
            if stmts:
                db.session.commit()
            # Ensure user.avatar_filename
            ucols = {c['name'] for c in inspector.get_columns('user')}
            if 'avatar_filename' not in ucols:
                try:
                    db.session.execute(text("ALTER TABLE user ADD COLUMN avatar_filename VARCHAR(255)"))
                    db.session.commit()
                except Exception:
                    pass
            if 'consent_accepted_at' not in ucols:
                try:
                    db.session.execute(text("ALTER TABLE user ADD COLUMN consent_accepted_at DATETIME"))
                    db.session.commit()
                except Exception:
                    pass
            # Ensure notification.seen_at and notification.read_at
            try:
                ncols = {c['name'] for c in inspector.get_columns('notification')}
                nstmts = []
                if 'seen_at' not in ncols:
                    nstmts.append("ALTER TABLE notification ADD COLUMN seen_at DATETIME")
                if 'read_at' not in ncols:
                    nstmts.append("ALTER TABLE notification ADD COLUMN read_at DATETIME")
                for s in nstmts:
                    try:
                        db.session.execute(text(s))
                    except Exception:
                        pass
                if nstmts:
                    db.session.commit()
            except Exception:
                pass
            # Ensure new Ticket columns for closure evaluation and rating
            try:
                tcols = {c['name'] for c in inspector.get_columns('ticket')}
                tstmts = []
                if 'tech_evaluation' not in tcols:
                    tstmts.append("ALTER TABLE ticket ADD COLUMN tech_evaluation TEXT")
                if 'tech_eval_category' not in tcols:
                    tstmts.append("ALTER TABLE ticket ADD COLUMN tech_eval_category VARCHAR(32)")
                if 'user_rating' not in tcols:
                    tstmts.append("ALTER TABLE ticket ADD COLUMN user_rating INTEGER")
                if 'user_rating_comment' not in tcols:
                    tstmts.append("ALTER TABLE ticket ADD COLUMN user_rating_comment TEXT")
                if 'user_rating_token' not in tcols:
                    tstmts.append("ALTER TABLE ticket ADD COLUMN user_rating_token VARCHAR(64)")
                if 'user_rating_at' not in tcols:
                    tstmts.append("ALTER TABLE ticket ADD COLUMN user_rating_at DATETIME")
                for s in tstmts:
                    try:
                        db.session.execute(text(s))
                    except Exception:
                        pass
                if tstmts:
                    db.session.commit()
            except Exception:
                pass
        except Exception:
            pass
        if Company.query.count() == 0:
            db.session.add(Company(name='JC Byte', domain='jhoncleyton.dev'))
            db.session.commit()
        # Criar admin padrão se não houver
        if User.query.filter_by(role='admin').count() == 0:
            company = Company.query.filter_by(domain='jhoncleyton.dev').first() or Company.query.first()
            if not company:
                company = Company(name='JC Byte - Solucoes em tecnologia', domain='jhoncleyton.dev')
                db.session.add(company)
                db.session.commit()
            admin_email = os.environ.get('ADMIN_EMAIL', 'admin@local.com').lower()
            admin_password = os.environ.get('ADMIN_PASSWORD', 'admin123')
            admin = User(email=admin_email, name='Administrador', role='admin', company_id=company.id, confirmed=True, confirmed_at=datetime.utcnow())
            admin.set_password(admin_password)
            db.session.add(admin)
            db.session.commit()
            print(f"[SEED] Admin criado: {admin_email} / senha: {admin_password} — altere em produção.")

        # Seed default LGPD text as a global email template (editable in Admin > Modelos de E-mail)
        try:
            if EmailTemplate.query.filter_by(company_id=None, name='lgpd').first() is None:
                lgpd_body = (
                    "Política de Privacidade e Proteção de Dados (LGPD)\n\n"
                    "1. Finalidade do tratamento: Utilizamos seus dados para prestação do serviço de suporte, cadastro e comunicação.\n"
                    "2. Bases legais: Execução de contrato, cumprimento de obrigação legal e legítimo interesse, quando aplicável.\n"
                    "3. Compartilhamento: Poderemos compartilhar dados com provedores estritamente necessários à operação (ex.: e-mail).\n"
                    "4. Direitos do titular: Você pode solicitar confirmação, acesso, correção, anonimização, exclusão e portabilidade.\n"
                    "5. Segurança: Adotamos medidas técnicas e administrativas para proteção dos dados.\n"
                    "6. Retenção: Mantemos dados pelo tempo necessário ao cumprimento de obrigações e prestação do serviço.\n"
                    "7. Contato do Encarregado (DPO): dpo@exemplo.com\n\n"
                    "Ao continuar, você declara ciência e concordância com esta Política."
                )
                tpl = EmailTemplate(company_id=None, name='lgpd', subject='Política de Privacidade', body=lgpd_body, active=True)
                db.session.add(tpl)
                db.session.commit()
        except Exception:
            pass

    return app
