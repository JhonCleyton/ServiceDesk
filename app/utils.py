from functools import wraps
from flask import abort, current_app
from .models import SLAPlan, Company, Ticket, TicketComment
from . import db
import imaplib
from email.header import decode_header
from email.utils import parseaddr
import email
import re
import ipaddress
from datetime import datetime, timedelta
import os


def role_required(*roles):
    from flask_login import current_user
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if current_user.role not in roles:
                abort(403)
            return f(*args, **kwargs)
        return wrapper
    return decorator


def choose_sla_plan(company_id, contract_id=None, category_id=None, priority=None):
    q = SLAPlan.query.filter_by(company_id=company_id, active=True)
    candidates = q.all()
    def score(p: SLAPlan):
        s = 0
        if p.contract_id and contract_id and p.contract_id == contract_id:
            s += 4
        elif p.contract_id and p.contract_id != contract_id:
            return -1
        if p.category_id and category_id and p.category_id == category_id:
            s += 2
        elif p.category_id and p.category_id != category_id:
            return -1
        if p.priority and priority and p.priority == priority:
            s += 1
        elif p.priority and p.priority != priority:
            return -1
        return s
    best = None
    best_score = -1
    for p in candidates:
        sc = score(p)
        if sc > best_score:
            best = p
            best_score = sc
    return best


def audit(entity: str, entity_id: int, action: str, user_id=None, data: str=None):
    from .models import AuditLog
    log = AuditLog(entity=entity, entity_id=entity_id, action=action, user_id=user_id, data=data)
    db.session.add(log)
    db.session.commit()


def ip_allowed(company: Company, ip: str) -> bool:
    if not company or not company.allowed_ips:
        return True
    rules = [r.strip() for r in company.allowed_ips.splitlines() if r.strip()]
    try:
        ip_obj = ipaddress.ip_address(ip)
        for r in rules:
            try:
                if '/' in r:
                    if ip_obj in ipaddress.ip_network(r, strict=False):
                        return True
                else:
                    if ip_obj == ipaddress.ip_address(r):
                        return True
            except ValueError:
                continue
    except ValueError:
        return False
    return False


TICKET_PATTERN = re.compile(r"TCK-\d{8}-[0-9A-F]{6}")


def poll_imap_and_process():
    host = current_app.config.get('IMAP_HOST')
    if not host:
        return 0
    port = current_app.config.get('IMAP_PORT', 993)
    use_ssl = current_app.config.get('IMAP_SSL', True)
    username = current_app.config.get('IMAP_USERNAME')
    password = current_app.config.get('IMAP_PASSWORD')
    if not username or not password:
        return 0
    conn = imaplib.IMAP4_SSL(host, port) if use_ssl else imaplib.IMAP4(host, port)
    conn.login(username, password)
    conn.select('INBOX')
    typ, data = conn.search(None, 'UNSEEN')
    if typ != 'OK':
        return 0
    count = 0
    for num in data[0].split():
        typ, msg_data = conn.fetch(num, '(RFC822)')
        if typ != 'OK':
            continue
        msg = email.message_from_bytes(msg_data[0][1])
        subj = decode_header(msg.get('Subject') or '')
        subject = ' '.join([ (str(t[0], t[1] or 'utf-8') if isinstance(t[0], bytes) else str(t[0])) for t in subj ])
        from_hdr = parseaddr(msg.get('From'))
        sender_email = (from_hdr[1] or '').lower()
        domain = sender_email.split('@')[-1]
        company = Company.query.filter(Company.domain.ilike(domain)).first()
        if not company:
            continue
        from .models import User
        user = User.query.filter_by(email=sender_email).first()
        if not user:
            # ignore unknown user for now
            continue
        # get body text
        body = ''
        if msg.is_multipart():
            for part in msg.walk():
                ctype = part.get_content_type()
                disp = part.get('Content-Disposition', '') or ''
                if ctype == 'text/plain' and 'attachment' not in disp:
                    charset = part.get_content_charset() or 'utf-8'
                    try:
                        body = part.get_payload(decode=True).decode(charset, errors='ignore')
                    except Exception:
                        body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                    break
        else:
            charset = msg.get_content_charset() or 'utf-8'
            try:
                body = msg.get_payload(decode=True).decode(charset, errors='ignore')
            except Exception:
                body = msg.get_payload(decode=True)

        # find ticket number
        m = TICKET_PATTERN.search(subject or '')
        ticket = None
        if m:
            ticket = Ticket.query.filter_by(number=m.group(0)).first()
        if ticket:
            # comment
            comment = TicketComment(ticket_id=ticket.id, user_id=user.id, content=body, internal=False)
            db.session.add(comment)
            db.session.commit()
        else:
            # create new ticket
            new_t = Ticket(
                number=f"TCK-{datetime.utcnow().strftime('%Y%m%d')}-{__import__('uuid').uuid4().hex[:6].upper()}",
                title=subject[:200] if subject else 'Chamado via e-mail',
                description=body or subject or 'Sem conteúdo',
                priority='Média',
                company_id=company.id,
                created_by_id=user.id,
                status='Novo'
            )
            db.session.add(new_t)
            db.session.commit()
        conn.store(num, '+FLAGS', '\\Seen')
        count += 1
    conn.logout()
    return count


def run_automations():
    now = datetime.utcnow()
    overdue = Ticket.query.filter(Ticket.due_resolution_at != None, Ticket.resolved_at == None, Ticket.due_resolution_at < now).all()  # noqa: E711
    for t in overdue:
        # simple escalation: set status to 'Aguardando' if not already and log
        if t.status not in ('Resolvido', 'Fechado'):
            old = t.status
            t.status = 'Aguardando'
            db.session.commit()
            audit('ticket', t.id, 'escalate_overdue', data=f'status {old} -> {t.status}')


def run_retention():
    from .models import Company, Attachment
    companies = Company.query.all()
    removed_files = 0
    anonymized_comments = 0
    for comp in companies:
        days = comp.retention_days or 0
        if days <= 0:
            continue
        cutoff = datetime.utcnow() - timedelta(days=days)
        old_tickets = Ticket.query.filter(
            Ticket.company_id == comp.id,
            Ticket.closed_at != None,  # noqa: E711
            Ticket.closed_at < cutoff
        ).all()
        for t in old_tickets:
            # remove attachments from disk and db
            atts = list(t.attachments)
            for att in atts:
                upload_dir = os.path.join(current_app.root_path, 'uploads', str(t.id))
                fpath = os.path.join(upload_dir, att.filename)
                try:
                    if os.path.exists(fpath):
                        os.remove(fpath)
                        removed_files += 1
                except Exception:
                    pass
                db.session.delete(att)
            # anonymize comments content
            for c in t.comments:
                if c.content and c.content != '[removido por retenção]':
                    c.content = '[removido por retenção]'
                    anonymized_comments += 1
        db.session.commit()
    current_app.logger.info(f"Retention executed: files removed={removed_files}, comments anonymized={anonymized_comments}")
