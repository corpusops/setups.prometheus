#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

import datetime

import os
import json
from collections import OrderedDict
import requests
import logging
import copy
import secrets
import re
import time
import random
import string
import smtplib
from http.client import HTTPConnection
from email.mime.text import MIMEText
import ldap3


def as_bool(value):
    if isinstance(value, str):
        return bool(re.match("^(y|o|1|t)", value.lower()))
    else:
        return bool(value)


L = logging.getLogger(__name__)
default_dry_run = os.environ.get('PROMETHEUS_INVITE_DRYRUN',
                                 os.environ.get("DRYRUN", "1"))
DEFAULT_ACCESS = [
    {'action': 'push', 'resource': 'repository'},
    {'action': 'pull', 'resource': 'repository'},
    {'action': 'delete', 'resource': 'artifact'},
    {'action': 'read', 'resource': 'helm-chart'},
    {'action': 'create', 'resource': 'helm-chart-version'},
    {'action': 'delete', 'resource': 'helm-chart-version'},
    {'action': 'create', 'resource': 'tag'},
    {'action': 'delete', 'resource': 'tag'},
    {'action': 'create', 'resource': 'artifact-label'},
    {'action': 'create', 'resource': 'scan'}]
ZERO_ACCESS = [{'action': 'read', 'resource': 'tag'}]
ZERO_PERMISSIONS = {
    'access': ZERO_ACCESS,
    'kind': 'project',
    'namespace': "library"}
DEFAULT_ROBOT_PERMISSION = {
    'access': DEFAULT_ACCESS,
    'kind': 'project',
    'namespace': None}
DEFAULT_ROBOT = {
    'disable': False,
    'duration': -1,
    'editable': True,
    'expires_at': -1,
    'id': 5,
    'level': 'system',
    'name': 'bot__project+testrobot',
    'permissions': [],
}
PROMETHEUS_DATAFILE = os.environ.get("PROMETHEUSR_DATAFILE_JSON", "data/prometheus.json")


_default = default = object()
_vars = {}

EXPORTFILE = '/w/data/portus.json'
PORTUS_URL = os.environ.get('PORTUS_URL', '')
PORTUS_API = '/api/v1'

PROMETHEUS_URL = os.environ.get('PROMETHEUS_URL', '')
PROMETHEUS_API = '/api/v2.0'

# do not export from portugs tags that may look like a SHA8
PTAGS = 'dev|prod|staging|qa|latest|:.*[-_.]+'
PORTUS_TAGS_WHITELIST = re.compile(os.environ.get(
    'PORTUS_TAGS_WHITELIST', PTAGS), flags=re.M | re.I)
PORTUS_TAGS_FILTER = re.compile(os.environ.get(
    'PORTUS_TAGS_FILTER', ':[^-_.]{8}$'), flags=re.M | re.I)
PORTUS_TOKEN = os.environ.get('PORTUS_TOKEN', '')
PROMETHEUS_COOKIE = os.environ.get('PROMETHEUS_COOKIE', '').strip()
PROMETHEUS_USERNAME = os.environ.get('PROMETHEUS_USERNAME', '').strip()
PROMETHEUS_PASSWORD = os.environ.get('PROMETHEUS_PASSWORD', '').strip()
# if PROMETHEUS_COOKIE:
#     PROMETHEUS_COOKIE = base64.b64decode(PROMETHEUS_COOKIE).decode().strip()

LOGLEVEL = os.environ.get("LOGLEVEL", "info").upper()
MAIL_LANG = os.environ.get("MAILLANG", "fr")
REQUEST_DEBUG = as_bool(os.environ.get("REQUEST_DEBUG", ""))
MAIL_TEMPLATES = {
    "subject": {
        "en": "Your prometheus access ({server})",
        "fr": "Votre accès prometheus ({server})",
    },
    "mail": {
        "en": """\
Hi,
You can connect to {server}
    login: {username}
    password: {password}  (valid only if you didn't changed it)
Thx to reinit your password upon first connection
Thx,
Harbor team
""",
        "fr": """\
Bonjour,
Vous pouvez vous connecter à {server}
    login: {username}
    password: {password} (valide uniquement si vous ne l'avez pas changé)
Merci de réinitialiser votre mot de passe à la première connexion.
Cordialement,
Équipe prometheus
""",
    },
}
ROLES = {
    4: 'Maintainer',
    2: 'Developer',
    3: 'Guest',
    5: 'Limited Guest',
    1: 'Project Admin',
}


def filter_dict(d, filters=None):
    if filters is None:
        filters = [a for a in d]
    ret = {}
    for i in d:
        if i not in filters:
            continue
        ret[i] = d[i]
    return ret


def toggle_debug(activate=None, loglevel=None, debuglevel=logging.DEBUG, errorlevel=logging.INFO):
    if loglevel is None:
        loglevel = LOGLEVEL
    loglevel = loglevel.upper()
    if activate is None:
        activate = not _vars.get("debug")
    dl = debuglevel <= logging.DEBUG and 1 or 0
    lvl = activate and debuglevel or errorlevel
    HTTPConnection.debuglevel = dl
    for req_log in [
        logging.getLogger(lg) for lg in (
            "urllib3",
            "urllib3.connectionpool",
            "equests.packages.urllib3",
        )
    ]:
        req_log.propagate = activate
        req_log.setLevel(lvl)
    _vars["debug"] = activate
    logging.getLogger("").setLevel(loglevel)
    return activate


def setup_logging(loglevel=None):
    logging.basicConfig()
    debuglvl = REQUEST_DEBUG and logging.DEBUG or logging.INFO
    toggle_debug(True, debuglevel=debuglvl, loglevel=loglevel)


class HarborRequestError(AssertionError):
    """."""

    def __init__(self, msg=None, resp=None, *a, **kw):
        AssertionError.__init__(self, msg, *a, **kw)
        self.resp = resp


def prometheus_api(path,
               method='get',
               json=default,
               force_uri=False,
               force_url=False,
               userheaders=default,
               expect_msg=None,
               expect=None,
               *a, **kw):
    """
    to auth yourself, login in a prometheus session with your user
    and sneak the requests to /apî,
    and grab the value of cookies which must look like "_gorilla_crsf=xxx, sid=xxxx"
    export it ao $PROMETHEUS_COOKIE env var
    """
    if userheaders is default:
        userheaders = get_userheaders()
    url = (not force_url) and PROMETHEUS_URL or ''
    uri = (not force_uri) and PROMETHEUS_API or ''
    uri = url + uri + path
    if json is not default:
        kw['json'] = json
    headers = kw.setdefault('headers', {})
    if isinstance(userheaders, dict):
        _ = [headers.setdefault(h, v) for h, v, in userheaders.items()]
    if PROMETHEUS_COOKIE:
        headers.setdefault('Cookie', PROMETHEUS_COOKIE)
    else:
        kw['auth'] = (PROMETHEUS_USERNAME, PROMETHEUS_PASSWORD)
        resp = getattr(requests, method.lower())(uri, *a, **kw)
    if expect:
        if not isinstance(expect, (list, tuple, set)):
            expect = [expect]
        expect_msg = (
            expect_msg or 'Request status code({resp.status_code}) is not in {expect}\n{resp.text}'
        ).format(resp=resp, expect=expect)
        if resp.status_code not in expect:
            raise HarborRequestError(msg=expect_msg, resp=resp)
    return resp


def ensure_prometheus_connected():
    user = prometheus_api('/users/current', expect=200)
    return user.json()


def get_userheaders(userheaders=None):
    if userheaders is None:
        try:
            userheaders = _vars['userheaders']
        except KeyError:
            userheaders = _vars['userheaders'] = filter_dict(
                prometheus_api('/users/current', userheaders=None).headers,
                ['X-Harbor-Csrf-Token', 'X-Request-Id'])
    return userheaders


def portus_api(path, method='get', json=default, force_uri=False, force_url=False, *a, **kw):
    url = (not force_url) and PORTUS_URL or ''
    uri = (not force_uri) and PORTUS_API or ''
    uri = url + uri + path
    if json is not default:
        kw['json'] = json
    headers = kw.setdefault('headers', {})
    headers.setdefault('Portus-Auth', f'{PORTUS_TOKEN}')
    return getattr(requests, method.lower())(uri, *a, **kw)


def save(export, fp=EXPORTFILE):
    with open(fp, 'w') as f:
        json.dump(export, f, indent=2)


def load_portus(exportfile=EXPORTFILE):
    try:
        with open(exportfile, 'r') as f:
            export = json.load(f)
    except FileNotFoundError:
        export = {}
    return export


def get_username(item):
    un = item['username']
    if item['bot']:
        un = f'bot__{un}'
    return un


def setup(load=True, exportfile=EXPORTFILE, loglevel=None):
    export = None
    setup_logging(loglevel=None)
    if load:
        export = load_portus(exportfile)
    return export


def toggle_requests_debug(toggle=True):
    # These two lines enable debugging at httplib level (requests->urllib3->http.client)
    # You will see the REQUEST, including HEADERS and DATA, and RESPONSE with HEADERS but without DATA.
    # The only thing missing will be the response.body which is not logged.
    level = {
        True: logging.DEBUG,
        False: logging.ERROR,
    }[toggle]
    try:
        import http.client as http_client
    except ImportError:
        # Python 2
        import httplib as http_client
    http_client.HTTPConnection.debuglevel = toggle and 1 or 0
    # You must initialize logging, otherwise you'll not see debug output.
    logging.getLogger().setLevel(level)
    requests_log = logging.getLogger("requests.packages.urllib3")
    requests_log.setLevel(level)
    requests_log.propagate = True


def get_prometheus_batched(uri, olddata=None, *a, **kw):
    if olddata is None:
        uri = PROMETHEUS_API + uri
        kw['force_uri'] = True
    ret = prometheus_api(uri, *a, **kw)
    data = ret.json()
    if olddata is None:
        olddata = data
    else:
        if isinstance(data, dict):
            for i, v in data.items():
                olddata[i] = v
        elif isinstance(data, list):
            for i in data:
                olddata.append(i)
        elif isinstance(data, tuple):
            for i in data:
                olddata = olddata + data
        elif isinstance(data, set):
            for i in data:
                olddata.add(i)
        else:
            return data
        data = olddata
    try:
        for link in requests.utils.parse_header_links(ret.headers['Link']):
            if link['rel'] == 'next':
                data = get_prometheus_batched(link['url'], olddata=data, *a, **kw)
    except KeyError:
        pass
    return data


def create_robot(user, prefix='bot__', projects=None, **kw):
    projects = projects or []
    bot = copy.deepcopy(DEFAULT_ROBOT)
    bot['name'] = user.startswith(prefix) and user[len(prefix):]
    for p in projects:
        perm = p
        if not isinstance(perm, dict):
            perm = copy.deepcopy(DEFAULT_ROBOT_PERMISSION)
            perm['namespace'] = p
        bot['permissions'].append(perm)
    bot.update(**kw)
    ret = prometheus_api('/robots', method='post', json=bot, expect=201)
    robot = prometheus_api(ret.headers['Location'], force_uri=True).json()
    return robot


def update_robot_secret(robot, secret):
    if secret:
        ret = prometheus_api(
            f'/robots/{robot["id"]}', method='patch', json={'secret': secret}, expect=200)
        L.info(f'Updated secret for {robot["name"]}')


def get_or_create_robot(user, granted_namespaces=None, robots=None, namespaces=None, secret=None):
    if granted_namespaces is None:
        granted_namespaces = []
    if robots is None:
        robots = OrderedDict([(a['name'], a) for a in get_prometheus_batched('/robots')])
    if namespaces is None:
        namespaces = OrderedDict([(a['name'], a) for a in get_prometheus_batched('/projects')])
    try:
        robot = robots[user]
    except KeyError:
        projects = [a for a in granted_namespaces if a in namespaces]
        if projects:
            permissions = []
        else:
            permissions = [ZERO_PERMISSIONS.copy()]
        robot = robots[user] = create_robot(user, projects=projects, permissions=permissions)
        L.info(f'Created robot: {user}')
    if secret:
        update_robot_secret(robot, secret)
    return robot


def sortperm(perm):
    return list(sorted([f'{a["action"]}__{a["resource"]}' for a in perm]))


def equivalent_permissions(perma, permb):
    return sortperm(perma) == sortperm(permb)


def get_prometheus_data(prometheusdatafile=PROMETHEUS_DATAFILE):
    try:
        d = _vars['prometheusdata']
        assert d
    except (KeyError, AssertionError):
        pass
    if not os.path.exists(prometheusdatafile):
        write_prometheus_data({}, prometheusdatafile)
    with open(prometheusdatafile) as fic:
        d = _vars['prometheusdata'] = json.load(fic)
    return d


def write_prometheus_data(data=None, prometheusdatafile=PROMETHEUS_DATAFILE):
    if data is None:
        data = get_prometheus_data(prometheusdatafile=prometheusdatafile)
    with open(prometheusdatafile, "w") as fic:
        json.dump(data, fic, indent=2, sort_keys=True)


def gen_pw(password_length=None):
    """Default password will meet this requirement: prometheus passwords needs at least one uppercase, downcase and 1 digit"""
    password_length = password_length or 16
    password = secrets.token_hex(password_length - 3)
    password += str(random.randint(0, 9))
    password += random.choice(string.ascii_lowercase)
    password += random.choice(string.ascii_uppercase)
    return password


def configure_prometheus_user(
    user_or_username,
    email=None,
    password=None,
    prometheusdatafile=PROMETHEUS_DATAFILE,
    realname=None,
    sysadmin=None,
    hdata=None,
    password_length=None,
    udata=None,
    **kw
):
    if udata is None:
        udata = {}
    if isinstance(user_or_username, dict):
        username = user_or_username['username']
        if udata:
            user_or_username.update(udata)
        udata = user_or_username
    else:
        username = user_or_username
    if hdata is None:
        hdata = get_prometheus_data(prometheusdatafile=prometheusdatafile)
    husers = hdata["users"]
    h = husers.setdefault(username, {})
    oh = copy.deepcopy(h)
    password = password or udata.get('password', None)
    opassword = oh.get('password', '')
    if not password and not opassword:
        password = gen_pw(password_length)
    for i in 'sysadmin', 'username', 'realname', 'email', 'password':
        val = locals()[i]
        if val is not None:
            udata[i] = val
    for i in udata, kw:
        h.update(i)
    h.setdefault('realname', oh.get('realname', username))
    if True in [(oh.get(a, _default) != h[a]) for a in h]:
        write_prometheus_data(hdata)
    udata.update(h)
    _ = [udata.pop(a) for a in udata if a not in h]
    return h


def get_or_patch_user(
    user_or_username,
    email=None,
    password=None,
    sysadmin=None,
    force_password=False,
    prometheusdatafile=PROMETHEUS_DATAFILE,
    realname=None,
    tls=None,
    force_notify=False,
    dry_run=None,
    mail_lang=None,
    mail_server=None,
    mail_port=None,
    mail_login=None,
    mail_from=None,
    mail_pw=None,
    notify=None,
    udata=None,
    **kw,
):
    udata = configure_prometheus_user(
        user_or_username, email=email, realname=realname,
        password=password, prometheusdatafile=prometheusdatafile,
        sysadmin=sysadmin, udata=udata, **kw)
    username, email, password, realname = udata['username'], udata['email'], udata['password'], udata["realname"]
    users = dict([(a['username'], a) for a in get_prometheus_batched('/users')])
    try:
        user = users[username]
        if password and force_password:
            ret = prometheus_api(
                f'/users/{user["user_id"]}/password', method='put',
                json={'new_password': password},
                expect=200)
        if email or realname:
            realname = realname or username
            ret = prometheus_api(
                f'/users/{user["user_id"]}', method='put',
                json={"realname": realname,
                      "email": email},
                expect=200)
    except KeyError:
        L.info(f'Created user: {username}')
        ret = prometheus_api(
            '/users', method='post',
            json={"username": username,
                  "realname": username,
                  "email": email,
                  "password": password},
            expect=201)
        user = prometheus_api(ret.headers['Location'], force_uri=True).json()
    if udata.get('sysadmin') is not None:
        ret = prometheus_api(
            f'/users/{user["user_id"]}/sysadmin', method='put',
            json={"sysadmin_flag": sysadmin},
            expect=200)
    notify, is_notified = as_bool(notify), user.get('notified', False)
    if is_notified:
        L.info(f'{udata["username"]} was already notified')
    if notify and (force_notify or not is_notified):
        notify_access(
            udata,
            mail_lang,
            tls,
            dry_run,
            mail_server,
            mail_port,
            mail_login,
            mail_from,
            mail_pw,
        )
    return user


def notify_access(
    user,
    mail_lang,
    tls,
    dry_run,
    mail_server,
    mail_port,
    mail_login,
    mail_from,
    mail_pw,
):
    dry_run = as_bool(dry_run)
    tls = as_bool(tls)
    if not mail_from:
        mail_from = mail_login
    assert mail_login
    assert mail_pw
    subject = f"Your prometheus {PROMETHEUS_URL} access"
    username = user['username']
    email = user['email']
    infos = dict(
        server=PROMETHEUS_URL,
        username=username,
        password=user['password'],
    )
    text = MAIL_TEMPLATES["mail"][mail_lang].format(**infos)
    subject = MAIL_TEMPLATES["subject"][mail_lang].format(**infos)
    msg = MIMEText(text)
    date = datetime.datetime.now(datetime.timezone.utc).strftime("%a, %d %b %Y %H:%M:%S %z")
    msg["From"] = mail_from
    msg["To"] = email
    msg["Date"] = date
    msg["Subject"] = subject
    if dry_run:
        L.info(f"Would send {mail_from} -> {email}")
        L.info(msg.as_string())
        L.info(f"\n\n-- PLAINTEXT --:\n{text}")
    else:
        s = smtplib.SMTP(mail_server, int(mail_port))
        s.set_debuglevel(1)
        if tls:
            s.starttls()
        if mail_login:
            s.login(mail_login, mail_pw)
        s.sendmail(mail_from, [email], msg.as_string())
        s.quit()
        configure_prometheus_user(user, notified=True)
    return msg


class Odict:

    def __init__(self, o):
        self.__dict__.update(o)


def ldap_connect(o):
    for i in ['ldap_uri', 'ldap_bind_dn', 'ldap_password']:
        assert getattr(o, i, ''), f'{i} is not defined'
    server = ldap3.Server(o.ldap_uri)
    conn = ldap3.Connection(
        server, o.ldap_bind_dn, o.ldap_password, client_strategy=ldap3.SAFE_SYNC)
    if o.tls:
        conn.start_tls()
    ret = conn.bind()
    return conn, ret


def stop_execs(repl_data=None):
    if not repl_data:
        return
    if not isinstance(repl_data, dict):
        repl_data = {'id': repl_data, 'name': repl_data}
    for exe in prometheus_api(
        f'/replication/executions?policy_id={repl_data["id"]}'
    ).json():
        if exe['in_progress']:
            ret = prometheus_api(
                f'/replication/executions/{exe["id"]}', method='put',
                json=repl_data)
            assert ret.status_code == 200
            while True:
                exe = prometheus_api(f'/replication/executions/{exe["id"]}').json()
                if exe['in_progress']:
                    L.info(f'Waiting for {repl_data["name"]} {exe["id"]} to finish')
                    time.sleep(1)
                else:
                    L.info(f'{repl_data["name"]} {exe["id"]} finished')
                    break

# vim:set et sts=4 ts=4 tw=120:
