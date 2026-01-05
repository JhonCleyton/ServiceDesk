from datetime import datetime, timedelta
from flask_login import UserMixin
from itsdangerous import URLSafeTimedSerializer
from werkzeug.security import generate_password_hash, check_password_hash
from flask import current_app
from . import db


class Company(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    domain = db.Column(db.String(120), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    allowed_ips = db.Column(db.Text)  # comma or newline-separated CIDRs or IPs
    terms_url = db.Column(db.String(255))
    consent_required = db.Column(db.Boolean, default=False)
    retention_days = db.Column(db.Integer, default=365)
    # Allow registrations without enforcing company e-mail domain
    accept_any_domain = db.Column(db.Boolean, default=False)
    # Optional branding
    brand_primary = db.Column(db.String(16))
    brand_primary_dark = db.Column(db.String(16))
    brand_primary_light = db.Column(db.String(16))
    logo_url = db.Column(db.String(255))
    lgpd_url = db.Column(db.String(255), nullable=True, comment='URL para a política LGPD da empresa')
    active = db.Column(db.Boolean, default=True)

    users = db.relationship('User', backref='company', lazy=True)
    tickets = db.relationship('Ticket', backref='company', lazy=True)
    contracts = db.relationship('Contract', backref='company', lazy=True)
    categories = db.relationship('Category', backref='company', lazy=True)
    queues = db.relationship('Queue', backref='company', lazy=True)
    assets = db.relationship('Asset', backref='company', lazy=True)
    problems = db.relationship('Problem', backref='company', lazy=True)
    changes = db.relationship('ChangeRequest', backref='company', lazy=True)


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), default='client')  # client, tech, supervisor, admin
    confirmed = db.Column(db.Boolean, default=False)
    confirmed_at = db.Column(db.DateTime)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    failed_attempts = db.Column(db.Integer, default=0)
    locked_until = db.Column(db.DateTime)
    force_2fa = db.Column(db.Boolean, default=False)
    last_login_at = db.Column(db.DateTime)
    avatar_filename = db.Column(db.String(255))
    consent_accepted_at = db.Column(db.DateTime)

    tickets_created = db.relationship('Ticket', backref='creator', foreign_keys='Ticket.created_by_id', lazy=True)
    tickets_assigned = db.relationship('Ticket', backref='assignee', foreign_keys='Ticket.assigned_to_id', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def generate_confirmation_token(self):
        s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        return s.dumps({'user_id': self.id, 'email': self.email})

    @staticmethod
    def verify_confirmation_token(token, max_age=3600*24):
        s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        data = s.loads(token, max_age=max_age)
        return data


class SLAConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    contract_name = db.Column(db.String(120))
    first_response_minutes = db.Column(db.Integer, default=60)
    resolution_minutes = db.Column(db.Integer, default=1440)
    paused = db.Column(db.Boolean, default=False)


class Contract(db.Model):
    __tablename__ = 'contract'
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    tickets = db.relationship('Ticket', backref='contract', lazy=True)


class Category(db.Model):
    __tablename__ = 'category'
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=True)
    name = db.Column(db.String(100), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('category.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    parent = db.relationship('Category', remote_side=[id], backref='children')


class SLAPlan(db.Model):
    __tablename__ = 'sla_plan'
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    # Targets in minutes
    first_response_minutes = db.Column(db.Integer, nullable=False)
    resolution_minutes = db.Column(db.Integer, nullable=False)
    # Optional scoping
    contract_id = db.Column(db.Integer, db.ForeignKey('contract.id'))
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'))
    priority = db.Column(db.String(16))  # If set, applies to this priority only
    active = db.Column(db.Boolean, default=True)

    contract = db.relationship('Contract')
    category = db.relationship('Category')


# Association table for queues and users (members)
queue_user = db.Table(
    'queue_user',
    db.Column('queue_id', db.Integer, db.ForeignKey('queue.id'), primary_key=True),
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
)


class Queue(db.Model):
    __tablename__ = 'queue'
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    members = db.relationship('User', secondary=queue_user, backref='queues', lazy='dynamic')
    tickets = db.relationship('Ticket', backref='queue', lazy=True)


class Asset(db.Model):
    __tablename__ = 'asset'
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    serial = db.Column(db.String(120))
    type = db.Column(db.String(120))
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    tickets = db.relationship('Ticket', backref='asset', lazy=True)


class Problem(db.Model):
    __tablename__ = 'problem'
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    status = db.Column(db.String(32), default='Aberto')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    tickets = db.relationship('Ticket', backref='problem_ref', lazy=True)


class ChangeRequest(db.Model):
    __tablename__ = 'change_request'
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    status = db.Column(db.String(32), default='Proposta')
    approval = db.Column(db.String(32), default='Pendente')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    tickets = db.relationship('Ticket', backref='change_ref', lazy=True)


class OTPCode(db.Model):
    __tablename__ = 'otp_code'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    code = db.Column(db.String(6), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)
    consumed = db.Column(db.Boolean, default=False)


class EmailTemplate(db.Model):
    __tablename__ = 'email_template'
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'))
    name = db.Column(db.String(120), nullable=False)  # e.g., ticket_created, comment, status_change
    subject = db.Column(db.String(255), nullable=False)
    body = db.Column(db.Text, nullable=False)
    active = db.Column(db.Boolean, default=True)
class Ticket(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.String(32), unique=True, index=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(32), default='Novo', index=True)  # Novo, Em atendimento, Aguardando, Resolvido, Fechado
    priority = db.Column(db.String(16), default='Média', index=True)
    category = db.Column(db.String(64))
    subcategory = db.Column(db.String(64))
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    created_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    assigned_to_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    contract_id = db.Column(db.Integer, db.ForeignKey('contract.id'))
    sla_plan_id = db.Column(db.Integer, db.ForeignKey('sla_plan.id'))
    queue_id = db.Column(db.Integer, db.ForeignKey('queue.id'))
    asset_id = db.Column(db.Integer, db.ForeignKey('asset.id'))
    problem_id = db.Column(db.Integer, db.ForeignKey('problem.id'))
    change_id = db.Column(db.Integer, db.ForeignKey('change_request.id'))

    first_response_at = db.Column(db.DateTime)
    resolved_at = db.Column(db.DateTime)
    closed_at = db.Column(db.DateTime)
    closed_reason = db.Column(db.String(255))
    solution = db.Column(db.Text)
    # Technician mandatory evaluation at close
    tech_evaluation = db.Column(db.Text)
    tech_eval_category = db.Column(db.String(32))  # tecnico, sistemico, usuario, solicitacao, melhoria, outro

    # User rating after closure
    user_rating = db.Column(db.Integer)  # 1-5
    user_rating_comment = db.Column(db.Text)
    user_rating_token = db.Column(db.String(64), index=True)
    user_rating_at = db.Column(db.DateTime)

    due_first_response_at = db.Column(db.DateTime)
    due_resolution_at = db.Column(db.DateTime)
    sla_paused = db.Column(db.Boolean, default=False)
    sla_paused_since = db.Column(db.DateTime)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    comments = db.relationship('TicketComment', backref='ticket', lazy=True, cascade='all, delete-orphan')
    attachments = db.relationship('Attachment', backref='ticket', lazy=True, cascade='all, delete-orphan')

    sla_plan = db.relationship('SLAPlan')

    participants = db.relationship('TicketParticipant', backref='ticket', lazy=True, cascade='all, delete-orphan')

    def apply_sla(self, sla_plan: 'SLAPlan'):
        self.sla_plan = sla_plan
        if sla_plan:
            self.due_first_response_at = self.created_at + timedelta(minutes=sla_plan.first_response_minutes)
            self.due_resolution_at = self.created_at + timedelta(minutes=sla_plan.resolution_minutes)


class TicketComment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey('ticket.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    internal = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User')
    reactions = db.relationship('CommentReaction', backref='comment', lazy=True, cascade='all, delete-orphan')


class Attachment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey('ticket.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    original_name = db.Column(db.String(255), nullable=False)
    content_type = db.Column(db.String(127))
    size = db.Column(db.Integer)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)


class CommentReaction(db.Model):
    __tablename__ = 'comment_reaction'
    id = db.Column(db.Integer, primary_key=True)
    comment_id = db.Column(db.Integer, db.ForeignKey('ticket_comment.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    emoji = db.Column(db.String(8), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User')
    __table_args__ = (
        db.UniqueConstraint('comment_id', 'user_id', 'emoji', name='uq_comment_reaction'),
    )


class TicketParticipant(db.Model):
    __tablename__ = 'ticket_participant'
    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey('ticket.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    role = db.Column(db.String(16), default='guest')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User')
    __table_args__ = (
        db.UniqueConstraint('ticket_id', 'user_id', name='uq_ticket_participant'),
    )


class Notification(db.Model):
    __tablename__ = 'notification'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False, index=True)
    kind = db.Column(db.String(32), nullable=False)  # ticket_comment, ticket_status, ticket_closed, etc.
    title = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text)
    link = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    seen_at = db.Column(db.DateTime)
    read_at = db.Column(db.DateTime)

    user = db.relationship('User')


class LGPDRevision(db.Model):
    __tablename__ = 'lgpd_revision'
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'))
    subject = db.Column(db.String(255), nullable=False)
    body = db.Column(db.Text, nullable=False)
    version = db.Column(db.Integer, default=1)
    published = db.Column(db.Boolean, default=False, index=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    company = db.relationship('Company')
    created_by = db.relationship('User')

class AuditLog(db.Model):
    __tablename__ = 'audit_log'
    id = db.Column(db.Integer, primary_key=True)
    entity = db.Column(db.String(50), nullable=False)
    entity_id = db.Column(db.Integer, nullable=False)
    action = db.Column(db.String(50), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    data = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class GameScore(db.Model):
    __tablename__ = 'game_score'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    name = db.Column(db.String(120))  # display name when not authenticated
    game = db.Column(db.String(32), nullable=False)  # e.g., snake, sudoku
    score = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    user = db.relationship('User')


class KnowledgeBaseArticle(db.Model):
    __tablename__ = 'knowledge_base_article'
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    public = db.Column(db.Boolean, default=False)
    status = db.Column(db.String(20), default='draft')  # draft, published, archived
    version = db.Column(db.Integer, default=1)
    created_by_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    approved_by_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
