import os
import uuid
from datetime import datetime, timedelta
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, send_from_directory, abort, jsonify, Response, stream_with_context
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from .. import db
from ..models import Ticket, Attachment, TicketComment, Contract, Category, User, Queue, Asset, CommentReaction, Notification, TicketParticipant
from .forms import TicketCreateForm, CommentForm, AssignForm, ResolveForm, CloseForm
from ..utils import choose_sla_plan, audit
from ..email import send_ticket_created, send_ticket_comment, send_ticket_status, send_ticket_closed
import secrets
import json
import time
from sqlalchemy import or_, inspect as sqla_inspect


tickets_bp = Blueprint('tickets', __name__, template_folder='../templates')


def _ticket_number():
    date = datetime.utcnow().strftime('%Y%m%d')
    seq = uuid.uuid4().hex[:6].upper()
    return f'TCK-{date}-{seq}'


def _ensure_ticket_access(ticket):
    if current_user.role in ('admin', 'supervisor', 'tech'):
        return
    else:
        # client: only own tickets in same company
        if ticket.company_id != current_user.company_id or ticket.created_by_id != current_user.id:
            abort(403)


def _participants_enabled():
    try:
        return sqla_inspect(db.engine).has_table('ticket_participant')
    except Exception:
        return False


def _is_participant(ticket, user):
    if not _participants_enabled():
        return False
    try:
        return any(p.user_id == user.id for p in getattr(ticket, 'participants', []) or [])
    except Exception:
        return False


@tickets_bp.route('/')
@login_required
def list_tickets():
    if current_user.role in ('admin', 'supervisor', 'tech'):
        # Staff: visão global (técnicos são gerais do sistema)
        tickets_all = Ticket.query.order_by(Ticket.created_at.desc()).all()
        # Agrupamentos
        def group_by_company(items):
            groups = {}
            for t in items:
                key = t.company.name if t.company else '—'
                groups.setdefault(key, []).append(t)
            return groups
        # Para todos os perfis de staff (tech/supervisor/admin), usar visão global
        unassigned = [t for t in tickets_all if t.assigned_to_id is None]
        in_progress = [t for t in tickets_all if (t.assigned_to_id is not None and t.status not in ('Resolvido', 'Fechado'))]
        closed = [t for t in tickets_all if t.status in ('Resolvido', 'Fechado')]
        tickets = tickets_all
        return render_template(
            'tickets/list.html',
            tickets=tickets,
            unassigned_by_company=group_by_company(unassigned),
            in_progress_by_company=group_by_company(in_progress),
            closed_by_company=group_by_company(closed),
        )
    else:
        tickets = Ticket.query.filter_by(company_id=current_user.company_id, created_by_id=current_user.id).order_by(Ticket.created_at.desc()).all()
        return render_template('tickets/list.html', tickets=tickets)


@tickets_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create_ticket():
    # Block ticket creation for inactive companies
    if not getattr(current_user.company, 'active', True):
        flash('Sua empresa está inativa. Abertura de chamados está temporariamente bloqueada.', 'warning')
        return redirect(url_for('tickets.list_tickets'))
    form = TicketCreateForm()
    # Populate choices
    contracts = Contract.query.filter_by(company_id=current_user.company_id, active=True).order_by(Contract.name).all()
    form.contract_id.choices = [(0, '— Sem contrato —')] + [(c.id, c.name) for c in contracts]
    parents = Category.query.filter(
        Category.parent_id.is_(None),
        or_(Category.company_id.is_(None), Category.company_id == current_user.company_id)
    ).order_by(Category.name).all()
    form.cat_parent_id.choices = [(0, '— Sem categoria —')] + [(c.id, c.name) for c in parents]
    # Children depend on selected parent (on GET default 0)
    selected_parent_id = request.form.get('cat_parent_id', type=int)
    if not selected_parent_id:
        selected_parent_id = 0
    children = []
    if selected_parent_id:
        children = Category.query.filter(
            Category.parent_id == selected_parent_id,
            or_(Category.company_id.is_(None), Category.company_id == current_user.company_id)
        ).order_by(Category.name).all()
    form.cat_child_id.choices = [(0, '— Sem subcategoria —')] + [(c.id, c.name) for c in children]
    queues = Queue.query.filter_by(company_id=current_user.company_id, active=True).order_by(Queue.name).all()
    form.queue_id.choices = [(0, '— Sem fila —')] + [(q.id, q.name) for q in queues]
    assets = Asset.query.filter_by(company_id=current_user.company_id, active=True).order_by(Asset.name).all()
    form.asset_id.choices = [(0, '— Sem ativo —')] + [(a.id, a.name) for a in assets]
    if form.validate_on_submit():
        now = datetime.utcnow()
        parent_cat = Category.query.get(form.cat_parent_id.data) if form.cat_parent_id.data else None
        child_cat = Category.query.get(form.cat_child_id.data) if form.cat_child_id.data else None
        ticket = Ticket(
            number=_ticket_number(),
            title=form.title.data,
            description=form.description.data,
            priority=form.priority.data,
            category=(parent_cat.name if parent_cat else None),
            subcategory=(child_cat.name if child_cat else None),
            company_id=current_user.company_id,
            created_by_id=current_user.id,
            status='Novo',
            contract_id=(form.contract_id.data or None) if form.contract_id.data != 0 else None,
            queue_id=(form.queue_id.data or None) if form.queue_id.data != 0 else None,
            asset_id=(form.asset_id.data or None) if form.asset_id.data != 0 else None,
            created_at=now
        )
        # Optional catalog category
        selected_cat_id = (child_cat.id if child_cat else (parent_cat.id if parent_cat else None))
        db.session.add(ticket)
        db.session.commit()

        # save attachments
        files = form.attachments.data or []
        if files:
            upload_dir = os.path.join(current_app.root_path, 'uploads', str(ticket.id))
            os.makedirs(upload_dir, exist_ok=True)
            for f in files:
                if not f:
                    continue
                original = secure_filename(f.filename)
                if not original:
                    continue
                ext = os.path.splitext(original)[1]
                stored = uuid.uuid4().hex + ext
                path = os.path.join(upload_dir, stored)
                f.save(path)
                att = Attachment(ticket_id=ticket.id, filename=stored, original_name=original, content_type=f.mimetype, size=os.path.getsize(path))
                db.session.add(att)
            db.session.commit()
        # Apply SLA
        plan = choose_sla_plan(company_id=current_user.company_id, contract_id=ticket.contract_id, category_id=selected_cat_id, priority=ticket.priority)
        if plan:
            ticket.sla_plan_id = plan.id
            ticket.due_first_response_at = ticket.created_at + timedelta(minutes=plan.first_response_minutes or 0)
            ticket.due_resolution_at = ticket.created_at + timedelta(minutes=plan.resolution_minutes or 0)
        db.session.commit()
        audit('ticket', ticket.id, 'create', user_id=current_user.id)
        # Notify creator and company admins (+ extra recipients via env)
        try:
            admin_emails = [u.email for u in User.query.filter_by(company_id=current_user.company_id, role='admin').all()]
            # Remove creator from watchers and dedupe
            creator_email = (current_user.email or '').lower()
            extra = current_app.config.get('NOTIFY_TICKETS_TO', []) or []
            base = set(e for e in admin_emails if (e or '').lower() != creator_email)
            for e in extra:
                if (e or '').lower() != creator_email:
                    base.add(e)
            watchers = list(base)
            send_ticket_created(ticket, creator=current_user, watchers=watchers)
        except Exception as e:
            current_app.logger.warning(f"Failed to send ticket created email: {e}")
        flash('Chamado criado com sucesso.', 'success')
        return redirect(url_for('tickets.detail', ticket_id=ticket.id))
    # GET inicial ou POST inválido
    return render_template('tickets/create.html', form=form)


@tickets_bp.route('/<int:ticket_id>/participants/add', methods=['POST'])
@login_required
def add_participant(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    _ensure_ticket_access(ticket)
    if not _participants_enabled():
        abort(404)
    # Só responsável, supervisor ou admin podem convidar
    if not (
        current_user.role in ('admin','supervisor') or
        (current_user.role == 'tech' and ticket.assigned_to_id == current_user.id)
    ):
        abort(403)
    user_id = request.form.get('user_id', type=int)
    if not user_id:
        flash('Seleção inválida.', 'warning')
        return redirect(url_for('tickets.detail', ticket_id=ticket.id))
    if ticket.assigned_to_id and user_id == ticket.assigned_to_id:
        flash('Usuário já é o responsável.', 'info')
        return redirect(url_for('tickets.detail', ticket_id=ticket.id))
    exists = TicketParticipant.query.filter_by(ticket_id=ticket.id, user_id=user_id).first()
    if exists:
        flash('Este usuário já é participante.', 'info')
        return redirect(url_for('tickets.detail', ticket_id=ticket.id))
    p = TicketParticipant(ticket_id=ticket.id, user_id=user_id, role='guest')
    db.session.add(p)
    db.session.commit()
    audit('ticket', ticket.id, 'participant_add', user_id=current_user.id, data=f'user_id={user_id}')
    flash('Participante adicionado.', 'success')
    return redirect(url_for('tickets.detail', ticket_id=ticket.id))


@tickets_bp.route('/<int:ticket_id>/participants/<int:participant_id>/remove', methods=['POST'])
@login_required
def remove_participant(ticket_id, participant_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    _ensure_ticket_access(ticket)
    if not _participants_enabled():
        abort(404)
    # Só responsável, supervisor ou admin podem remover
    if not (
        current_user.role in ('admin','supervisor') or
        (current_user.role == 'tech' and ticket.assigned_to_id == current_user.id)
    ):
        abort(403)
    part = TicketParticipant.query.filter_by(id=participant_id, ticket_id=ticket.id).first_or_404()
    db.session.delete(part)
    db.session.commit()
    audit('ticket', ticket.id, 'participant_remove', user_id=current_user.id, data=f'participant_id={participant_id}')
    flash('Participante removido.', 'success')
    return redirect(url_for('tickets.detail', ticket_id=ticket.id))

    


@tickets_bp.route('/categories/children')
@login_required
def categories_children():
    parent_id = request.args.get('parent_id', type=int)
    if not parent_id:
        return jsonify({'ok': True, 'items': []})
    items = Category.query.filter(
        Category.parent_id == parent_id,
        or_(Category.company_id.is_(None), Category.company_id == current_user.company_id)
    ).order_by(Category.name).all()
    data = [{'id': c.id, 'name': c.name} for c in items]
    return jsonify({'ok': True, 'items': data})


@tickets_bp.route('/<int:ticket_id>/comments/poll')
@login_required
def poll_comments(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    _ensure_ticket_access(ticket)
    after = request.args.get('after', type=int) or 0
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
        'internal': c.internal,
    } for c in items]
    return jsonify({'ok': True, 'items': data})


@tickets_bp.route('/<int:ticket_id>/comments/stream')
@login_required
def stream_comments(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    _ensure_ticket_access(ticket)
    after = request.args.get('after', type=int) or 0
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
                'internal': c.internal,
            } for c in items]
            payload = json.dumps({'ok': True, 'items': data})
            yield f"data: {payload}\n\n"
            time.sleep(5)
    return Response(stream_with_context(gen()), mimetype='text/event-stream')


@tickets_bp.route('/<int:ticket_id>', methods=['GET', 'POST'])
@login_required
def detail(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    _ensure_ticket_access(ticket)
    form = CommentForm()
    assign_form = None
    resolve_form = None
    close_form = None
    if current_user.role in ('admin', 'supervisor', 'tech'):
        assign_form = AssignForm()
        staff = User.query.filter(User.role.in_(['tech','supervisor','admin'])).order_by(User.name).all()
        assign_form.assignee_id.choices = [(0, '— Não atribuído —')] + [(u.id, u.name) for u in staff]
        assign_form.status.data = ticket.status
        # queues
        queues = Queue.query.order_by(Queue.name).all()
        assign_form.queue_id.choices = [(0, '— Sem fila —')] + [(q.id, q.name) for q in queues]
        assign_form.queue_id.data = ticket.queue_id or 0
        resolve_form = ResolveForm()
        close_form = CloseForm()

    # Block any new comment if ticket is closed
    if request.method == 'POST' and ticket.status == 'Fechado':
        flash('Chamado encerrado. Para interagir, reabra o chamado.', 'warning')
        return redirect(url_for('tickets.detail', ticket_id=ticket.id))

    if form.validate_on_submit():
        # Apenas o técnico designado pode interagir quando houver responsável (admin/supervisor têm permissão)
        # Técnicos convidados (participantes) também podem interagir
        if ticket.assigned_to_id and current_user.role == 'tech' and current_user.id != ticket.assigned_to_id and not _is_participant(ticket, current_user):
            flash('Este chamado está em atendimento por outro técnico. Solicite transferência ou convite.', 'warning')
            return redirect(url_for('tickets.detail', ticket_id=ticket.id))
        # New comment
        comment = TicketComment(ticket_id=ticket.id, user_id=current_user.id, content=form.content.data, internal=form.internal.data)
        db.session.add(comment)
        # First response timestamp (by staff, public or internal) if not set
        if not ticket.first_response_at and current_user.role in ('admin','supervisor','tech'):
            ticket.first_response_at = datetime.utcnow()
        db.session.commit()
        files = form.attachments.data or []
        if files:
            upload_dir = os.path.join(current_app.root_path, 'uploads', str(ticket.id))
            os.makedirs(upload_dir, exist_ok=True)
            for f in files:
                if not f:
                    continue
                original = secure_filename(f.filename)
                if not original:
                    continue
                ext = os.path.splitext(original)[1]
                stored = uuid.uuid4().hex + ext
                path = os.path.join(upload_dir, stored)
                f.save(path)
                att = Attachment(ticket_id=ticket.id, filename=stored, original_name=original, content_type=f.mimetype, size=os.path.getsize(path))
                db.session.add(att)
            db.session.commit()
        try:
            send_ticket_comment(ticket, author=current_user, public=not form.internal.data)
        except Exception as e:
            current_app.logger.warning(f"Failed to send ticket comment email: {e}")
        # In-app notifications: notify counterpart on public comments
        try:
            if not form.internal.data:
                if current_user.role in ('admin','supervisor','tech'):
                    # notify creator
                    db.session.add(Notification(
                        user_id=ticket.created_by_id,
                        company_id=ticket.company_id,
                        kind='ticket_comment',
                        title=f"Novo comentário em {ticket.number}",
                        body=f"{current_user.name}: {form.content.data[:120]}",
                        link=url_for('tickets.detail', ticket_id=ticket.id)
                    ))
                else:
                    # notify assignee (if any)
                    if ticket.assigned_to_id:
                        db.session.add(Notification(
                            user_id=ticket.assigned_to_id,
                            company_id=ticket.company_id,
                            kind='ticket_comment',
                            title=f"Novo comentário do cliente em {ticket.number}",
                            body=f"{current_user.name}: {form.content.data[:120]}",
                            link=url_for('tickets.detail', ticket_id=ticket.id)
                        ))
                db.session.commit()
        except Exception:
            pass
        flash('Comentário adicionado.', 'success')
        return redirect(url_for('tickets.detail', ticket_id=ticket.id))

    comments = ticket.comments
    if current_user.role == 'client':
        comments = [c for c in comments if not c.internal]
    # Staff interaction permission (front-end hints): admin/supervisor sempre; técnico somente se responsável (ou sem responsável)
    can_staff_interact = False
    if current_user.role in ('admin','supervisor'):
        can_staff_interact = True
    elif current_user.role == 'tech':
        can_staff_interact = (ticket.assigned_to_id is None) or (ticket.assigned_to_id == current_user.id) or _is_participant(ticket, current_user)
    # Participants data for UI
    participants_enabled = _participants_enabled()
    participants = ticket.participants if participants_enabled else []
    # build list of staff to invite (same company, not already participant, not assignee)
    candidates = []
    transfer_candidates = []
    if current_user.role in ('admin','supervisor') or (current_user.role == 'tech' and (ticket.assigned_to_id == current_user.id)):
        staff = User.query.filter(User.role.in_(['tech','supervisor','admin'])).order_by(User.name).all()
        existing_ids = {p.user_id for p in participants}
        if ticket.assigned_to_id:
            existing_ids.add(ticket.assigned_to_id)
        candidates = [u for u in staff if u.id not in existing_ids]
        transfer_candidates = [u for u in staff if not (ticket.assigned_to_id and u.id == ticket.assigned_to_id)]
    return render_template('tickets/detail.html', ticket=ticket, form=form, assign_form=assign_form, resolve_form=resolve_form, close_form=close_form, comments=comments, can_staff_interact=can_staff_interact, participants_enabled=participants_enabled, participants=participants, participant_candidates=candidates, transfer_candidates=transfer_candidates)


@tickets_bp.route('/<int:ticket_id>/attachments/<int:attachment_id>')
@login_required
def download_attachment(ticket_id, attachment_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    _ensure_ticket_access(ticket)
    att = Attachment.query.filter_by(id=attachment_id, ticket_id=ticket_id).first_or_404()
    directory = os.path.join(current_app.root_path, 'uploads', str(ticket.id))
    return send_from_directory(directory, att.filename, as_attachment=True, download_name=att.original_name)


@tickets_bp.route('/<int:ticket_id>/attachments/<int:attachment_id>/view')
@login_required
def view_attachment(ticket_id, attachment_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    _ensure_ticket_access(ticket)
    att = Attachment.query.filter_by(id=attachment_id, ticket_id=ticket_id).first_or_404()
    directory = os.path.join(current_app.root_path, 'uploads', str(ticket.id))
    # Let browser decide how to render (image/pdf etc.).
    return send_from_directory(directory, att.filename, as_attachment=False)


@tickets_bp.route('/<int:ticket_id>/comments/<int:comment_id>/react', methods=['POST'])
@login_required
def react_comment(ticket_id, comment_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    _ensure_ticket_access(ticket)
    if ticket.status == 'Fechado':
        return jsonify({'ok': False, 'error': 'ticket closed'}), 400
    # Bloqueia interação de técnico não responsável, exceto se for participante convidado
    if ticket.assigned_to_id and current_user.role == 'tech' and current_user.id != ticket.assigned_to_id and not _is_participant(ticket, current_user):
        return jsonify({'ok': False, 'error': 'somente o técnico responsável pode interagir'}), 403
    comment = TicketComment.query.filter_by(id=comment_id, ticket_id=ticket_id).first_or_404()
    emoji = (request.form.get('emoji') or '').strip()
    if not emoji:
        return jsonify({'ok': False, 'error': 'emoji missing'}), 400
    existing = CommentReaction.query.filter_by(comment_id=comment.id, user_id=current_user.id, emoji=emoji).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
    else:
        r = CommentReaction(comment_id=comment.id, user_id=current_user.id, emoji=emoji)
        db.session.add(r)
        db.session.commit()
    # Return aggregated counts
    counts = {}
    for r in comment.reactions:
        counts[r.emoji] = counts.get(r.emoji, 0) + 1
    return jsonify({'ok': True, 'counts': counts})


@tickets_bp.route('/<int:ticket_id>/comments/<int:comment_id>/reactions')
@login_required
def get_comment_reactions(ticket_id, comment_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    _ensure_ticket_access(ticket)
    comment = TicketComment.query.filter_by(id=comment_id, ticket_id=ticket_id).first_or_404()
    counts = {}
    for r in comment.reactions:
        counts[r.emoji] = counts.get(r.emoji, 0) + 1
    return jsonify({'ok': True, 'counts': counts})


@tickets_bp.route('/<int:ticket_id>/assign', methods=['POST'])
@login_required
def assign(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    _ensure_ticket_access(ticket)
    if current_user.role not in ('admin','supervisor','tech'):
        abort(403)
    # Tecnico que nao é o responsável atual nao pode reatribuir quando já houver responsável
    if current_user.role == 'tech' and ticket.assigned_to_id and ticket.assigned_to_id != current_user.id:
        flash('Somente o técnico responsável, supervisor ou admin podem transferir este chamado.', 'warning')
        return redirect(url_for('tickets.detail', ticket_id=ticket.id))
    form = AssignForm()
    staff = User.query.filter(User.role.in_(['tech','supervisor','admin'])).all()
    form.assignee_id.choices = [(0,'—')] + [(u.id, u.name) for u in staff]
    queues = Queue.query.order_by(Queue.name).all()
    form.queue_id.choices = [(0,'— Sem fila —')] + [(q.id, q.name) for q in queues]
    if form.validate_on_submit():
        old_status = ticket.status
        ticket.assigned_to_id = form.assignee_id.data or None
        ticket.status = form.status.data
        ticket.queue_id = form.queue_id.data or None
        db.session.commit()
        audit('ticket', ticket.id, 'assign/status', user_id=current_user.id, data=f"assignee={ticket.assigned_to_id}; status={ticket.status}")
        if old_status != ticket.status:
            try:
                send_ticket_status(ticket, actor=current_user, old_status=old_status, new_status=ticket.status)
            except Exception as e:
                current_app.logger.warning(f"Failed to send status email: {e}")
            # Notify creator about status change
            try:
                db.session.add(Notification(
                    user_id=ticket.created_by_id,
                    company_id=ticket.company_id,
                    kind='ticket_status',
                    title=f"Status atualizado: {ticket.number}",
                    body=f"{old_status} 806 {ticket.status}",
                    link=url_for('tickets.detail', ticket_id=ticket.id)
                ))
                db.session.commit()
            except Exception:
                pass
        flash('Atualização aplicada.', 'success')
    return redirect(url_for('tickets.detail', ticket_id=ticket.id))


@tickets_bp.route('/<int:ticket_id>/resolve', methods=['POST'])
@login_required
def resolve(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    _ensure_ticket_access(ticket)
    if current_user.role not in ('admin','supervisor','tech'):
        abort(403)
    # Apenas técnico responsável (ou admin/supervisor) pode resolver
    if current_user.role == 'tech' and ticket.assigned_to_id and ticket.assigned_to_id != current_user.id:
        flash('Este chamado está em atendimento por outro técnico. Solicite transferência.', 'warning')
        return redirect(url_for('tickets.detail', ticket_id=ticket.id))
    form = ResolveForm()
    if form.validate_on_submit():
        old_status = ticket.status
        ticket.solution = form.solution.data
        ticket.status = 'Resolvido'
        ticket.resolved_at = datetime.utcnow()
        db.session.commit()
        audit('ticket', ticket.id, 'resolve', user_id=current_user.id)
        try:
            send_ticket_status(ticket, actor=current_user, old_status=old_status, new_status=ticket.status)
        except Exception as e:
            current_app.logger.warning(f"Failed to send status email: {e}")
        # Notify creator about resolution
        try:
            db.session.add(Notification(
                user_id=ticket.created_by_id,
                company_id=ticket.company_id,
                kind='ticket_status',
                title=f"Ticket resolvido: {ticket.number}",
                body=f"{ticket.title}",
                link=url_for('tickets.detail', ticket_id=ticket.id)
            ))
            db.session.commit()
        except Exception:
            pass
        flash('Chamado marcado como resolvido.', 'success')
    return redirect(url_for('tickets.detail', ticket_id=ticket.id))


@tickets_bp.route('/<int:ticket_id>/close', methods=['POST'])
@login_required
def close(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    _ensure_ticket_access(ticket)
    if current_user.role not in ('admin','supervisor','tech'):
        abort(403)
    # Apenas técnico responsável (ou admin/supervisor) pode encerrar
    if current_user.role == 'tech' and ticket.assigned_to_id and ticket.assigned_to_id != current_user.id:
        flash('Este chamado está em atendimento por outro técnico. Solicite transferência.', 'warning')
        return redirect(url_for('tickets.detail', ticket_id=ticket.id))
    form = CloseForm()
    if form.validate_on_submit():
        old_status = ticket.status
        # Require technician evaluation fields
        ticket.closed_reason = form.reason.data
        ticket.tech_evaluation = form.tech_evaluation.data
        ticket.tech_eval_category = form.tech_eval_category.data
        ticket.status = 'Fechado'
        ticket.closed_at = datetime.utcnow()
        # Generate rating token for user feedback
        if not ticket.user_rating_at:
            ticket.user_rating_token = secrets.token_hex(16)
        db.session.commit()
        audit('ticket', ticket.id, 'close', user_id=current_user.id)
        try:
            # Status email
            send_ticket_status(ticket, actor=current_user, old_status=old_status, new_status=ticket.status)
            # Build public transcript (description + public comments)
            lines = []
            lines.append(f"Descrição: {ticket.description}")
            for c in TicketComment.query.filter_by(ticket_id=ticket.id).order_by(TicketComment.created_at.asc()).all():
                if c.internal:
                    continue
                who = c.user.name if c.user else 'Usuário'
                when = c.created_at.strftime('%d/%m/%Y %H:%M') if c.created_at else ''
                lines.append(f"[{when}] {who}: {c.content}")
            rating_link = url_for('tickets.rate_by_token', token=ticket.user_rating_token, _external=True)
            send_ticket_closed(ticket, actor=current_user, transcript_lines=lines, rating_link=rating_link)
            # Create in-app notification for creator
            try:
                note = Notification(
                    user_id=ticket.created_by_id,
                    company_id=ticket.company_id,
                    kind='ticket_closed',
                    title=f"Ticket encerrado: {ticket.number}",
                    body=f"{ticket.title}",
                    link=url_for('tickets.detail', ticket_id=ticket.id)
                )
                db.session.add(note)
                db.session.commit()
            except Exception:
                pass
        except Exception as e:
            current_app.logger.warning(f"Failed to send close email: {e}")
        flash('Chamado encerrado.', 'success')
    return redirect(url_for('tickets.detail', ticket_id=ticket.id))


@tickets_bp.route('/rate/<token>', methods=['GET', 'POST'])
def rate_by_token(token):
    ticket = Ticket.query.filter_by(user_rating_token=token).first()
    if not ticket:
        flash('Token inválido ou avaliação já realizada.', 'warning')
        return redirect(url_for('main.index'))
    if ticket.user_rating_at:
        flash('Este ticket já foi avaliado.', 'info')
        return redirect(url_for('main.index'))
    from .forms import RatingForm
    form = RatingForm()
    if form.validate_on_submit():
        ticket.user_rating = int(form.rating.data)
        ticket.user_rating_comment = form.comment.data
        ticket.user_rating_at = datetime.utcnow()
        db.session.commit()
        flash('Obrigado pela sua avaliação!', 'success')
        return redirect(url_for('main.index'))
    return render_template('tickets/rate.html', form=form, ticket=ticket)


@tickets_bp.route('/<int:ticket_id>/rate', methods=['GET', 'POST'])
@login_required
def rate_auth(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    _ensure_ticket_access(ticket)
    # Only creator can rate
    if ticket.created_by_id != current_user.id:
        abort(403)
    if ticket.status != 'Fechado':
        flash('Ticket ainda não está encerrado.', 'warning')
        return redirect(url_for('tickets.detail', ticket_id=ticket.id))
    if ticket.user_rating_at:
        flash('Você já avaliou este ticket.', 'info')
        return redirect(url_for('tickets.detail', ticket_id=ticket.id))
    from .forms import RatingForm
    form = RatingForm()
    if form.validate_on_submit():
        ticket.user_rating = int(form.rating.data)
        ticket.user_rating_comment = form.comment.data
        ticket.user_rating_at = datetime.utcnow()
        db.session.commit()
        flash('Obrigado pela sua avaliação!', 'success')
        return redirect(url_for('tickets.detail', ticket_id=ticket.id))
    return render_template('tickets/rate.html', form=form, ticket=ticket)


@tickets_bp.route('/<int:ticket_id>/reopen', methods=['POST'])
@login_required
def reopen(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    _ensure_ticket_access(ticket)
    if current_user.role not in ('admin','supervisor','tech'):
        abort(403)
    if ticket.status not in ('Resolvido','Fechado'):
        flash('Chamado não está resolvido/fechado.', 'warning')
        return redirect(url_for('tickets.detail', ticket_id=ticket.id))
    old_status = ticket.status
    ticket.status = 'Em atendimento'
    ticket.closed_at = None
    ticket.closed_reason = None
    db.session.commit()
    audit('ticket', ticket.id, 'reopen', user_id=current_user.id)
    try:
        send_ticket_status(ticket, actor=current_user, old_status=old_status, new_status=ticket.status)
    except Exception as e:
        current_app.logger.warning(f"Failed to send status email: {e}")
    flash('Chamado reaberto.', 'success')
    return redirect(url_for('tickets.detail', ticket_id=ticket.id))


@tickets_bp.route('/<int:ticket_id>/pause_sla', methods=['POST'])
@login_required
def pause_sla(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    _ensure_ticket_access(ticket)
    if current_user.role not in ('admin','supervisor','tech'):
        abort(403)
    if not ticket.sla_paused:
        ticket.sla_paused = True
        ticket.sla_paused_since = datetime.utcnow()
        db.session.commit()
        audit('ticket', ticket.id, 'sla_pause', user_id=current_user.id)
        flash('SLA pausado.', 'success')
    return redirect(url_for('tickets.detail', ticket_id=ticket.id))


@tickets_bp.route('/<int:ticket_id>/resume_sla', methods=['POST'])
@login_required
def resume_sla(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    _ensure_ticket_access(ticket)
    if current_user.role not in ('admin','supervisor','tech'):
        abort(403)
    if ticket.sla_paused:
        # Push due dates by paused duration
        paused_for = datetime.utcnow() - (ticket.sla_paused_since or datetime.utcnow())
        if ticket.due_first_response_at:
            ticket.due_first_response_at = ticket.due_first_response_at + paused_for
        if ticket.due_resolution_at:
            ticket.due_resolution_at = ticket.due_resolution_at + paused_for
        ticket.sla_paused = False
        ticket.sla_paused_since = None
        db.session.commit()
        audit('ticket', ticket.id, 'sla_resume', user_id=current_user.id)
        flash('SLA retomado.', 'success')
    return redirect(url_for('tickets.detail', ticket_id=ticket.id))
