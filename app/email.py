from flask_mail import Message
from flask import url_for, current_app
from . import mail
from .models import EmailTemplate, Company


def _send(subject, recipients, body, html=None):
    msg = Message(subject=subject, recipients=recipients, body=body)
    if html:
        msg.html = html
    if current_app.config.get('MAIL_SUPPRESS_SEND', True):
        print(f"[MAIL SUPPRESSED] To: {', '.join(recipients)}\nSubject: {subject}\n\n{body}")
        return
    try:
        mail.send(msg)
    except Exception as e:
        current_app.logger.exception('Erro ao enviar e-mail')
        raise e


def _render_template(name, company_id, default_subject, default_body, context: dict):
    tpl = None
    if company_id:
        tpl = EmailTemplate.query.filter_by(company_id=company_id, name=name, active=True).first()
    if not tpl:
        tpl = EmailTemplate.query.filter_by(company_id=None, name=name, active=True).first()
    subject = default_subject
    body = default_body
    if tpl:
        try:
            subject = (tpl.subject or default_subject).format_map(context)
            body = (tpl.body or default_body).format_map(context)
        except Exception:
            pass
    else:
        try:
            subject = default_subject.format_map(context)
            body = default_body.format_map(context)
        except Exception:
            pass
    return subject, body


def _brand_for_company(company_id):
    company = Company.query.get(company_id) if company_id else None
    primary = (company.brand_primary if company and company.brand_primary else current_app.config.get('BRAND_PRIMARY', '#2563eb'))
    logo_url = company.logo_url if company and company.logo_url else url_for('static', filename='img/logo.png')
    brand_name = company.name if company else 'JC Byte'
    return {
        'primary': primary,
        'logo_url': logo_url,
        'brand_name': brand_name,
    }


def _text_to_html(body: str) -> str:
    parts = [p.strip() for p in (body or '').split('\n\n')]
    html_parts = []
    for p in parts:
        if not p:
            continue
        replaced = p.replace('\n','<br>')
        html_parts.append(f"<p style=\"margin:0 0 12px; line-height:1.5;\">{replaced}</p>")
    return "\n".join(html_parts) or "<p></p>"


def _wrap_html(subject: str, company_id, body: str) -> str:
    brand = _brand_for_company(company_id)
    body_html = _text_to_html(body)
    primary = brand['primary']
    logo_html = (
        f"<img src=\"{brand['logo_url']}\" alt=\"{brand['brand_name']}\" style=\"max-height:40px; display:block;\">"
        if brand['logo_url'] else
        f"<div style=\"font-weight:700; font-size:20px; color:#fff;\">{brand['brand_name']}</div>"
    )
    return f"""
<!doctype html>
<html lang=\"pt-BR\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
  <title>{subject}</title>
  <style>
    @media (prefers-color-scheme: dark) {{ body {{ background:#111 !important; }} }}
  </style>
  </head>
<body style=\"margin:0; padding:24px; background:#f5f7fb; font-family: -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif; color:#111;\">
  <div style=\"max-width:640px; margin:0 auto;\">
    <div style=\"background:{primary}; padding:16px 20px; border-radius:12px 12px 0 0;\">{logo_html}</div>
    <div style=\"background:#fff; border:1px solid #e5e7eb; border-top:0; border-radius:0 0 12px 12px; padding:20px;\">
      {body_html}
    </div>
    <div style=\"text-align:center; color:#6b7280; font-size:12px; margin-top:12px;\">© {brand['brand_name']}</div>
  </div>
</body>
</html>
"""


def send_confirmation_email(user, token):
    confirm_url = url_for('auth.confirm_email', token=token, _external=True)
    subject = 'Confirme seu cadastro'
    body = (
        f'Olá {user.name},\n\n'
        f'Confirme seu cadastro clicando no link:\n{confirm_url}\n\n'
        'Se você não solicitou este cadastro, ignore esta mensagem.'
    )
    html = _wrap_html(subject, user.company_id, body)
    _send(subject=subject, recipients=[user.email], body=body, html=html)


def send_password_reset_email(user, token):
    reset_url = url_for('auth.reset_password', token=token, _external=True)
    subject = 'Redefinição de senha'
    body = (
        f'Olá {user.name},\n\n'
        f'Recebemos uma solicitação para redefinir sua senha. Para continuar, acesse:\n{reset_url}\n\n'
        'Se você não solicitou esta alteração, ignore este e-mail. O link expira em 2 horas.'
    )
    html = _wrap_html(subject, user.company_id, body)
    _send(subject, [user.email], body, html)


def send_ticket_created(ticket, creator, watchers=None):
    link = url_for('tickets.detail', ticket_id=ticket.id, _external=True)
    default_subject = "[Ticket {number}] Criado: {title}"
    default_body = (
        "Ticket criado por {creator_name} ({creator_email}).\n"
        "Número: {number}\nTítulo: {title}\nPrioridade: {priority}\nStatus: {status}\n\n"
        "Acessar: {link}"
    )
    context = {
        'number': ticket.number,
        'title': ticket.title,
        'priority': ticket.priority,
        'status': ticket.status,
        'link': link,
        'creator_name': creator.name,
        'creator_email': creator.email,
    }
    subject, body = _render_template('ticket_created', ticket.company_id, default_subject, default_body, context)
    recipients = [creator.email]
    if watchers:
        recipients += watchers
    html = _wrap_html(subject, ticket.company_id, body)
    _send(subject, recipients, body, html)


def send_ticket_comment(ticket, author, public=True):
    link = url_for('tickets.detail', ticket_id=ticket.id, _external=True)
    visibility = 'público' if public else 'interno'
    default_subject = "[Ticket {number}] Novo comentário"
    default_body = (
        "Novo comentário {visibility} por {author_name}.\n"
        "Ticket: {number} - {title}\n\n"
        "Acessar: {link}"
    )
    context = {
        'number': ticket.number,
        'title': ticket.title,
        'visibility': visibility,
        'author_name': author.name,
        'link': link,
    }
    subject, body = _render_template('ticket_comment', ticket.company_id, default_subject, default_body, context)
    recipients = []
    if public:
        recipients.append(ticket.creator.email)
    if ticket.assignee:
        recipients.append(ticket.assignee.email)
    if recipients:
        html = _wrap_html(subject, ticket.company_id, body)
        _send(subject, recipients, body, html)


def send_ticket_status(ticket, actor, old_status, new_status):
    link = url_for('tickets.detail', ticket_id=ticket.id, _external=True)
    default_subject = "[Ticket {number}] Status: {old_status} → {new_status}"
    default_body = (
        "{actor_name} alterou o status do ticket.\n"
        "Ticket: {number} - {title}\nStatus: {old_status} → {new_status}\n\n"
        "Acessar: {link}"
    )
    context = {
        'number': ticket.number,
        'title': ticket.title,
        'old_status': old_status,
        'new_status': new_status,
        'actor_name': actor.name,
        'link': link,
    }
    subject, body = _render_template('ticket_status', ticket.company_id, default_subject, default_body, context)
    recipients = [ticket.creator.email]
    if ticket.assignee:
        recipients.append(ticket.assignee.email)
    html = _wrap_html(subject, ticket.company_id, body)
    _send(subject, recipients, body, html)


def send_otp_email(user, code):
    default_subject = "Seu código de verificação"
    default_body = (
        "Olá {name},\n\n"
        "Seu código de verificação é: {code}. Ele expira em {minutes} minutos.\n\n"
        "Se você não solicitou, ignore este e-mail."
    )
    subject, body = _render_template('otp_code', user.company_id, default_subject, default_body, {'name': user.name, 'code': code, 'minutes': 10})
    html = _wrap_html(subject, user.company_id, body)
    _send(subject, [user.email], body, html)


def send_ticket_closed(ticket, actor, transcript_lines, rating_link: str):
    link = url_for('tickets.detail', ticket_id=ticket.id, _external=True)
    default_subject = "[Ticket {number}] Encerrado: {title}"
    transcript = "\n\n".join(transcript_lines) if transcript_lines else "(Sem mensagens públicas)"
    default_body = (
        "{actor_name} encerrou o ticket.\n"
        "Ticket: {number} - {title}\n"
        "Motivo: {closed_reason}\n"
        "Solução: {solution}\n"
        "Avaliação técnica: {tech_eval_category} - {tech_evaluation}\n\n"
        "Histórico:\n{transcript}\n\n"
        "Avalie o atendimento: {rating_link}\n"
        "Acessar ticket: {link}"
    )
    context = {
        'number': ticket.number,
        'title': ticket.title,
        'closed_reason': ticket.closed_reason or '-',
        'solution': ticket.solution or '-',
        'tech_evaluation': ticket.tech_evaluation or '-',
        'tech_eval_category': ticket.tech_eval_category or '-',
        'transcript': transcript,
        'actor_name': actor.name,
        'link': link,
        'rating_link': rating_link,
    }
    subject, body = _render_template('ticket_closed', ticket.company_id, default_subject, default_body, context)
    recipients = [ticket.creator.email]
    if ticket.assignee:
        recipients.append(ticket.assignee.email)
    html = _wrap_html(subject, ticket.company_id, body)
    _send(subject, recipients, body, html)

