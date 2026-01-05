from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app, Response, stream_with_context
from flask_login import login_required, current_user
from .. import db
from ..models import Ticket, TicketComment
from ..tickets.forms import CommentForm
from datetime import datetime
import json
import time


chat_bp = Blueprint('chat', __name__, template_folder='../templates')


@chat_bp.route('/')
@login_required
def index():
    # User tickets
    if current_user.role in ('admin','supervisor','tech'):
        tickets = Ticket.query.filter_by(company_id=current_user.company_id).order_by(Ticket.updated_at.desc()).limit(50).all()
    else:
        tickets = Ticket.query.filter_by(created_by_id=current_user.id).order_by(Ticket.updated_at.desc()).limit(50).all()
    ticket_id = request.args.get('ticket_id', type=int)
    active = Ticket.query.get(ticket_id) if ticket_id else (tickets[0] if tickets else None)
    comments = []
    if active:
        comments = active.comments
        if current_user.role == 'client':
            comments = [c for c in comments if not c.internal]
    form = CommentForm()
    return render_template('chat/index.html', tickets=tickets, active=active, comments=comments, form=form)


@chat_bp.route('/poll')
@login_required
def poll():
    ticket_id = request.args.get('ticket_id', type=int)
    after = request.args.get('after', type=int) or 0
    if not ticket_id:
        return jsonify({'ok': True, 'items': []})
    ticket = Ticket.query.get_or_404(ticket_id)
    # clients can only see own ticket
    if current_user.role == 'client' and ticket.created_by_id != current_user.id:
        return jsonify({'ok': False, 'error': 'forbidden'}), 403
    q = TicketComment.query.filter_by(ticket_id=ticket.id)
    if current_user.role == 'client':
        q = q.filter_by(internal=False)
    if after:
        q = q.filter(TicketComment.id > after)
    items = q.order_by(TicketComment.id.asc()).all()
    def fmt(dt):
        try:
            return dt.strftime('%d/%m/%Y %H:%M') if dt else ''
        except Exception:
            return ''
    data = [{
        'id': c.id,
        'user_id': c.user_id,
        'user_name': getattr(c.user, 'name', 'Usuário'),
        'content': c.content,
        'created_at': fmt(c.created_at),
    } for c in items]
    return jsonify({'ok': True, 'items': data})


@chat_bp.route('/stream')
@login_required
def stream():
    ticket_id = request.args.get('ticket_id', type=int)
    after = request.args.get('after', type=int) or 0
    if not ticket_id:
        return jsonify({'ok': True, 'items': []})
    ticket = Ticket.query.get_or_404(ticket_id)
    if current_user.role == 'client' and ticket.created_by_id != current_user.id:
        return jsonify({'ok': False, 'error': 'forbidden'}), 403
    def gen():
        last = after
        for _ in range(720):  # ~60 min @5s
            q = TicketComment.query.filter_by(ticket_id=ticket.id)
            if current_user.role == 'client':
                q = q.filter_by(internal=False)
            if last:
                q = q.filter(TicketComment.id > last)
            items = q.order_by(TicketComment.id.asc()).all()
            if items:
                last = max(last, max(c.id for c in items))
            def fmt(dt):
                try:
                    return dt.strftime('%d/%m/%Y %H:%M') if dt else ''
                except Exception:
                    return ''
            data = [{
                'id': c.id,
                'user_id': c.user_id,
                'user_name': getattr(c.user, 'name', 'Usuário'),
                'content': c.content,
                'created_at': fmt(c.created_at),
            } for c in items]
            yield f"data: {json.dumps({'ok': True, 'items': data})}\n\n"
            time.sleep(5)
    return Response(stream_with_context(gen()), mimetype='text/event-stream')


@chat_bp.route('/send', methods=['POST'])
@login_required
def send():
    text = request.form.get('content', '').strip()
    internal = bool(request.form.get('internal')) if current_user.role in ('admin','supervisor','tech') else False
    ticket_id = request.form.get('ticket_id', type=int)
    if not text:
        flash('Mensagem vazia.', 'warning')
        return redirect(url_for('chat.index', ticket_id=ticket_id) if ticket_id else url_for('chat.index'))
    if ticket_id:
        ticket = Ticket.query.get_or_404(ticket_id)
        # clients can only message own tickets
        if current_user.role == 'client' and ticket.created_by_id != current_user.id:
            flash('Permissão negada.', 'danger')
            return redirect(url_for('chat.index'))
        # Block interaction on closed tickets
        if ticket.status == 'Fechado':
            flash('Chamado encerrado. Para interagir, reabra o chamado.', 'warning')
            return redirect(url_for('chat.index', ticket_id=ticket.id))
        # Only assigned tech can interact when there is a responsible (admins/supervisors allowed)
        if ticket.assigned_to_id and current_user.role == 'tech' and current_user.id != ticket.assigned_to_id:
            flash('Este chamado está em atendimento por outro técnico. Solicite transferência.', 'warning')
            return redirect(url_for('chat.index', ticket_id=ticket.id))
        c = TicketComment(ticket_id=ticket.id, user_id=current_user.id, content=text, internal=internal)
        db.session.add(c)
        ticket.updated_at = datetime.utcnow()
        db.session.commit()
        flash('Mensagem enviada.', 'success')
        return redirect(url_for('chat.index', ticket_id=ticket.id))
    # No ticket: create one
    title = (text[:80] + '...') if len(text) > 80 else text
    t = Ticket(
        number=f"TCK-{datetime.utcnow().strftime('%Y%m%d')}-{__import__('uuid').uuid4().hex[:6].upper()}",
        title=title or 'Chat - Novo chamado',
        description=text,
        priority='Média',
        company_id=current_user.company_id,
        created_by_id=current_user.id,
        status='Novo'
    )
    db.session.add(t)
    db.session.commit()
    c = TicketComment(ticket_id=t.id, user_id=current_user.id, content=text, internal=False)
    db.session.add(c)
    db.session.commit()
    flash('Chamado criado a partir do chat.', 'success')
    return redirect(url_for('chat.index', ticket_id=t.id))


@chat_bp.route('/webhook/whatsapp', methods=['POST'])
def whatsapp_webhook():
    # Stub: expects JSON {"from":"+55...","text":"..."}
    data = request.get_json(silent=True) or {}
    sender = (data.get('from') or '').strip()
    text = (data.get('text') or '').strip()
    if not text:
        return jsonify({'status':'ignored'}), 200
    # naive: cannot map to company without domain. Just create a system ticket without user mapping.
    t = Ticket(
        number=f"TCK-{datetime.utcnow().strftime('%Y%m%d')}-{__import__('uuid').uuid4().hex[:6].upper()}",
        title=f"WhatsApp de {sender}",
        description=text,
        priority='Média',
        company_id=1,  # default company id; adjust mapping as needed
        created_by_id=1,  # system user placeholder
        status='Novo'
    )
    db.session.add(t)
    db.session.commit()
    current_app.logger.info(f"WhatsApp webhook created ticket {t.number} from {sender}")
    return jsonify({'status':'ok','ticket':t.number}), 200
