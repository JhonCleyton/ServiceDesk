from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField, SelectField
from wtforms.validators import DataRequired, Email, Length, EqualTo


class LoginForm(FlaskForm):
    email = StringField('E-mail', validators=[DataRequired(), Email()])
    password = PasswordField('Senha', validators=[DataRequired()])
    remember = BooleanField('Lembrar')
    submit = SubmitField('Entrar')


class RegisterForm(FlaskForm):
    name = StringField('Nome', validators=[DataRequired(), Length(min=2, max=120)])
    company_id = SelectField('Empresa', coerce=int, validators=[DataRequired()])
    email = StringField('E-mail corporativo', validators=[DataRequired(), Email()])
    password = PasswordField('Senha', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirmar Senha', validators=[DataRequired(), EqualTo('password')])
    agree = BooleanField('Concordo com os Termos e Política de Privacidade')
    submit = SubmitField('Criar conta')


class OTPForm(FlaskForm):
    email = StringField('E-mail', validators=[DataRequired(), Email()])
    code = StringField('Código', validators=[DataRequired(), Length(min=6, max=6)])
    submit = SubmitField('Verificar')


class ForgotPasswordForm(FlaskForm):
    email = StringField('E-mail', validators=[DataRequired(), Email()])
    submit = SubmitField('Enviar link de redefinição')


class ResetPasswordForm(FlaskForm):
    password = PasswordField('Nova senha', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirmar nova senha', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Definir nova senha')
