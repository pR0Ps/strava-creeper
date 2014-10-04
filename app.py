#!/usr/bin/env python

from flask import Flask, request, session, redirect, url_for, flash
from flask import render_template_string

from stravalib import Client

try:
    from config import SECRET_KEY, STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET, STRAVA_CALLBACK_URL
except ImportError:
    print ("Couldn't get data from the config.py file")
    print ("Create 'config.py' that sets 'SECRET_KEY', 'STRAVA_CLIENT_ID'," \
           "'STRAVA_CLIENT_SECRET', and 'STRAVA_CALLBACK_URL'")
    raise

DEBUG = True

app = Flask(__name__)
app.config.from_object(__name__)

@app.route('/')
def index():
    return "<html><body>index</body></html>"

@app.route('/login')
def login():
    if session.get('access_token', None) is None:
        return redirect(Client().authorization_url(client_id=STRAVA_CLIENT_ID, redirect_uri=STRAVA_CALLBACK_URL))
    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.pop('access_token', None)
    return redirect(url_for('index'))

@app.route('/auth')
def auth():
    code = request.args.get('code')
    token = Client().exchange_code_for_token(client_id=STRAVA_CLIENT_ID, client_secret=STRAVA_CLIENT_SECRET, code=code)
    if token:
        session['access_token'] = token
    return redirect(url_for('process'))

@app.route('/process')
def process():
    token = session.get('access_token', None)
    if token is None:
        return redirect(url_for('login'))
    client = Client(token)
    athlete = client.get_athlete()

    return "<html><body><img src='{}'/>{} {}</body></html>".format(athlete.profile, athlete.firstname, athlete.lastname)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)



