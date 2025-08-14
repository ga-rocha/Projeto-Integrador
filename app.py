from flask import Flask, render_template, request, redirect, url_for, flash
from flask_mail import Mail, Message
from flask import session
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
import pyodbc
import config
import re
import os
import secrets

# Se existir no ambiente, usa, senão cria uma nova
SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_hex(32))

# Strings de conexão
SQLSERVER_LOCAL = os.getenv("SQLSERVER_LOCAL", "mssql+pyodbc://sa:unifai2022@localhost/SistemaAltasdePaciente_Gabriel_Rocha_Melo_RA_026823?driver=ODBC+Driver+17+for+SQL+Server")

app = Flask(__name__)
app.secret_key = config.SECRET_KEY

# Exemplo de uso de uma string de conexão
# conn_string = config.SQLSERVER_LOCAL
# conn_string = config.SQLSERVER_WINDOWS


# ===== CONFIGURAÇÃO DO EMAIL =====
app.config["MAIL_SERVER"] = "smtp.gmail.com"
app.config["MAIL_PORT"] = 587
app.config["MAIL_USE_TLS"] = True
app.config["MAIL_USERNAME"] = "@gmail.com"  # Trocar
app.config["MAIL_PASSWORD"] = "suasenha"            # Trocar
app.config["MAIL_DEFAULT_SENDER"] = "seuemail@gmail.com"

mail = Mail(app)

# Token seguro
s = URLSafeTimedSerializer(app.secret_key)

# ===== CONEXÕES SQL SERVER =====
conn_str_local = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=localhost;"
    "DATABASE=SistemaAltasdePaciente_Gabriel_Rocha_Melo_RA_026823;"
    "UID=sa;PWD=unifai2022"
)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario = request.form["usuario"]
        senha = request.form["senha"]

        with pyodbc.connect(conn_str_local) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT senha FROM Usuarios WHERE login = ?", (usuario,))
            resultado = cursor.fetchone()

        if resultado:
            senha_correta = resultado[0]
            if senha == senha_correta:
                return redirect(url_for("dashboard"))
            else:
                flash("Usuário ou senha incorretos.", "error")
        else:
            flash("Usuário ou senha incorretos.", "error")

    return render_template("login.html")

        # with pyodbc.connect(conn_str_local) as conn:
        #     cursor = conn.cursor()
        #     cursor.execute("SELECT senha FROM Usuarios WHERE login = ?", (usuario,))
        #     row = cursor.fetchone()

        #     if row and row[0] == senha:
        #         session["usuario"] = usuario
        #         return redirect(url_for("dashboard"))
        #     else:
        #         flash("Usuário não registrado. Clique em 'Registre-se' para criar uma nova conta.", "danger")
        #         return redirect(url_for("login"))
        # return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if not session.get("admin_logado"):
        flash("Acesso negado. Faça login como administrador.", "error")
        return redirect("/login_admin")
    
    if request.method == "POST":
        usuario = request.form["usuario"].strip()
        senha = request.form["senha"].strip()
        nome = request.form["nome_completo"].strip()
        registro = request.form["registro_profissional"].strip()
        especialidade_nome = request.form["especialidade"].strip()
        email = request.form["email"].strip()

        with pyodbc.connect(conn_str_local) as conn:
            cursor = conn.cursor()

            # Verifica se login já existe
            cursor.execute("SELECT COUNT(*) FROM Usuarios WHERE login = ?", (usuario,))
            if cursor.fetchone()[0] > 0:
                flash("Esse nome de usuário já está em uso. Escolha outro.", "error")
                return redirect("/register")

            # Verifica se email já existe
            cursor.execute("SELECT COUNT(*) FROM Usuarios WHERE email = ?", (email,))
            if cursor.fetchone()[0] > 0:
                flash("Esse email já está cadastrado. Use outro.", "error")
                return redirect("/register")

            # Verifica se especialidade já existe
            cursor.execute("SELECT id_especialidade FROM Especialidade WHERE nome = ?", (especialidade_nome,))
            esp = cursor.fetchone()
            if esp:
                id_esp = esp[0]
            else:
                cursor.execute("SELECT MAX(id_especialidade) FROM Especialidade")
                max_id = cursor.fetchone()[0]
                id_esp = (max_id or 0) + 1
                cursor.execute("INSERT INTO Especialidade (id_especialidade, nome) VALUES (?, ?)", (id_esp, especialidade_nome))

            # Valida senha
            if not re.match(r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$', senha):
                flash("A senha deve ter pelo menos 8 caracteres, incluindo letras maiúsculas, minúsculas, números e símbolos.", "error")
                return redirect("/register")

            # Insere profissional
            cursor.execute("SELECT MAX(id_profissional) FROM Profissional_da_Saude")
            max_prof = cursor.fetchone()[0]
            id_prof = (max_prof or 0) + 1
            cursor.execute("""
                INSERT INTO Profissional_da_Saude (id_profissional, nome, registro_medico, id_especialidade)
                VALUES (?, ?, ?, ?)
            """, (id_prof, nome, registro, id_esp))

            # Insere usuário com email
            cursor.execute("INSERT INTO Usuarios (login, senha, email) VALUES (?, ?, ?)", (usuario, senha, email))

            conn.commit()
            session.pop("admin_logado", None)
            flash("Usuário registrado com sucesso.", "success")
            return redirect("/login")

    return render_template("register.html")

@app.route("/login_admin", methods=["GET", "POST"])
def login_admin():


    if request.method == "POST":
        login = request.form["login"].strip()
        senha = request.form["senha"].strip()

        with pyodbc.connect(conn_str_local) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM Administradores WHERE login = ? AND senha = ?", (login, senha))
            admin = cursor.fetchone()

            if admin:
                session["admin_logado"] = True
                flash("Login de administrador bem-sucedido!", "success")
                return redirect("/register")
            else:
                flash("Administrador não cadastrado ou senha incorreta.", "error")
                return redirect("/login_admin")

    return render_template("login_admin.html")


@app.route("/send_confirmation/<email>")
def send_confirmation(email):
    token = s.dumps(email, salt="email-confirm")
    link = url_for("confirm_email", token=token, _external=True)

    msg = Message("Confirme seu email", recipients=[email])
    msg.body = f"Clique no link para confirmar: {link}"
    mail.send(msg)

    flash("Email de confirmação enviado!", "info")
    return redirect(url_for("login"))

@app.route("/confirm_email/<token>")
def confirm_email(token):
    try:
        email = s.loads(token, salt="email-confirm", max_age=3600)
        flash("Email confirmado com sucesso!", "success")
    except SignatureExpired:
        flash("Token expirado.", "danger")
    except BadSignature:
        flash("Token inválido.", "danger")
    return redirect(url_for("login"))

@app.route("/reset_password", methods=["GET", "POST"])
def reset_password():
    if request.method == "POST":
        entrada = request.form["usuario_email"].strip()

        with pyodbc.connect(conn_str_local) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM Usuarios WHERE login = ? OR email = ?", (entrada, entrada))
            if cursor.fetchone()[0] == 0:
                flash("Usuário ou email não registrado.", "danger")
                return render_template("reset_password.html")

            # Aqui você pode enviar o código por email
            flash("Se usuário ou email existir, será enviado código de recuperação.", "info")
            return redirect(url_for("login"))

    return render_template("reset_password.html")

@app.route("/dashboard")
def dashboard():
    if "usuario" not in session:
        flash("Você precisa estar logado para acessar o dashboard.", "warning")
        return redirect(url_for("login"))
    
    usuario = session["usuario"]
    return render_template("dashboard.html", usuario=usuario)

@app.route("/logout")
def logout():
    session.pop("usuario", None)
    flash("Logout realizado com sucesso.", "info")
    return redirect(url_for("login"))

if __name__ == "__main__":
    app.run(debug=True)

@app.route("/login_admin", methods=["GET", "POST"])
def login_admin():
    if request.method == "POST":
        login = request.form["login"].strip()
        senha = request.form["senha"].strip()

        with pyodbc.connect(conn_str_local) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM Administradores WHERE login = ? AND senha = ?", (login, senha))
            admin = cursor.fetchone()

            if admin:
                session["admin_logado"] = True
                flash("Login de administrador bem-sucedido!", "success")
                return redirect("/register")  # ou outra rota exclusiva
            else:
                flash("Administrador não cadastrado ou senha incorreta.", "error")
                return redirect("/login_admin")

    return render_template("login_admin.html")
