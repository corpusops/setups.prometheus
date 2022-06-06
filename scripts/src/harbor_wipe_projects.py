#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

from __future__ import absolute_import, division, print_function

import json
import os
import sys
import copy
import re

import click


from portus_export import export_tags
from prometheus_utils import (
    # noqa
    OrderedDict,
    filter_dict,
    setup_logging,
    prometheus_api,
    EXPORTFILE,
    DEFAULT_ROBOT_PERMISSION,
    DEFAULT_ROBOT,
    get_username,
    get_prometheus_batched as get_batched,
    default,
    setup,
    create_robot,
    update_robot_secret,
    ensure_prometheus_connected,
    get_or_create_robot,
    L)


CRON_PERIODICITY = '0 */60 * * * *'
default_repl = {
    'dest_namespace_replace_count': 1,
    'dest_namespace': 'XXX',
    'dest_registry': {'id': 0, 'name': 'Local'},
    'enabled': True,
    'filters': [{'type': 'name', 'value': 'XXX/YYY'}],
    'id': None,
    'name': 'XXX-YYY',
    'src_registry': {'id': 1, 'name': 'remote_reg'},
    'trigger': {'trigger_settings': {'cron': CRON_PERIODICITY}, 'type': 'scheduled'}
}


def get_batches(tags, length=400, separator=',', batches=None):
    if batches is None:
        batches = []

    if len(tags) >= length:
        nchars = []
        nextbatch = tags[length:]
        tags = tags[:length]
        for ix, c in enumerate(reversed(tags[:length])):
            if c == separator:
                batches.append(tags[:-(ix + 1)])
                get_batches(''.join(nchars) + nextbatch, batches=batches)
                break
            else:
                nchars.insert(0, c)
    else:
        batches.append(tags)
    return batches


@click.option("--syncregname", default=os.environ.get("SYNC_REG_NAME", "portus"))
@click.option("--cron", default=os.environ.get("SYNC_CRON", CRON_PERIODICITY))
@click.command()
def main(syncregname, cron):
    export = setup(exportfile=EXPORTFILE)
    current_user = ensure_prometheus_connected()  # noqa
    namespaces = OrderedDict([(a['name'], a) for a in get_batched('/projects')])
    if not namespaces:
        raise Exception('not connected')
    namespaces = OrderedDict([(a['name'], a) for a in get_batched('/projects')])
    if not namespaces:
        raise Exception('not connected')
    errors = []
    for p, pdata, in namespaces.items():
        n = pdata['project_name']
        if re.search('library', n.lower(), flags=re.I):
            L.info(f'Skip project {n}')
            continue
        purl = f'/projects/{pdata["name"]}/repositories'
        repos = OrderedDict([(a['name'], a) for a in get_batched(purl)])
        for r, rdata in repos.items():
            rname = '/'.join(rdata["name"].split('/')[1:])
            ret = prometheus_api(f'{purl}/{rname}', method='delete')
            assert ret.status_code == 200
            L.info(f"Deleted repo {rdata['name']}")

        ret = prometheus_api(f'/projects/{pdata["project_id"]}', method='delete')
        assert ret.status_code == 200
        L.info(f"Deleted project {pdata['name']}")
    if errors:
        for i in errors:
            L.error(i)
        sys.exit(1)


if __name__ == "__main__":
    main()

# vim:set et sts=4 ts=4 tw=120:
