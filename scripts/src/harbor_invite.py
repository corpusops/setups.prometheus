#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

import json
import os
import secrets

import click

from prometheus_utils import (
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
@click.option("--only", default=os.environ.get("ONLY_USERS", ""))
@click.option("--force-password", default=os.environ.get("FORCE_PASSWORD", ""))
@click.option("--mail-lang", default=MAIL_LANG)
@click.option("--tls", default=os.environ.get("SMTP_TLS", "1"))
@click.option("--dry-run", default=default_dry_run)
@click.option("--mail-server", default=os.environ.get("SMTP_HOST", "localhost"))
@click.option("--mail-port", default=os.environ.get("SMTP_PORT", "25"))
@click.option("--mail-login", default=os.environ.get("SMTP_USERNAME", ""))
@click.option("--mail-from", default=os.environ.get("SMTP_FROM", ""))
@click.option("--mail-pw", default=os.environ.get("SMTP_PASSWORD", ""))
@click.option("--notify", default=os.environ.get("SMTP_NOTIFY", "1"))
@click.option("--user-sysadmin", default=os.environ.get("USER_SYSADMIN", ""))
def main(**cli):
    L.info("start")
    o = Odict(cli)
    setup_logging()
    hdata = get_prometheus_data()
    husers = hdata["users"]
    for username, udata in husers.items():
        if o.notify:
            unotify = not udata.get('portus_bot', False)
        if udata.get("ldap"):
            continue
        if o.only:
            if username not in o.only:
                L.info(f'Skip {username} managment')
                continue
        L.info(f'Updating: {username} / {udata["email"]}')
        user = get_or_patch_user(
            user_or_username=username,
            password=udata.get('password', None),
            force_password=as_bool(o.force_password),
            udata=udata,
            notify=unotify,
            mail_lang=o.mail_lang,
            sysadmin=as_bool(o.user_sysadmin),
            tls=o.tls,
            dry_run=o.dry_run,
            mail_server=o.mail_server,
            mail_port=o.mail_port,
            mail_login=o.mail_login,
            mail_from=o.mail_from,
            mail_pw=o.mail_pw)
        L.info(f'Created or updated {user["username"]} / {user["email"]}')
    L.info("end")


if __name__ == "__main__":
    main()

# vim:set et sts=4 ts=4 tw=120:
