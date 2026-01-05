from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, BooleanField, IntegerField, SelectField, TextAreaField
from flask_wtf.file import FileField
from wtforms.validators import DataRequired, Length, Optional, NumberRange, Email


class CompanyForm(FlaskForm):
    name = StringField('Nome', validators=[DataRequired(), Length(max=120)])
    domain = StringField('Domínio', validators=[DataRequired(), Length(max=120)])
    terms_url = StringField('URL dos Termos/LGPD', validators=[Optional(), Length(max=255)],
                         description='URL para os Termos de Uso e Política de Privacidade (LGPD)')
    consent_required = BooleanField('Exigir consentimento', default=False)
    retention_days = IntegerField('Retenção (dias)', validators=[Optional(), NumberRange(min=1)], default=365)
    allowed_ips = TextAreaField('IPs/CIDRs permitidos (um por linha)', validators=[Optional()])
    accept_any_domain = BooleanField('Aceitar cadastros com qualquer domínio de e-mail', default=False)
    brand_primary = StringField('Cor primária (hex, opcional)', validators=[Optional(), Length(max=16)])
    brand_primary_dark = StringField('Cor primária (escura, opcional)', validators=[Optional(), Length(max=16)])
    brand_primary_light = StringField('Cor primária (clara, opcional)', validators=[Optional(), Length(max=16)])
    logo_url = StringField('Logo URL (opcional)', validators=[Optional(), Length(max=255)])
    lgpd_url = StringField('URL da Política LGPD (opcional)', validators=[Optional(), Length(max=255)], 
                         description='Link para a política LGPD da empresa')
    logo_file = FileField('Logo (upload opcional)')
    submit = SubmitField('Salvar')


class UserCreateForm(FlaskForm):
    company_id = SelectField('Empresa', coerce=int, validators=[DataRequired()])
    name = StringField('Nome', validators=[DataRequired(), Length(max=120)])
    email = StringField('E-mail', validators=[DataRequired(), Email(), Length(max=255)])
    role = SelectField('Perfil', choices=[('client','Cliente'),('tech','Técnico'),('supervisor','Supervisor'),('admin','Administrador')], default='client')
    password = StringField('Senha temporária (opcional)', validators=[Optional(), Length(min=6, max=255)])
    confirmed = BooleanField('Confirmado', default=True)
    force_2fa = BooleanField('Exigir 2FA', default=False)
    submit = SubmitField('Criar usuário')


class UserEditForm(FlaskForm):
    company_id = SelectField('Empresa', coerce=int, validators=[DataRequired()])
    name = StringField('Nome', validators=[DataRequired(), Length(max=120)])
    email = StringField('E-mail', validators=[DataRequired(), Email(), Length(max=255)])
    role = SelectField('Perfil', choices=[('client','Cliente'),('tech','Técnico'),('supervisor','Supervisor'),('admin','Administrador')])
    password = StringField('Nova senha (opcional)', validators=[Optional(), Length(min=6, max=255)])
    confirmed = BooleanField('Confirmado')
    force_2fa = BooleanField('Exigir 2FA')
    avatar_file = FileField('Foto de perfil (opcional)')
    submit = SubmitField('Salvar alterações')


class CategoryForm(FlaskForm):
    company_id = SelectField('Empresa', coerce=int, validators=[Optional()], default=0)
    name = StringField('Nome', validators=[DataRequired(), Length(max=100)])
    parent_id = SelectField('Categoria pai', coerce=int, validators=[Optional()], default=0)
    submit = SubmitField('Salvar')


class ContractForm(FlaskForm):
    company_id = SelectField('Empresa', coerce=int, validators=[DataRequired()])
    name = StringField('Nome', validators=[DataRequired(), Length(max=120)])
    active = BooleanField('Ativo', default=True)
    submit = SubmitField('Salvar')


class SLAPlanForm(FlaskForm):
    company_id = SelectField('Empresa', coerce=int, validators=[DataRequired()])
    name = StringField('Nome', validators=[DataRequired(), Length(max=120)])
    first_response_minutes = IntegerField('1ª resposta (min)', validators=[DataRequired(), NumberRange(min=0)])
    resolution_minutes = IntegerField('Resolução (min)', validators=[DataRequired(), NumberRange(min=0)])
    contract_id = SelectField('Contrato', coerce=int, validators=[Optional()], default=0)
    category_id = SelectField('Categoria', coerce=int, validators=[Optional()], default=0)
    priority = SelectField('Prioridade (opcional)', choices=[('', '—'), ('Baixa', 'Baixa'), ('Média', 'Média'), ('Alta', 'Alta'), ('Crítica', 'Crítica')], default='')
    active = BooleanField('Ativo', default=True)
    submit = SubmitField('Salvar')


class UserRoleForm(FlaskForm):
    role = SelectField('Perfil', choices=[('client','Cliente'),('tech','Técnico'),('supervisor','Supervisor'),('admin','Administrador')])
    submit = SubmitField('Aplicar')


class QueueForm(FlaskForm):
    company_id = SelectField('Empresa', coerce=int, validators=[DataRequired()])
    name = StringField('Nome', validators=[DataRequired(), Length(max=120)])
    active = BooleanField('Ativa', default=True)
    submit = SubmitField('Salvar')


class AssetForm(FlaskForm):
    company_id = SelectField('Empresa', coerce=int, validators=[DataRequired()])
    name = StringField('Nome', validators=[DataRequired(), Length(max=200)])
    serial = StringField('Serial', validators=[Optional(), Length(max=120)])
    type = StringField('Tipo', validators=[Optional(), Length(max=120)])
    active = BooleanField('Ativo', default=True)
    submit = SubmitField('Salvar')


class EmailTemplateForm(FlaskForm):
    company_id = SelectField('Empresa (opcional)', coerce=int, validators=[Optional()], default=0)
    name = SelectField('Evento', choices=[
        ('ticket_created','Ticket criado'),
        ('ticket_comment','Comentário'),
        ('ticket_status','Status'),
        ('ticket_closed','Encerramento'),
        ('otp_code','OTP'),
        ('lgpd','LGPD (texto padrão)'),
    ])
    subject = StringField('Assunto', validators=[DataRequired(), Length(max=255)])
    body = TextAreaField('Corpo', validators=[DataRequired()])
    active = BooleanField('Ativo', default=True)
    submit = SubmitField('Salvar')


class ProblemForm(FlaskForm):
    company_id = SelectField('Empresa', coerce=int, validators=[DataRequired()])
    title = StringField('Título', validators=[DataRequired(), Length(max=200)])
    description = TextAreaField('Descrição', validators=[Optional()])
    status = SelectField('Status', choices=[('Aberto','Aberto'),('Investigação','Investigação'),('Mitigado','Mitigado'),('Fechado','Fechado')])
    submit = SubmitField('Salvar')


class ChangeRequestForm(FlaskForm):
    company_id = SelectField('Empresa', coerce=int, validators=[DataRequired()])
    title = StringField('Título', validators=[DataRequired(), Length(max=200)])
    description = TextAreaField('Descrição', validators=[Optional()])
    status = SelectField('Status', choices=[('Proposta','Proposta'),('Planejada','Planejada'),('Em execução','Em execução'),('Concluída','Concluída'),('Cancelada','Cancelada')])
    approval = SelectField('Aprovação', choices=[('Pendente','Pendente'),('Aprovada','Aprovada'),('Rejeitada','Rejeitada')])
    submit = SubmitField('Salvar')


class LGPDRevisionForm(FlaskForm):
    company_id = SelectField('Empresa', coerce=int, validators=[DataRequired()])
    subject = StringField('Assunto', validators=[DataRequired(), Length(max=255)])
    body = TextAreaField('Conteúdo', validators=[DataRequired()])
    publish_now = BooleanField('Publicar agora', default=False)
    submit = SubmitField('Salvar revisão')
