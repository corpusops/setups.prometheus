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
    Odict,
    as_bool,
    setup_logging,
    get_or_patch_user,
    get_prometheus_data,
    default_dry_run,
)


@click.command()
@click.option("--username")
@click.option("--email")
@click.option("--mail-lang", default=MAIL_LANG)
@click.option("--tls", default=os.environ.get("SMTP_TLS", "1"))
@click.option("--dry-run", default=default_dry_run)
@click.option("--mail-server", default=os.environ.get("SMTP_HOST", "localhost"))
@click.option("--mail-port", default=os.environ.get("SMTP_PORT", "25"))
@click.option("--mail-login", default=os.environ.get("SMTP_USERNAME", ""))
@click.option("--mail-from", default=os.environ.get("SMTP_FROM", ""))
@click.option("--mail-pw", default=os.environ.get("SMTP_PASSWORD", ""))
@click.option("--notify", default=os.environ.get("SMTP_NOTIFY", "1"))
@click.option("--force-password", default=os.environ.get("FORCE_PASSWORD", ""))
@click.option("--user-sysadmin", default=os.environ.get("USER_SYSADMIN", ""))
def main(**cli):
    o = Odict(cli)
    return get_or_patch_user(
        username=o.username,
        email=o.email,
        mail_lang=o.mail_lang,
        force_password=o.force_password,
        sysadmin=as_bool(o.user_sysadmin),
        tls=o.tls,
        dry_run=o.dry_run,
        mail_server=o.mail_server,
        mail_port=o.mail_port,
        mail_login=o.mail_login,
        mail_from=o.mail_from,
        mail_pw=o.mail_pw,
        notify=o.notify)


if __name__ == "__main__":
    main()

# vim:set et sts=4 ts=4 tw=120:
