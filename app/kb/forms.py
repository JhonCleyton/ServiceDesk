from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, BooleanField, SubmitField, SelectField
from wtforms.validators import DataRequired, Length


class ArticleForm(FlaskForm):
    company_id = SelectField('Empresa', coerce=int)
    title = StringField('Título', validators=[DataRequired(), Length(max=200)])
    content = TextAreaField('Conteúdo', validators=[DataRequired()])
    public = BooleanField('Público')
    status = SelectField('Status', choices=[('draft','Rascunho'),('published','Publicado'),('archived','Arquivado')], default='draft')
    submit = SubmitField('Salvar')
