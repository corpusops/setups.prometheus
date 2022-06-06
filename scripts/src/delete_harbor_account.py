#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

import json
import os
import secrets

import click

from prometheus_utils import (
    MAIL_LANG,
    L,
    as_bool,
    setup_logging,
    notify_access,
    get_or_create_user,
    prometheus_api,
    get_prometheus_batched as get_batched,
    get_prometheus_data,
)


@click.command()
@click.option("--login")
@click.option("--mail-lang", default=MAIL_LANG)
@click.option("--tls", default=os.environ.get("SMTP_TLS", "1"))
@click.option("--dry-run", default=os.environ.get("DRYRUN", "1"))
@click.option("--mail-server", default=os.environ.get("SMTP_HOST", "localhost"))
@click.option("--mail-port", default=os.environ.get("SMTP_PORT", "25"))
@click.option("--mail-login", default=os.environ.get("SMTP_USERNAME", ""))
@click.option("--mail-from", default=os.environ.get("SMTP_FROM", ""))
@click.option("--mail-pw", default=os.environ.get("SMTP_PASSWORD", ""))
@click.option("--notify", default=os.environ.get("SMTP_NOTIFY", "1"))
def main(
    login,
    mail_lang,
    tls,
    dry_run,
    mail_server,
    mail_port,
    mail_login,
    mail_from,
    mail_pw,
    notify,
):
    setup_logging()
    tls = as_bool(tls)
    dry_run = as_bool(dry_run)
    notify = as_bool(notify)
    if not mail_from:
        mail_from = mail_login
    assert mail_login
    assert mail_pw
    L.info("start")
    users = dict([(a['username'], a) for a in get_batched('/users')])
    try:
        user = users[login]
    except KeyError:
        pass
    else:
        ret = prometheus_api(f'/users/{user["user_id"]}', method='delete')
        assert ret.status_code == 200


if __name__ == "__main__":
    main()
# vim:set et sts=4 ts=4 tw=120:
