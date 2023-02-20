from flask import Flask, render_template, url_for, redirect, request, flash, get_flashed_messages
from datetime import date
from urllib.parse import urlparse
from bs4 import BeautifulSoup
import psycopg2, os, validators, requests


app = Flask(__name__)
app.secret_key = "super_secret_key"

DATABASE_URL = os.getenv('DATABASE_URL')
conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()


def make_check(url):
    resp = requests.get(url)
    soup = BeautifulSoup(resp.text, 'html.parser')

    try:
        h1 = soup.h1.text
    except AttributeError:
        h1 = ''

    try:
        title = soup.title.string
    except AttributeError:
        title = ''

    try:
        desc = soup.meta['content']
    except KeyError:
        desc = ''

    return h1, title, desc


@app.get('/')
def get_index():
    messages = get_flashed_messages(with_categories=True)
    return render_template('index.html', messages=messages)


@app.post('/')
def post_index():
    data = request.form.to_dict()
    if validators.url(data['url']):
        p = urlparse(data['url'])
        url = f'{p.scheme}://{p.hostname}'

        cur.execute("SELECT name FROM urls")
        added_urls = cur.fetchall()
        if (url,) in added_urls:
            cur.execute(f"SELECT id FROM urls WHERE name = '{url}'")
            id = cur.fetchone()

            flash('Страница уже существует', 'info')
            return redirect(url_for('get_url', id=id[0]))

        cur.execute(f"INSERT INTO urls (name, created_at) VALUES ('{url}', '{date.today()}')")
        conn.commit()

        cur.execute(f"SELECT id FROM urls WHERE name = '{url}'")
        id = cur.fetchone()

        flash('Страница успешно добавлена', 'success')
        return redirect(url_for('get_url', id=id[0]))
    flash('Некорректный URL', 'error')
    return redirect(url_for('get_index'))


@app.route('/urls')
def get_urls():
    cur.execute("SELECT DISTINCT ON (urls.id) urls.id, urls.name, url_checks.created_at, url_checks.status_code FROM urls LEFT JOIN url_checks ON urls.id = url_checks.url_id ORDER BY urls.id DESC")
    data = cur.fetchall()
    return render_template('urls.html', data=data)


@app.route('/urls/<id>')
def get_url(id):
    messages = get_flashed_messages(with_categories=True)

    cur.execute(f"SELECT * FROM urls WHERE id = {id[0]}")
    data = cur.fetchone()

    cur.execute(f"SELECT * FROM url_checks WHERE url_id = {id[0]} ORDER BY id DESC")
    checks = cur.fetchall()

    return render_template('url.html', messages=messages, data=data, checks=checks)


@app.post('/urls/<id>/checks')
def post_check(id):
    cur.execute(f"SELECT name FROM urls WHERE id = {id}")
    url = cur.fetchone()

    try:
        resp = requests.get(url[0])
    except requests.exceptions.ConnectionError:
        flash('Произошла ошибка при проверке', 'error')
        return redirect(url_for('get_url', id=id))

    h1, title, desc = make_check(url[0])

    cur.execute(f"INSERT INTO url_checks (url_id, status_code, h1, title, description, created_at) VALUES ({id}, {resp.status_code}, '{h1}', '{title}', '{desc}', '{date.today()}')")
    conn.commit()
    return redirect(url_for('get_url', id=id))