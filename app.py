import http.client
import json
from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin, login_user, login_required, current_user, logout_user, LoginManager
from datetime import datetime

app = Flask(__name__)

app.config['SECRET_KEY'] = 'sua_chave_secreta'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), nullable=False, unique=True)
    password = db.Column(db.String(150), nullable=False)
    habilidades = db.Column(db.String(500), nullable=True)
    areas_interesse = db.Column(db.String(500), nullable=True)
    ultima_busca = db.Column(db.String(500), nullable=True)  # Adiciona campo de última busca


with app.app_context():
    db.create_all()


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def buscar_vagas_jooble(palavra_chave):
    host = 'br.jooble.org'
    connection = http.client.HTTPConnection(host)

    body = json.dumps({
        "keywords": palavra_chave,
        "location": "Brasil",
        "page": 1,
        "limit": 10
    })

    headers = {
        "Content-type": "application/json",
        "Authorization": "Bearer 7a88abc5-e2fe-45ed-9956-32a1b6c45775"
    }

    try:
        connection.request('POST', '/api/7a88abc5-e2fe-45ed-9956-32a1b6c45775', body, headers)
        response = connection.getresponse()
        data = response.read()

        if response.status == 200:
            data_json = json.loads(data)

            # Formatar a data para 'dd/mm/yyyy'
            for vaga in data_json.get('jobs', []):
                if 'updated' in vaga:
                    try:
                        vaga['updated'] = datetime.fromisoformat(vaga['updated']).strftime("%d/%m/%Y")
                    except ValueError:
                        vaga['updated'] = "Data não disponível"
            return data_json.get('jobs', [])
        else:
            return []

    except Exception as e:
        print(f"Erro na requisição à API: {e}")
        return []


def filtrar_por_habilidades(habilidades_usuario, vagas):
    habilidades_usuario_set = set(habilidades_usuario.lower().split(', '))
    vagas_filtradas = []

    for vaga in vagas:
        habilidades_vaga = set(vaga.get('skills', '').lower().split(', ')) if vaga.get('skills') else set()
        faltantes = habilidades_vaga - habilidades_usuario_set

        if not faltantes:
            vagas_filtradas.append(vaga)

    return vagas_filtradas


@app.route('/', methods=['GET', 'POST'])
@login_required
def home():
    if request.method == 'POST':
        return redirect(url_for('perfil'))
    return render_template('form.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and user.password == password:
            login_user(user)
            return redirect(url_for('home'))
        else:
            return render_template('login.html', error="Nome de usuário ou senha incorretos.")
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user_exists = User.query.filter_by(username=username).first()
        if user_exists:
            return render_template('register.html', error="Nome de usuário já está em uso. Escolha outro.")
        else:
            new_user = User(username=username, password=password)
            db.session.add(new_user)
            db.session.commit()
            return render_template('register.html', success="Conta cadastrada com sucesso! Faça login.")
    return render_template('register.html')


@app.route('/perfil', methods=['GET', 'POST'])
@login_required
def perfil():
    if request.method == 'POST':
        habilidades = request.form.get('habilidades')
        areas_interesse = request.form.getlist('areas_interesse')

        current_user.habilidades = habilidades
        current_user.ultima_busca = habilidades
        current_user.areas_interesse = ', '.join(areas_interesse)
        db.session.commit()

        return redirect(url_for('resultado', pesquisa=current_user.habilidades))

    return render_template('perfil.html', ultima_busca=current_user.ultima_busca)


@app.route('/resultado', methods=['GET'])
@login_required
def resultado():
    pesquisa_habilidades = request.args.get('pesquisa')
    pagina = int(request.args.get('pagina', 1))

    vagas = buscar_vagas_jooble(pesquisa_habilidades)

    vagas_filtradas = filtrar_por_habilidades(current_user.habilidades, vagas)

    total_vagas = len(vagas_filtradas)

    vagas_por_pagina = 10
    total_paginas = (total_vagas // vagas_por_pagina) + (1 if total_vagas % vagas_por_pagina > 0 else 0)

    vagas_paginadas = vagas_filtradas[(pagina - 1) * vagas_por_pagina: pagina * vagas_por_pagina]

    return render_template('result.html', vagas=vagas_paginadas, pagina=pagina, total_paginas=total_paginas,
                           pesquisa=pesquisa_habilidades, total_vagas=total_vagas)


@app.route('/ultima-busca', methods=['POST'])
@login_required
def ultima_busca():
    if current_user.ultima_busca:
        return redirect(url_for('resultado', pesquisa=current_user.ultima_busca))
    return redirect(url_for('perfil'))


if __name__ == '__main__':
    app.run(debug=True)
