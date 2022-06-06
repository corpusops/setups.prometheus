#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

import json
import os
import secrets

import click

import ldap3
from prometheus_utils import (
    write_prometheus_data,
    _default,
    ldap_connect,
    Odict,
    MAIL_LANG,
    L,
    as_bool,
    setup_logging,
    notify_access,
    get_or_patch_user,
    get_prometheus_data,
    default_dry_run,
)


@click.command()
@click.option("--mail-lang", default=MAIL_LANG)
@click.option("--tls", default=os.environ.get("SMTP_TLS", "1"))
@click.option("--only", default=os.environ.get("ONLY_USERS", ""))
@click.option("--force-password", default=os.environ.get("FORCE_PASSWORD", ""))
@click.option("--dry-run", default=default_dry_run)
@click.option("--mail-server", default=os.environ.get("SMTP_HOST", "localhost"))
@click.option("--mail-port", default=os.environ.get("SMTP_PORT", "25"))
@click.option("--mail-login", default=os.environ.get("SMTP_USERNAME", ""))
@click.option("--mail-from", default=os.environ.get("SMTP_FROM", ""))
@click.option("--mail-pw", default=os.environ.get("SMTP_PASSWORD", ""))
@click.option("--notify", default=os.environ.get("SMTP_NOTIFY", "1"))
@click.option("--ldap-bind_dn", default=os.environ.get("LDAP_BIND_DN", ""))
@click.option("--ldap-base_dn", default=os.environ.get("LDAP_BASE_DN", ""))
@click.option("--ldap-password", default=os.environ.get("LDAP_PASSWORD", ""))
@click.option("--ldap-uri", default=os.environ.get("LDAP_URI", ""))
@click.option("--ldap-filter", default=os.environ.get("LDAP_FILTER", ""))
@click.option("--ldap-uid-attr", default=os.environ.get("LDAP_UID_ATTR", "uid"))
@click.option("--ldap-email-attr", default=os.environ.get("LDAP_EMAIL_ATTR", "mail"))
@click.option("--ldap-sysadmin", default=os.environ.get("LDAP_SYSADMIN", ""))
@click.option("--user-sysadmin", default=os.environ.get("USER_SYSADMIN", ""))
def main(**cli):
    o = Odict(cli)
    o.only = [a.strip() for a in o.only.split()]
    o.ldap_sysadmin = [a.strip() for a in o.ldap_sysadmin.split()]
    o.tls = as_bool(o.tls)
    setup_logging()
    hdata = get_prometheus_data()
    husers = hdata["users"]
    conn, _ = ldap_connect(o)
    status, result, response, _ = conn.search(
        o.ldap_base_dn, o.ldap_filter,
        attributes=[ldap3.ALL_ATTRIBUTES, ldap3.ALL_OPERATIONAL_ATTRIBUTES])
    L.info("start")
    if o.user_sysadmin == '':
        o.user_sysadmin = None
    else:
        o.user_sysadmin = as_bool(o.user_sysadmin)
    for pudata in response:
        attrs = pudata['attributes']
        username = attrs[o.ldap_uid_attr][0]
        if o.only:
            if username not in o.only:
                L.info(f'Skip {username} managment')
                continue
        udata = {'username': username,
                 'ldap': True,
                 'realname': attrs['cn'][0],
                 'email': attrs[o.ldap_email_attr][0]}
        huser = husers.get(username, {})
        sysadmin = o.user_sysadmin
        val = huser.get('password', _default)
        if val is not _default:
            udata['password'] = val
        if o.ldap_sysadmin and sysadmin is None:
            for g in attrs['memberof']:
                if g in o.ldap_sysadmin:
                    sysadmin = True
                    break
        if sysadmin is None:
            sysadmin = huser.get('sysadmin', None)
        L.info(f'Created or updated {username}')
        user = get_or_patch_user(
            udata,
            force_password=as_bool(o.force_password),
            notify=o.notify,
            mail_lang=o.mail_lang,
            sysadmin=sysadmin,
            tls=o.tls,
            dry_run=o.dry_run,
            mail_server=o.mail_server,
            mail_port=o.mail_port,
            mail_login=o.mail_login,
            mail_from=o.mail_from,
            mail_pw=o.mail_pw)
        L.info(f'Created or updated {user["username"]} / {user["email"]}')


if __name__ == "__main__":
    main()

# vim:set et sts=4 ts=4 tw=120:
