from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, jsonify
from flask_login import login_required, current_user
from .. import db
from ..models import User, GameScore, EmailTemplate, Company, LGPDRevision
from .forms import ProfileForm, LGPDAcceptForm
from werkzeug.utils import secure_filename
from datetime import datetime
import os
import uuid
try:
    from PIL import Image  # type: ignore
except Exception:
    Image = None


main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    return render_template('index.html')


@main_bp.route('/dashboard')
@login_required
def dashboard():
    try:
        if not getattr(current_user.company, 'active', True):
            flash('Sua empresa está inativa. Algumas funcionalidades podem estar indisponíveis.', 'warning')
    except Exception:
        pass
    return render_template('dashboard.html')


@main_bp.route('/meu-perfil', methods=['GET','POST'])
@login_required
def profile():
    form = ProfileForm(obj=current_user)
    if form.validate_on_submit():
        # E-mail único
        email = form.email.data.strip().lower()
        if User.query.filter(User.id != current_user.id, User.email == email).first():
            flash('E-mail já está em uso por outro usuário.', 'danger')
            return render_template('main/profile.html', form=form)
        current_user.name = form.name.data.strip()
        current_user.email = email
        if form.password.data:
            current_user.set_password(form.password.data)
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
                current_user.avatar_filename = filename
        db.session.commit()
        flash('Perfil atualizado com sucesso.', 'success')
        return redirect(url_for('main.profile'))
    return render_template('main/profile.html', form=form)


@main_bp.route('/lgpd', methods=['GET','POST'])
@login_required
def lgpd():
    form = LGPDAcceptForm()
    company = getattr(current_user, 'company', None)
    
    if not company:
        flash('Você não está associado a nenhuma empresa.', 'warning')
        return redirect(url_for('main.dashboard'))
    
    # Get the latest published revision for the user's company
    lgpd_rev = LGPDRevision.query.filter_by(
        company_id=company.id, 
        published=True
    ).order_by(LGPDRevision.version.desc()).first()
    
    if form.validate_on_submit():
        current_user.consent_accepted_at = datetime.utcnow()
        db.session.commit()
        flash('Consentimento registrado com sucesso.', 'success')
        return redirect(url_for('main.dashboard'))
        
    return render_template('main/lgpd.html', 
                         form=form, 
                         company=company,
                         lgpd_rev=lgpd_rev,
                         lgpd_url=company.terms_url)


@main_bp.route('/lgpd/public/<int:company_id>')
def lgpd_public(company_id):
    company = Company.query.get_or_404(company_id)
    rev = LGPDRevision.query.filter_by(company_id=company.id, published=True).order_by(LGPDRevision.version.desc(), LGPDRevision.created_at.desc()).first()
    if rev:
        subject = rev.subject
        body = rev.body
    else:
        tpl = EmailTemplate.query.filter_by(company_id=company.id, name='lgpd', active=True).first()
        if tpl is None:
            tpl = EmailTemplate.query.filter_by(company_id=None, name='lgpd', active=True).first()
        subject = tpl.subject if tpl else 'Política de Privacidade'
        body = tpl.body if tpl else 'Nenhum conteúdo LGPD configurado.'
    return render_template('main/lgpd_public.html', company=company, subject=subject, body=body, rev=rev)


@main_bp.route('/lgpd/view/<int:rev_id>')
@login_required
def lgpd_view(rev_id):
    rev = LGPDRevision.query.get_or_404(rev_id)
    if not rev.published and not current_user.is_admin:
        flash('Acesso não autorizado.', 'danger')
        return redirect(url_for('main.dashboard'))
    return render_template('lgpd_view.html', rev=rev)


@main_bp.route('/waiting-room')
def waiting_room():
    return render_template('main/waiting_room.html')


@main_bp.route('/api/game/top')
def api_game_top():
    game = (request.args.get('game') or '').strip().lower()
    if game not in ('snake', 'sudoku'):
        return jsonify({'ok': False, 'error': 'invalid game'}), 400
    rows = GameScore.query.filter_by(game=game).order_by(GameScore.score.desc(), GameScore.created_at.asc()).limit(10).all()
    data = [{
        'name': (r.user.name if r.user else (r.name or 'Jogador')),
        'score': r.score,
        'created_at': r.created_at.isoformat() if r.created_at else None,
    } for r in rows]
    return jsonify({'ok': True, 'items': data})


@main_bp.route('/api/game/score')
def api_game_score():
    game = (request.args.get('game') or '').strip().lower()
    try:
        score = int(request.args.get('score', 0))
    except Exception:
        score = 0
    try:
        ms = int(request.args.get('ms', 0))
    except Exception:
        ms = 0
    name = (request.args.get('name') or '').strip()[:120]
    if game not in ('snake', 'sudoku') or score <= 0:
        return jsonify({'ok': False, 'error': 'invalid params'}), 400
    # Anti-cheat baseline rules
    if game == 'snake':
        # Require some time per point and cap unrealistic scores
        if score > 1000:
            return jsonify({'ok': False, 'error': 'score too high'}), 400
        if ms and ms < score * 80:  # at least 80ms per point
            return jsonify({'ok': False, 'error': 'too fast'}), 400
        if score > 50 and ms < 10000:
            return jsonify({'ok': False, 'error': 'too fast'}), 400
    if game == 'sudoku':
        # Recompute score from ms when provided
        if ms:
            secs = max(1, ms // 1000)
            score = max(1, 10000 - secs)
        # Require minimum time to complete and cap max
        if ms and ms < 30000:
            return jsonify({'ok': False, 'error': 'too fast'}), 400
        if score > 9900:
            score = 9900
    r = GameScore(game=game, score=score)
    if current_user.is_authenticated:
        r.user_id = current_user.id
    else:
        r.name = name or 'Jogador'
    db.session.add(r)
    db.session.commit()
    return jsonify({'ok': True})
