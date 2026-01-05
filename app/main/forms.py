from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email, Length, Optional, EqualTo
from flask_wtf.file import FileField


class ProfileForm(FlaskForm):
    name = StringField('Nome', validators=[DataRequired(), Length(max=120)])
    email = StringField('E-mail', validators=[DataRequired(), Email(), Length(max=255)])
    password = PasswordField('Nova senha (opcional)', validators=[Optional(), Length(min=6)])
    confirm_password = PasswordField('Confirmar Senha', validators=[Optional(), EqualTo('password')])
    avatar_file = FileField('Foto de perfil (opcional)')
    submit = SubmitField('Salvar alterações')


class LGPDAcceptForm(FlaskForm):
    submit = SubmitField('Aceitar')
