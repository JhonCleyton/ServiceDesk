# JC Service Desk

Service Desk web application built with Flask, providing ticket management, real‑time notifications, chat, password reset, LGPD policy management, and a modern UI.

# environment settings

- ADMIN_EMAIL=admin@local.com
- ADMIN_PASSWORD=admin123
- In the _init_.py file, line 201 contains the default company and admin user settings. You can edit them to create your local company, or edit them after you log in.

## Highlights

- Tickets with comments, attachments, status changes and e‑mail notifications
- Real‑time updates via Server‑Sent Events (SSE) with polling fallback
- Notification center with unread counter and mark‑as‑read (individual and bulk)
- Integrated chat (SSE) and waiting room mini‑games (Snake and Sudoku)
- Authentication with email confirmation and optional 2FA via OTP
- Forgot Password flow with secure time‑limited token
- Multi‑tenant companies with domain validation and branding colors
- LGPD center: public privacy page and admin revision/audit management
- Bootstrap 5 UI with icons, favicon and logo fallback


## Tech Stack

- Flask 3, Flask‑SQLAlchemy, Flask‑Migrate
- Flask‑Login, Flask‑WTF (CSRF), Flask‑Mail
- Itsdangerous (tokens), python‑dotenv
- Bootstrap 5 and Bootstrap Icons
- SQLite by default (via SQLAlchemy). Other DBs are possible by adjusting `DATABASE_URL` and driver packages.


## Project Structure (high‑level)

- `app/__init__.py` – app factory, extensions, blueprints, Jinja filters, basic schema ensures and seed
- `app/config.py` – environment‑driven configuration
- `app/models.py` – SQLAlchemy ORM models
- `app/*/routes.py` – blueprints: `auth`, `tickets`, `main`, `admin`, `kb`, `reports`, `notifications`, `chat`
- `app/templates/*` – Jinja templates (base, auth, tickets, main, admin, etc.)
- `app/static/main.js` – front‑end logic: SSE, notifications, chat, games, UI extras
- `run.py` – local entry point for development


## Setup

1. Requirements
   - Python 3.10+
   - Pip

2. Create and activate a virtual environment
   - Windows (PowerShell)
     - `python -m venv .venv`
     - `.venv\\Scripts\\Activate.ps1`

3. Install dependencies
   - `pip install -r requirements.txt`

4. Configure environment variables (create a `.env` file in project root)

```
# Core
FLASK_ENV=development
SECRET_KEY=change-this-in-production
DATABASE_URL=sqlite:///app.db
TIMEZONE=America/Sao_Paulo

# Mail (development defaults to a local dummy server)
MAIL_SERVER=localhost
MAIL_PORT=8025
MAIL_USE_TLS=0
MAIL_USE_SSL=0
MAIL_USERNAME=
MAIL_PASSWORD=
MAIL_DEFAULT_SENDER=no-reply@local
MAIL_SUPPRESS_SEND=1
NOTIFY_TICKETS_TO=your email to received notfications
# Admin seed (first run only)
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=change-me

# Optional
SESSION_LIFETIME_SECONDS=28800
BRAND_PRIMARY=#2563eb
BRAND_PRIMARY_DARK=#1d4ed8
BRAND_PRIMARY_LIGHT=#3b82f6
```

5. Run (development)
   - `python run.py`
   - The first run creates the database/tables and seeds a default admin user using `ADMIN_EMAIL`/`ADMIN_PASSWORD`.


## Running a dummy SMTP for local tests

- You can use Python’s built‑in smtpd (or a tool like MailHog) to capture emails.
- Example (Python 3.11+, separate terminal): `python -m aiosmtpd -n -l localhost:8025`
- Set `MAIL_SUPPRESS_SEND=0` to actually send to your SMTP.


## Key Features and Flows

- Authentication
  - Registration with company domain validation and optional LGPD consent
  - Email confirmation before first login
  - Optional 2FA (OTP via email)
  - Forgot password
    - `GET/POST /auth/forgot` – request reset link
    - `GET/POST /auth/reset/<token>` – set a new password (token expires in 2 hours)

- Tickets
  - Create, view details, assign, resolve and close with technician evaluation
  - Email notifications for creation, comments and status changes
  - Client rating flow with secure token link after closure

- Notifications (SSE)
  - Dropdown with unread count; mark single or all as read
  - Auto‑update via SSE with polling fallback when necessary

- Chat (SSE)
  - Real‑time message stream with role checks and fallback

- Waiting Room Games
  - Snake UX improvements (focus handling, speed display, overlay messages)
  - Sudoku with generator/solver, difficulty and conflict validation

- LGPD
  - Admin UI to create/publish revisions with audit
  - Public route shows the latest published policy


## Production notes

- Set `FLASK_ENV=production` and switch to `ProductionConfig` if you maintain multiple wsgi entrypoints.
- Ensure `SECRET_KEY` is strong and unique.
- Configure a production SMTP and set `MAIL_SUPPRESS_SEND=0`.
- Put the app behind a reverse proxy (Nginx/Apache). For SSE, disable proxy buffering for the SSE endpoints to keep streams alive (e.g., `proxy_buffering off;`).
- Use a production WSGI server (e.g., gunicorn or waitress). Example (Linux): `gunicorn -w 4 -b 0.0.0.0:8000 'run:app'`.
- For non‑SQLite databases, set `DATABASE_URL` accordingly and install the driver (e.g., psycopg for Postgres or pymysql for MySQL).


## Troubleshooting

- Emails not sending
  - Check SMTP host/port and `MAIL_SUPPRESS_SEND` flag
  - Review logs for exceptions
- SSE not updating
  - Verify reverse proxy buffering is disabled and connections aren’t being closed prematurely
- Login blocked
  - User lockout after repeated failures is temporary; wait or reset password
- Templates/branding
  - Update company branding in Admin or override defaults via `.env`


## License

Proprietary — internal use unless otherwise agreed.

---

# Extended Documentation

## Overview for Requesters (Usu�rios que abrem chamados)

- Abra e acompanhe chamados em uma interface simples.
- Receba notifica��es em tempo real das atualiza��es do seu chamado.
- Envie coment�rios e anexos a qualquer momento.
- Avalie o atendimento quando o chamado for encerrado.
- Consulte a Base de Conhecimento (quando habilitada para sua empresa).

## Architecture and Modules

- App Factory: `app/__init__.py` com extens�es (SQLAlchemy, Migrate, Login, Mail, CSRF), filtros Jinja e seed de desenvolvimento.
- Blueprints:
  - `main` (`/`): landing, dashboard, perfil, LGPD p�blica/privada, sala de espera e APIs auxiliares.
  - `auth` (`/auth`): login, registro com confirma��o por e-mail, OTP (2FA opcional), esqueci/redefini��o de senha.
  - `tickets` (`/tickets`): lista/cria��o/detalhe, coment�rios, anexos, atribui��o, resolver/fechar/reabrir, avalia��o de atendimento, SLA.
  - `notify` (`/notify*`): notifica��es em tempo real via SSE com fallback de polling.
  - `chat` (`/chat`): chat em tempo real por ticket + webhook WhatsApp (stub para exemplo).
  - `kb` (`/kb`): Base de Conhecimento (CRUD, p�blico/privado, busca e sugest�es no formul�rio de ticket).
  - `reports` (`/reports`): vis�o agregada e exporta��o CSV.
  - `admin` (`/admin`): empresas, usu�rios, categorias, contratos, planos de SLA, filas/equipes, ativos, problemas, mudan�as, LGPD, modelos de e-mail e ferramentas.

## Data Model (high-level)

- N�cleo: Company, User (roles: client, tech, supervisor, admin), Ticket, TicketComment, Attachment.
- SLA e Cat�logo: SLAPlan, Contract, Category, Queue, Asset.
- ITSM extra: Problem, ChangeRequest.
- Sistema: Notification (seen/read), EmailTemplate, LGPDRevision, AuditLog, GameScore, KnowledgeBaseArticle.

## Directory Structure (high-level)

```
app/
  __init__.py        # app factory, blueprints, filtros e seed
  config.py          # configs por ambiente (env-driven)
  models.py          # ORM models
  email.py           # envio de e-mails e modelos
  utils.py           # utilit�rios (SLA, IMAP, reten��o, auditoria)
  static/main.js     # SSE, notifica��es, UI, jogos, melhorias UX
  templates/         # base, auth, tickets, admin, kb, reports, main
  */routes.py        # rotas por m�dulo
run.py               # entrypoint dev (0.0.0.0:4480)
requirements.txt     # depend�ncias
.env                 # vari�veis de ambiente (n�o versionar chaves sens�veis)
```

## Environment Variables (.env)

```
# Core
FLASK_ENV=development
SECRET_KEY=change-this-in-production
DATABASE_URL=sqlite:///app.db
TIMEZONE=America/Sao_Paulo

# Mail
MAIL_SERVER=localhost
MAIL_PORT=8025
MAIL_USE_TLS=0
MAIL_USE_SSL=0
MAIL_USERNAME=
MAIL_PASSWORD=
MAIL_DEFAULT_SENDER=no-reply@local
MAIL_SUPPRESS_SEND=1
NOTIFY_TICKETS_TO=admin1@example.com, admin2@example.com

# Admin seed (first run)
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=change-me

# Optional branding
BRAND_PRIMARY=#2563eb
BRAND_PRIMARY_DARK=#1d4ed8
BRAND_PRIMARY_LIGHT=#3b82f6

# Sessions
SESSION_LIFETIME_SECONDS=28800

# IMAP inbound (opcional)
IMAP_HOST=
IMAP_PORT=993
IMAP_SSL=1
IMAP_USERNAME=
IMAP_PASSWORD=
```

## Setup (Windows PowerShell)

1. Instale Python 3.10+ e `pip`.
2. Ambiente virtual e depend�ncias:
   - `python -m venv .venv`
   - `.venv\Scripts\Activate.ps1`
   - `pip install -r requirements.txt`
3. Crie `.env` conforme exemplo acima.
4. Desenvolvimento: `python run.py` (inicia em `http://localhost:4480`).

Primeira execu��o cria tabelas e semeia usu�rio admin com `ADMIN_EMAIL`/`ADMIN_PASSWORD`.

## Database Migrations (Flask-Migrate)

Al�m dos ensures do app factory, use migra��es quando necess�rio:

```
$env:FLASK_APP = "run:app"
flask db init
flask db migrate -m "initial"
flask db upgrade
```

## Local Email Testing

- Capturar e-mails localmente: `python -m aiosmtpd -n -l localhost:8025`
- Para enviar ao SMTP local, defina `MAIL_SUPPRESS_SEND=0`.

## Reverse Proxy and SSE

- Coloque o app atr�s de Nginx/Apache e desative buffering nas rotas SSE:
  - Nginx: `proxy_buffering off;`
- Ajuste timeouts para conex�es longas.

## Security Notes

- Confirma��o de e-mail e OTP (2FA opcional) no login.
- Lockout ap�s 5 falhas por ~15 min.
- Allowlist de IP por empresa (`Company.allowed_ips`).
- CSRF em formul�rios; tokens via itsdangerous.
- RBAC simples por fun��o (`role_required`).
- Reten��o/anonimiza��o (LGPD) e avalia��o t�cnica no fechamento.
- Uploads de anexos por ticket com `secure_filename` e diret�rios isolados.

## Key Routes Summary

- main: `/` (landing), `/dashboard`, `/meu-perfil`, `/lgpd`, `/lgpd/public/<company_id>`
- auth: `/auth/login`, `/auth/register`, `/auth/forgot`, `/auth/reset/<token>`, `/auth/otp`, `/auth/logout`
- tickets: `/tickets/` (lista), `/tickets/create`, `/<id>` (detalhe), comments (poll/stream), anexos (download/view), atribuir/resolver/fechar/reabrir, avaliar
- notify: `/notify/poll`, `/notify/stream`, `/notify/read`, `/notify/read_all`
- chat: `/chat/`, `/chat/poll`, `/chat/stream`, `/chat/send`, `/chat/webhook/whatsapp`
- kb: `/kb/`, `/kb/create`, `/kb/<id>/edit`, `/kb/<id>`, `/kb/search`
- reports: `/reports/`, `/reports/export.csv`
- admin: empresas, usu�rios, categorias, contratos, SLA, filas, ativos, problemas, mudan�as, LGPD, modelos, ferramentas

## Troubleshooting

- E-mails n�o enviam: verifique SMTP e `MAIL_SUPPRESS_SEND`.
- SSE sem atualizar: desative buffering no proxy e valide timeouts.
- Login bloqueado: aguarde expirar o lockout ou redefina a senha.
- Anexos: revisar permiss�es do diret�rio `app/uploads/`.
- Branding: ajuste via Admin ou vari�veis `.env`.

## FAQ

- Restringir acesso por IP?
  - Configure `allowed_ips` na empresa (IPs e CIDRs por linha).
- Aceitar e-mail fora do dom�nio da empresa?
  - Marque `accept_any_domain` na empresa.
- Usar Postgres/MySQL?
  - Sim. Ajuste `DATABASE_URL` e instale o driver (psycopg/pymysql).

## Roadmap Sugerido

- Testes automatizados (PyTest) e CI.
- Pagina��o e cache nas listas maiores.
- WebSocket opcional al�m de SSE.
- Integra��o real de WhatsApp/Telegram via provedores.
- Templates de e-mail HTML (Jinja) e branding avan�ado.

# Novidades Principais
- Tickets: categoria e subcategoria salvas no momento da criação.
- Listagem profissional para técnicos:
  - “Sem atendimento” (não atribuídos) e “Em atendimento” (com responsável).
  - Agrupado por empresa e mostrando o responsável.
- Restrições de interação:
  - Apenas técnico responsável e perfis autorizados (admin/supervisor) podem assumir, resolver e encerrar.
  - Participantes colaboram via comentários internos; clientes não veem mensagens internas.
- Participantes e transferência:
  - Convidar/remover técnicos participantes no ticket.
  - Transferência rápida de responsável no detalhe do ticket.
- Chat interno:
  - Checkbox “Interno” para mensagens visíveis apenas para equipe.
- Relatórios:
  - Filtro por período (hoje/semana/mês/todos), KPIs e gráficos de satisfação.
- E-mails:
  - Templates HTML com branding e fallback de logo.
- Sala de espera – Sudoku:
  - Cronômetro e sistema de vidas (fácil=5, médio=3, difícil=1).
  - Erros não bloqueiam o jogo; célula marcada e decremento de vida; fim ao zerar vidas.
 
Desenvolvedor
Desenvolvido por Jhon Cleyton – JC Byte - Solução em Tecnologia.

GitHub: https://github.com/JhonCleyton
LinkedIn: https://www.linkedin.com/in/jhon-freire
Instagram: https://www.instagram.com/jhoncleyton.dev
WhatsApp: https://wa.me/557399854785
Portfólio: https://jhoncleyton.dev"# ServiceDesk"  
