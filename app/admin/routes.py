from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, current_app, jsonify
from flask_login import current_user
from ..utils import role_required
from .. import db
from ..models import Company, Category, Contract, SLAPlan, User, Queue, Asset, EmailTemplate, Problem, ChangeRequest, LGPDRevision
from .forms import CompanyForm, CategoryForm, ContractForm, SLAPlanForm, UserRoleForm, QueueForm, AssetForm, EmailTemplateForm, ProblemForm, ChangeRequestForm, UserCreateForm, UserEditForm, LGPDRevisionForm
from ..utils import poll_imap_and_process, run_automations, run_retention, audit
from ..email import _send
from werkzeug.utils import secure_filename
import os
import uuid
try:
    from PIL import Image  # type: ignore
except Exception:
    Image = None


admin_bp = Blueprint('admin', __name__, template_folder='../templates')


@admin_bp.before_request
def require_admin_or_supervisor():
    if not current_user.is_authenticated:
        return redirect(url_for('auth.login'))
    if current_user.role not in ('admin','supervisor'):
        abort(403)


@admin_bp.route('/')
def index():
    stats = {
        'companies': Company.query.count(),
        'users': User.query.count(),
        'contracts': Contract.query.count(),
        'slaplans': SLAPlan.query.count(),
        'categories': Category.query.count(),
    }
    return render_template('admin/index.html', stats=stats)


@admin_bp.route('/companies', methods=['GET', 'POST'])
def companies():
    form = CompanyForm()
    if form.validate_on_submit():
        c = Company(
            name=form.name.data,
            domain=form.domain.data.lower(),
            terms_url=form.terms_url.data or None,
            consent_required=form.consent_required.data or False,
            retention_days=form.retention_days.data or 365,
            allowed_ips=(form.allowed_ips.data or '').strip() or None,
            accept_any_domain=form.accept_any_domain.data or False,
            brand_primary=(form.brand_primary.data or None),
            brand_primary_dark=(form.brand_primary_dark.data or None),
            brand_primary_light=(form.brand_primary_light.data or None),
            logo_url=(form.logo_url.data or None),
        )
        # Handle logo file upload
        f = request.files.get('logo_file')
        if f and getattr(f, 'filename', ''):
            original = secure_filename(f.filename)
            ext = os.path.splitext(original)[1].lower()
            if ext in ('.png', '.jpg', '.jpeg', '.webp', '.gif'):
                filename = f"{uuid.uuid4().hex}{ext}"
                target = os.path.join(current_app.root_path, 'static', 'uploads', 'logos', filename)
                if Image is not None:
                    try:
                        img = Image.open(f.stream)
                        # resize to height 64, keep aspect
                        ratio = 64.0 / float(img.height)
                        new_w = int(img.width * ratio)
                        img = img.resize((new_w, 64), Image.LANCZOS)
                        img.save(target)
                    except Exception:
                        f.seek(0)
                        f.save(target)
                else:
                    f.save(target)
                c.logo_url = url_for('static', filename=f'uploads/logos/{filename}') + f"?v={uuid.uuid4().hex[:6]}"
        db.session.add(c)
        db.session.commit()
        flash('Empresa criada.', 'success')
        return redirect(url_for('admin.companies'))
    items = Company.query.order_by(Company.name).all()
    return render_template('admin/companies.html', form=form, items=items)


@admin_bp.route('/categories', methods=['GET', 'POST'])
def categories():
    form = CategoryForm()
    form.company_id.choices = [(0, '— Global —')] + [(c.id, f"{c.name} ({c.domain})") for c in Company.query.order_by(Company.name).all()]
    # parent choices depend on company selection; for simplicity show all
    form.parent_id.choices = [(0, '— Sem pai —')] + [(cat.id, cat.name) for cat in Category.query.order_by(Category.name).all()]
    if form.validate_on_submit():
        parent_id = form.parent_id.data if form.parent_id.data != 0 else None
        company_id = form.company_id.data if form.company_id.data != 0 else None
        cat = Category(company_id=company_id, name=form.name.data, parent_id=parent_id)
        db.session.add(cat)
        db.session.commit()
        flash('Categoria criada.', 'success')
        return redirect(url_for('admin.categories'))
    items = Category.query.order_by(Category.company_id, Category.name).all()
    return render_template('admin/categories.html', form=form, items=items)


@admin_bp.route('/categories/<int:category_id>/edit', methods=['GET','POST'])
def category_edit(category_id):
    cat = Category.query.get_or_404(category_id)
    form = CategoryForm(obj=cat)
    form.company_id.choices = [(0, '— Global —')] + [(c.id, f"{c.name} ({c.domain})") for c in Company.query.order_by(Company.name).all()]
    form.parent_id.choices = [(0, '— Sem pai —')] + [(c.id, c.name) for c in Category.query.order_by(Category.name).all()]
    if form.validate_on_submit():
        if form.parent_id.data == cat.id:
            flash('Uma categoria não pode ser pai de si mesma.', 'danger')
            return render_template('admin/category_edit.html', form=form, category=cat)
        cat.company_id = form.company_id.data if form.company_id.data != 0 else None
        cat.name = form.name.data
        cat.parent_id = form.parent_id.data if form.parent_id.data != 0 else None
        db.session.commit()
        flash('Categoria atualizada.', 'success')
        return redirect(url_for('admin.categories'))
    return render_template('admin/category_edit.html', form=form, category=cat)


@admin_bp.route('/categories/<int:category_id>/delete', methods=['POST'])
def category_delete(category_id):
    cat = Category.query.get_or_404(category_id)
    # Bloqueia exclusão se houver filhos ou planos de SLA referenciando
    if getattr(cat, 'children', []):
        flash('Não é possível excluir: existem subcategorias.', 'danger')
        return redirect(url_for('admin.categories'))
    if SLAPlan.query.filter_by(category_id=cat.id).first():
        flash('Não é possível excluir: existe plano de SLA usando esta categoria.', 'danger')
        return redirect(url_for('admin.categories'))
    db.session.delete(cat)
    db.session.commit()
    flash('Categoria excluída.', 'success')
    return redirect(url_for('admin.categories'))


@admin_bp.route('/contracts', methods=['GET', 'POST'])
def contracts():
    form = ContractForm()
    form.company_id.choices = [(c.id, f"{c.name} ({c.domain})") for c in Company.query.order_by(Company.name).all()]
    if form.validate_on_submit():
        ct = Contract(company_id=form.company_id.data, name=form.name.data, active=form.active.data)
        db.session.add(ct)
        db.session.commit()
        flash('Contrato criado.', 'success')
        return redirect(url_for('admin.contracts'))
    items = Contract.query.order_by(Contract.company_id, Contract.name).all()
    return render_template('admin/contracts.html', form=form, items=items)


@admin_bp.route('/slaplans', methods=['GET', 'POST'])
def slaplans():
    form = SLAPlanForm()
    form.company_id.choices = [(c.id, f"{c.name} ({c.domain})") for c in Company.query.order_by(Company.name).all()]
    form.contract_id.choices = [(0, '—')] + [(ct.id, ct.name) for ct in Contract.query.order_by(Contract.name).all()]
    form.category_id.choices = [(0, '—')] + [(cat.id, cat.name) for cat in Category.query.order_by(Category.name).all()]
    if form.validate_on_submit():
        plan = SLAPlan(
            company_id=form.company_id.data,
            name=form.name.data,
            first_response_minutes=form.first_response_minutes.data,
            resolution_minutes=form.resolution_minutes.data,
            contract_id=(form.contract_id.data if form.contract_id.data != 0 else None),
            category_id=(form.category_id.data if form.category_id.data != 0 else None),
            priority=form.priority.data or None,
            active=form.active.data,
        )
        db.session.add(plan)
        db.session.commit()
        flash('SLA criado.', 'success')
        return redirect(url_for('admin.slaplans'))
    items = SLAPlan.query.order_by(SLAPlan.company_id, SLAPlan.name).all()
    return render_template('admin/slaplans.html', form=form, items=items)


@admin_bp.route('/users', methods=['GET', 'POST'])
@role_required('admin')
def users():
    form = UserRoleForm()
    if request.method == 'POST':
        uid = int(request.form.get('user_id'))
        user = User.query.get_or_404(uid)
        old = user.role
        user.role = form.role.data
        user.force_2fa = True if request.form.get('force_2fa') else False
        db.session.commit()
        flash(f'Perfil de {user.email} atualizado: {old} → {user.role} | 2FA: {"on" if user.force_2fa else "off"}', 'success')
        return redirect(url_for('admin.users'))
    items = User.query.order_by(User.company_id, User.name).all()
    return render_template('admin/users.html', form=form, items=items)


@admin_bp.route('/users/create', methods=['GET','POST'])
@role_required('admin')
def user_create():
    form = UserCreateForm()
    form.company_id.choices = [(c.id, f"{c.name} ({c.domain})") for c in Company.query.order_by(Company.name).all()]
    if form.validate_on_submit():
        company = Company.query.get(form.company_id.data)
        email = form.email.data.strip().lower()
        if company and company.domain and not email.endswith('@' + company.domain.lower()):
            flash('O e-mail deve possuir o domínio da empresa selecionada.', 'danger')
            return render_template('admin/user_create.html', form=form)
        if User.query.filter_by(email=email).first():
            flash('E-mail já cadastrado.', 'danger')
            return render_template('admin/user_create.html', form=form)
        user = User(email=email, name=form.name.data.strip(), role=form.role.data, company_id=company.id,
                    confirmed=form.confirmed.data, force_2fa=form.force_2fa.data)
        tmp_password = form.password.data.strip() if form.password.data else None
        if not tmp_password:
            import secrets
            tmp_password = secrets.token_urlsafe(8)
            print(f"[ADMIN] Senha temporária para {email}: {tmp_password}")
        user.set_password(tmp_password)
        db.session.add(user)
        db.session.commit()
        flash('Usuário criado com sucesso.', 'success')
        return redirect(url_for('admin.users'))
    return render_template('admin/user_create.html', form=form)


@admin_bp.route('/users/<int:user_id>/edit', methods=['GET','POST'])
@role_required('admin')
def user_edit(user_id):
    user = User.query.get_or_404(user_id)
    form = UserEditForm(obj=user)
    form.company_id.choices = [(c.id, f"{c.name} ({c.domain})") for c in Company.query.order_by(Company.name).all()]
    if form.validate_on_submit():
        company = Company.query.get(form.company_id.data)
        email = form.email.data.strip().lower()
        if company and company.domain and not email.endswith('@' + company.domain.lower()):
            flash('O e-mail deve possuir o domínio da empresa selecionada.', 'danger')
            return render_template('admin/user_edit.html', form=form, user=user)
        exists = User.query.filter(User.email == email, User.id != user.id).first()
        if exists:
            flash('E-mail já cadastrado em outro usuário.', 'danger')
            return render_template('admin/user_edit.html', form=form, user=user)
        user.company_id = company.id
        user.name = form.name.data.strip()
        user.email = email
        user.role = form.role.data
        user.confirmed = form.confirmed.data
        user.force_2fa = form.force_2fa.data
        if form.password.data:
            user.set_password(form.password.data)
        # Avatar upload
        f = request.files.get('avatar_file')
        if f and getattr(f, 'filename', ''):
            original = secure_filename(f.filename)
            ext = os.path.splitext(original)[1].lower()
            if ext in ('.png', '.jpg', '.jpeg', '.webp', '.gif'):
                filename = f"{uuid.uuid4().hex}{ext}"
                target = os.path.join(current_app.root_path, 'static', 'uploads', 'avatars', filename)
                if Image is not None:
                    try:
                        img = Image.open(f.stream).convert('RGB')
                        # square crop center
                        w, h = img.size
                        m = min(w, h)
                        left = (w - m) // 2
                        top = (h - m) // 2
                        img = img.crop((left, top, left + m, top + m))
                        img = img.resize((128, 128), Image.LANCZOS)
                        img.save(target, quality=92)
                    except Exception:
                        f.seek(0)
                        f.save(target)
                else:
                    f.save(target)
                user.avatar_filename = filename
        db.session.commit()
        flash('Usuário atualizado.', 'success')
        return redirect(url_for('admin.users'))
    return render_template('admin/user_edit.html', form=form, user=user)


@admin_bp.route('/companies/<int:company_id>/edit', methods=['GET','POST'])
def company_edit(company_id):
    c = Company.query.get_or_404(company_id)
    form = CompanyForm(obj=c)
    if form.validate_on_submit():
        c.name = form.name.data
        c.domain = form.domain.data.lower()
        c.terms_url = form.terms_url.data or None
        c.consent_required = form.consent_required.data or False
        c.retention_days = form.retention_days.data or 365
        c.allowed_ips = (form.allowed_ips.data or '').strip() or None
        c.accept_any_domain = form.accept_any_domain.data or False
        c.brand_primary = form.brand_primary.data or None
        c.brand_primary_dark = form.brand_primary_dark.data or None
        c.brand_primary_light = form.brand_primary_light.data or None
        # Prefer new logo_file if provided; else keep logo_url or allow override via url
        f = request.files.get('logo_file')
        if f and getattr(f, 'filename', ''):
            original = secure_filename(f.filename)
            ext = os.path.splitext(original)[1].lower()
            if ext in ('.png', '.jpg', '.jpeg', '.webp', '.gif'):
                filename = f"{uuid.uuid4().hex}{ext}"
                target = os.path.join(current_app.root_path, 'static', 'uploads', 'logos', filename)
                f.save(target)
                c.logo_url = url_for('static', filename=f'uploads/logos/{filename}') + f"?v={uuid.uuid4().hex[:6]}"
        elif form.logo_url.data:
            c.logo_url = form.logo_url.data
        db.session.commit()
        flash('Empresa atualizada.', 'success')
        return redirect(url_for('admin.companies'))
    return render_template('admin/company_edit.html', form=form, company=c)


@admin_bp.route('/companies/<int:company_id>/toggle-active', methods=['POST'])
def company_toggle_active(company_id):
    c = Company.query.get_or_404(company_id)
    c.active = not bool(c.active)
    db.session.commit()
    flash('Empresa ativada.' if c.active else 'Empresa inativada.', 'success')
    return redirect(request.referrer or url_for('admin.companies'))


@admin_bp.route('/queues', methods=['GET','POST'])
def queues():
    form = QueueForm()
    form.company_id.choices = [(c.id, f"{c.name} ({c.domain})") for c in Company.query.order_by(Company.name).all()]
    if form.validate_on_submit():
        q = Queue(company_id=form.company_id.data, name=form.name.data, active=form.active.data)
        db.session.add(q)
        db.session.commit()
        flash('Fila criada.', 'success')
        return redirect(url_for('admin.queues'))
    items = Queue.query.order_by(Queue.company_id, Queue.name).all()
    return render_template('admin/queues.html', form=form, items=items)


@admin_bp.route('/assets', methods=['GET','POST'])
def assets():
    form = AssetForm()
    form.company_id.choices = [(c.id, f"{c.name} ({c.domain})") for c in Company.query.order_by(Company.name).all()]
    if form.validate_on_submit():
        a = Asset(company_id=form.company_id.data, name=form.name.data, serial=form.serial.data or None, type=form.type.data or None, active=form.active.data)
        db.session.add(a)
        db.session.commit()
        flash('Ativo criado.', 'success')
        return redirect(url_for('admin.assets'))
    items = Asset.query.order_by(Asset.company_id, Asset.name).all()
    return render_template('admin/assets.html', form=form, items=items)


@admin_bp.route('/email-templates', methods=['GET','POST'])
def email_templates():
    form = EmailTemplateForm()
    form.company_id.choices = [(0, '— Global —')] + [(c.id, f"{c.name} ({c.domain})") for c in Company.query.order_by(Company.name).all()]
    if form.validate_on_submit():
        tpl = EmailTemplate(
            company_id=form.company_id.data if form.company_id.data != 0 else None,
            name=form.name.data,
            subject=form.subject.data,
            body=form.body.data,
            active=form.active.data,
        )
        db.session.add(tpl)
        db.session.commit()
        flash('Modelo de e-mail salvo.', 'success')
        return redirect(url_for('admin.email_templates'))
    items = EmailTemplate.query.order_by(EmailTemplate.company_id, EmailTemplate.name).all()
    return render_template('admin/email_templates.html', form=form, items=items)


@admin_bp.route('/problems', methods=['GET','POST'])
def problems():
    form = ProblemForm()
    form.company_id.choices = [(c.id, f"{c.name} ({c.domain})") for c in Company.query.order_by(Company.name).all()]
    if form.validate_on_submit():
        p = Problem(company_id=form.company_id.data, title=form.title.data, description=form.description.data or None, status=form.status.data)
        db.session.add(p)
        db.session.commit()
        flash('Problema criado.', 'success')
        return redirect(url_for('admin.problems'))
    items = Problem.query.order_by(Problem.company_id, Problem.created_at.desc()).all()
    return render_template('admin/problems.html', form=form, items=items)


@admin_bp.route('/changes', methods=['GET','POST'])
def changes():
    form = ChangeRequestForm()
    form.company_id.choices = [(c.id, f"{c.name} ({c.domain})") for c in Company.query.order_by(Company.name).all()]
    if form.validate_on_submit():
        ch = ChangeRequest(company_id=form.company_id.data, title=form.title.data, description=form.description.data or None, status=form.status.data, approval=form.approval.data)
        db.session.add(ch)
        db.session.commit()
        flash('Requisição de mudança criada.', 'success')
        return redirect(url_for('admin.changes'))
    items = ChangeRequest.query.order_by(ChangeRequest.company_id, ChangeRequest.created_at.desc()).all()
    return render_template('admin/changes.html', form=form, items=items)


@admin_bp.route('/tools')
def tools():
    return render_template('admin/tools.html')


@admin_bp.route('/tools/poll-imap', methods=['POST'])
def tools_poll_imap():
    n = poll_imap_and_process()
    flash(f'IMAP processado, {n} mensagem(ns) tratada(s).', 'success')
    return redirect(url_for('admin.tools'))


@admin_bp.route('/tools/run-automations', methods=['POST'])
def tools_run_automations():
    run_automations()
    flash('Automações executadas.', 'success')
    return redirect(url_for('admin.tools'))


@admin_bp.route('/tools/run-retention', methods=['POST'])
def tools_run_retention():
    run_retention()
    flash('Rotina de retenção executada.', 'success')
    return redirect(url_for('admin.tools'))


@admin_bp.route('/tools/send-test-email', methods=['POST'])
def tools_send_test_email():
    to = (request.form.get('to') or '').strip()
    subject = (request.form.get('subject') or 'Teste de e-mail')
    if not to:
        flash('Informe o destinatário.', 'danger')
        return redirect(url_for('admin.tools'))
    body = 'Este é um envio de teste do Service Desk.'
    try:
        _send(subject, [to], body)
        flash(f'E-mail de teste enviado para {to}.', 'success')
    except Exception as e:
        flash(f'Falha ao enviar e-mail de teste: {e}', 'danger')
    return redirect(url_for('admin.tools'))


@admin_bp.route('/lgpd', methods=['GET','POST'])
def lgpd_center():
    form = LGPDRevisionForm()
    companies = Company.query.order_by(Company.name).all()
    form.company_id.choices = [(c.id, f"{c.name} ({c.domain})") for c in companies]
    selected_company_id = request.args.get('company_id', type=int) or (companies[0].id if companies else None)
    if form.validate_on_submit():
        company_id = form.company_id.data
        # bump version
        from sqlalchemy import func
        max_ver = db.session.query(func.max(LGPDRevision.version)).filter_by(company_id=company_id).scalar() or 0
        rev = LGPDRevision(company_id=company_id, subject=form.subject.data, body=form.body.data,
                           version=max_ver + 1, published=form.publish_now.data, created_by_id=current_user.id)
        if rev.published:
            LGPDRevision.query.filter_by(company_id=company_id, published=True).update({'published': False})
        db.session.add(rev)
        db.session.commit()
        try:
            audit('lgpd_revision', rev.id, 'create', user_id=current_user.id, data=f"v={rev.version}; published={rev.published}")
        except Exception:
            pass
        flash('Revisão LGPD salva.', 'success')
        return redirect(url_for('admin.lgpd_center', company_id=company_id))
    items = []
    if selected_company_id:
        items = LGPDRevision.query.filter_by(company_id=selected_company_id).order_by(LGPDRevision.created_at.desc()).all()
    return render_template('admin/lgpd.html', form=form, items=items, companies=companies, selected_company_id=selected_company_id)


@admin_bp.route('/lgpd/<int:rev_id>/publish', methods=['POST'])
def lgpd_publish(rev_id):
    rev = LGPDRevision.query.get_or_404(rev_id)
    LGPDRevision.query.filter_by(company_id=rev.company_id, published=True).update({'published': False})
    rev.published = True
    db.session.commit()
    try:
        audit('lgpd_revision', rev.id, 'publish', user_id=current_user.id, data=f"v={rev.version}")
    except Exception:
        pass
    flash('Revisão publicada.', 'success')
    return redirect(url_for('admin.lgpd_center', company_id=rev.company_id))

