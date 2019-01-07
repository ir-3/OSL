from flask import Flask, g, session, redirect, request, url_for, jsonify, abort ,render_template
from requests_oauthlib import OAuth2Session
import psycopg2
# noinspection PyUnresolvedReferences
import config
import os
import re

app = Flask(__name__)
app.debug = True
app.config['SECRET_KEY'] = config.CLIENT_SECRET

DAPI_BASE = "https://discordapp.com/api"
AUTH_BASE = DAPI_BASE + "/oauth2/authorize"
TOKEN_BASE = DAPI_BASE + "/oauth2/token"

if config.REDIRECT_URI.startswith("http://"):
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = 'true'


def token_updater(token):
    session['oauth2_token'] = token


def fetch_user_id(token):
    discord = make_session(token=token)
    return discord.get(DAPI_BASE + "/users/@me").json()['id']


def make_session(token=None, state=None, scope=None):
    return OAuth2Session(
        client_id=config.CLIENT_ID,
        token=token,
        state=state,
        scope=scope,
        redirect_uri=config.REDIRECT_URI,
        auto_refresh_kwargs=dict(
            client_id=config.CLIENT_ID,
            client_secret=config.CLIENT_SECRET
        ),
        auto_refresh_url=TOKEN_BASE
    )


@app.before_request
def get_db():
    if "db" not in g:
        g.db = psycopg2.connect(**config.DATABASE)
        g.db.autocommit = True


@app.teardown_appcontext
def teardown_db(x):
    db = g.pop("db", None)
    if db:
        db.close()


@app.route("/")
def index():
    return render_template("index.html", name="test")


@app.route("/redirect")
def oauth2_login():
    if session.get('oauth2_token'):
        return redirect(url_for(".me"))
    scope = request.args.get(
        "scope",
        "identify guilds"
    )
    discord = make_session(scope=scope.split(" "))
    auth_url, state = discord.authorization_url(AUTH_BASE)
    session['oauth2_state'] = state
    return redirect(auth_url)


@app.route("/callback")
def callback():
    if request.values.get("error"):
        return request.values["error"]
    discord = make_session(state=session.get("oauth2_state"))
    token = discord.fetch_token(
        TOKEN_BASE,
        client_secret=config.CLIENT_SECRET,
        authorization_response=request.url
    )
    session['oauth2_token'] = token
    session['userid'] = discord.get(DAPI_BASE + "/users/@me").json()['id']
    return redirect(url_for(".me"))


@app.route("/me")
def me():
    discord = make_session(token=session.get("oauth2_token"))
    user = discord.get(DAPI_BASE + "/users/@me").json()
    return render_template("home.html", username=user['username'], is_admin=user['id'] in config.ADMINS)


@app.route("/admin")
def admin():
    discord = make_session(token=session.get("oauth2_token"))
    user = discord.get(DAPI_BASE + "/users/@me").json()
    if user['id'] not in config.ADMINS:
        abort(404)
    with g.db.cursor() as cur:
        cur.execute("SELECT * FROM blacklist;")
        bl = cur.fetchall()
    return render_template("admin.html", username=user['username']+'#'+user['discriminator'], blacklist=bl)


def query_workaround(query, *args):
    """ query = "SELECT %s FROM $1"
    Args must contain the relevant names."""
    tot = re.findall(r"\$(\d+)", query)
    for i in range(len(tot)):
        query = query.replace(f"${i+1}", f'"{args[i]}"')
    return query


@app.route("/removefromdb")
def remove_from_db():
    if fetch_user_id(session.get("oauth2_token")) not in config.ADMINS:
        abort(404)
    table = request.args.get("table")
    column = request.args.get("column")
    value = request.args.get("value")
    with g.db.cursor() as cur:
        query = query_workaround("DELETE FROM $1 WHERE $2=%s", table, column)
        cur.execute(query, (value,))
    return redirect(url_for(".admin"))


app.run(host="0.0.0.0")
