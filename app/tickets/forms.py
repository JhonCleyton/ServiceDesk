from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, SubmitField, BooleanField
from wtforms.validators import DataRequired, Length
from flask_wtf.file import FileAllowed, MultipleFileField


PRIORITY_CHOICES = [('Baixa', 'Baixa'), ('Média', 'Média'), ('Alta', 'Alta'), ('Crítica', 'Crítica')]


class TicketCreateForm(FlaskForm):
    title = StringField('Título', validators=[DataRequired(), Length(max=200)])
    description = TextAreaField('Descrição detalhada', validators=[DataRequired()])
    priority = SelectField('Prioridade', choices=PRIORITY_CHOICES, default='Média')
    cat_parent_id = SelectField('Categoria', coerce=int, validators=[], default=0)
    cat_child_id = SelectField('Subcategoria', coerce=int, validators=[], default=0)
    contract_id = SelectField('Contrato', coerce=int, validators=[], default=0)
    queue_id = SelectField('Fila/Equipe', coerce=int, validators=[], default=0)
    asset_id = SelectField('Ativo', coerce=int, validators=[], default=0)
    attachments = MultipleFileField('Anexos', validators=[FileAllowed(['jpg', 'jpeg', 'png', 'gif', 'pdf', 'txt', 'log', 'csv', 'xlsx', 'docx', 'zip'], 'Tipos de arquivo não permitidos')])
    submit = SubmitField('Abrir chamado')


class CommentForm(FlaskForm):
    content = TextAreaField('Comentário', validators=[DataRequired()])
    internal = BooleanField('Comentário interno')
    attachments = MultipleFileField('Anexos', validators=[FileAllowed(['jpg', 'jpeg', 'png', 'gif', 'pdf', 'txt', 'log', 'csv', 'xlsx', 'docx', 'zip'], 'Tipos de arquivo não permitidos')])
    submit = SubmitField('Adicionar comentário')


class AssignForm(FlaskForm):
    assignee_id = SelectField('Atribuir a', coerce=int)
    status = SelectField('Status', choices=[('Novo','Novo'),('Em atendimento','Em atendimento'),('Aguardando','Aguardando'),('Resolvido','Resolvido'),('Fechado','Fechado')])
    queue_id = SelectField('Fila/Equipe', coerce=int)
    submit = SubmitField('Aplicar')


class ResolveForm(FlaskForm):
    solution = TextAreaField('Solução aplicada', validators=[DataRequired()])
    submit = SubmitField('Resolver')


class CloseForm(FlaskForm):
    reason = StringField('Motivo do encerramento', validators=[DataRequired(), Length(max=255)])
    tech_evaluation = TextAreaField('Avaliação técnica (obrigatória)', validators=[DataRequired()])
    tech_eval_category = SelectField('Classificação', choices=[
        ('tecnico', 'Erro técnico'),
        ('sistemico', 'Erro sistêmico'),
        ('usuario', 'Erro do usuário'),
        ('solicitacao', 'Solicitação'),
        ('melhoria', 'Melhoria'),
        ('outro', 'Outro'),
    ], default='tecnico')
    submit = SubmitField('Encerrar')


class RatingForm(FlaskForm):
    rating = StringField('Avaliação', validators=[DataRequired()])  # Campo oculto para a classificação
    comment = TextAreaField('Comentário (opcional)')
    submit = SubmitField('Enviar avaliação')
