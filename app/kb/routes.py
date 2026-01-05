from flask import Blueprint, render_template, redirect, url_for, flash, request, abort, jsonify
from flask_login import login_required, current_user
from ..models import KnowledgeBaseArticle, Company
from .. import db
from .forms import ArticleForm
from ..utils import role_required


kb_bp = Blueprint('kb', __name__, template_folder='../templates')


@kb_bp.route('/')
@login_required
def index():
    if current_user.role in ('admin','supervisor','tech'):
        articles = KnowledgeBaseArticle.query.order_by(KnowledgeBaseArticle.updated_at.desc()).all()
    else:
        articles = KnowledgeBaseArticle.query.filter_by(public=True, company_id=current_user.company_id, status='published').order_by(KnowledgeBaseArticle.updated_at.desc()).all()
    return render_template('kb/index.html', articles=articles)


@kb_bp.route('/create', methods=['GET','POST'])
@login_required
@role_required('admin','supervisor','tech')
def create():
    form = ArticleForm()
    form.company_id.choices = [(c.id, f"{c.name} ({c.domain})") for c in Company.query.order_by(Company.name).all()]
    if form.validate_on_submit():
        art = KnowledgeBaseArticle(
            company_id=form.company_id.data,
            title=form.title.data,
            content=form.content.data,
            public=form.public.data,
            status=form.status.data,
            created_by_id=current_user.id,
        )
        db.session.add(art)
        db.session.commit()
        flash('Artigo criado.', 'success')
        return redirect(url_for('kb.index'))
    return render_template('kb/edit.html', form=form, article=None)


@kb_bp.route('/<int:article_id>/edit', methods=['GET','POST'])
@login_required
@role_required('admin','supervisor','tech')
def edit(article_id):
    art = KnowledgeBaseArticle.query.get_or_404(article_id)
    form = ArticleForm(obj=art)
    form.company_id.choices = [(c.id, f"{c.name} ({c.domain})") for c in Company.query.order_by(Company.name).all()]
    if form.validate_on_submit():
        art.company_id = form.company_id.data
        art.title = form.title.data
        art.content = form.content.data
        art.public = form.public.data
        art.status = form.status.data
        db.session.commit()
        flash('Artigo atualizado.', 'success')
        return redirect(url_for('kb.index'))
    return render_template('kb/edit.html', form=form, article=art)


@kb_bp.route('/<int:article_id>')
@login_required
def view(article_id):
    art = KnowledgeBaseArticle.query.get_or_404(article_id)
    if current_user.role not in ('admin','supervisor','tech'):
        if not (art.public and art.company_id == current_user.company_id and art.status == 'published'):
            abort(403)
    return render_template('kb/view.html', article=art)


@kb_bp.route('/search')
@login_required
def search():
    q = (request.args.get('q') or '').strip().lower()
    if not q:
        return jsonify([])
    query = KnowledgeBaseArticle.query
    if current_user.role not in ('admin','supervisor','tech'):
        query = query.filter_by(company_id=current_user.company_id, public=True, status='published')
    results = query.filter(
        (KnowledgeBaseArticle.title.ilike(f"%{q}%")) | (KnowledgeBaseArticle.content.ilike(f"%{q}%"))
    ).order_by(KnowledgeBaseArticle.updated_at.desc()).limit(5).all()
    return jsonify([
        {
            'id': a.id,
            'title': a.title,
            'url': url_for('kb.view', article_id=a.id)
        } for a in results
    ])
