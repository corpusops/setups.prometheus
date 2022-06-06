#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

import json
import random
import os
import datetime
import time
import sys
import copy
import click
from portus_export import export_tags
from prometheus_utils import (
    # noqa
    Odict,
    OrderedDict,
    filter_dict,
    setup_logging,
    prometheus_api,
    EXPORTFILE,
    DEFAULT_ROBOT_PERMISSION,
    DEFAULT_ROBOT,
    get_prometheus_data,
    get_username,
    get_prometheus_batched as get_batched,
    default,
    setup,
    create_robot,
    update_robot_secret,
    ensure_prometheus_connected,
    get_or_create_robot,
    L)


CRON_PERIODICITY = '0 0 */1 * * *'
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
REPLICATIONS = {
    'counter': {},
    'repls': {},
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
def main(**cli):
    o = Odict(cli)
    syncregname = o.syncregname
    cron = o.cron
    _ = setup(exportfile=EXPORTFILE)
    hdata = get_prometheus_data()
    current_user = ensure_prometheus_connected()  # noqa
    namespaces = OrderedDict([(a['name'], a) for a in get_batched('/projects')])
    if not namespaces:
        raise Exception('not connected')
    namespaces = OrderedDict([(a['name'], a) for a in get_batched('/projects')])
    if not namespaces:
        raise Exception('not connected')
    replications = OrderedDict([(a['name'], a) for a in get_batched('/replication/policies')])
    registries = OrderedDict([(a['name'], a) for a in get_batched('/registries')])
    registry = registries[syncregname]

    # create robots
    errors = []
    via_excludes = False
    ix = 0
    for ns, nsdata in sorted(hdata['projects'].items()):
        try:
            ns = namespaces[ns]
        except KeyError:
            errors.append(f"{ns} ns does not exists")
            continue
        for img, idata in nsdata['repos'].items():
            tags = ','.join(list(sorted(idata['tags'])))
            ftags = ','.join(list(sorted(idata['filtered'])))
            # but replication rules with filter strings limited to 400 chars
            # (current interface limit of prometheus)
            for _, tags in enumerate(get_batches(ftags if via_excludes else tags)):
                add_replication_rule(registry, ns['name'], img, tags, cron=cron,
                                     replications=replications,
                                     errors=errors, exclude=via_excludes)
                ix += 1
    if errors:
        for i in errors:
            L.error(i)
        sys.exit(1)


def add_replication_rule(registry, ns, img, tags,
                         cron=None, bandwith=None, override=True, enabled=True,
                         exclude=False, replications=None, errors=None):
    if errors is None:
        errors = []
    if replications is None:
        replications = OrderedDict([(a['name'], a)
                                    for a in get_batched('/replication/policies')])
    replname_default = img.replace('/', '-')
    ix = REPLICATIONS['counter'].setdefault(replname_default, 0)
    replname = ix == 0 and replname_default or f'{replname_default}-{ix}'
    REPLICATIONS['counter'][replname_default] += 1
    repl_data = {'src_registry': registry,
                 'name': replname,
                 'override': override,
                 'enabled': enabled,
                 'filters': [{'type': 'name', 'value': img}],
                 'dest_namespace': ns}
    if cron:
        # make default a bit random not to DDOS former registry
        # with all crons at the same time
        if cron == CRON_PERIODICITY:
            cron = cron.split()
            cron[1] = str(random.randint(0, 59))
            cron = " ".join(cron)
            L.info(f'cron is now: {cron}')

        repl_data['trigger'] = {'trigger_settings': {'cron': cron},
                                'type': 'scheduled'}
    if tags:
        repl_data['filters'].append({
            'type': 'tag', 'value': '{' + tags + '}',
            'decoration': exclude and 'excludes' or 'matches'})
    if bandwith:
        replname['speed'] = int(bandwith)
    try:
        repl = replications[replname]
    except KeyError:
        rdata = copy.deepcopy(default_repl)
        rdata.update(repl_data)
        ret = prometheus_api('/replication/policies', method='post', json=rdata, expect=201)

        repl = prometheus_api(ret.headers['Location'], force_uri=True).json()
        replications[repl['name']] = repl
        L.info(f"Added replication {repl['name']}")
    for i, v in repl_data.items():
        try:
            if not repl['enabled']:
                L.info("Skip {repl['name']} as it is not updated")
                break
        except KeyError:
            pass
        if repl.get(i) != v:
            L.info(f"Updating replication {repl['name']}")
            repl.update(repl_data)
            ret = prometheus_api(f'/replication/policies/{repl["id"]}', method='put', json=repl, expect=200)
            repl = prometheus_api(f'/replication/policies/{repl["id"]}').json()
            replications[repl['name']] = repl
            break
    if repl.get('enabled'):
        if not filter_execs(repl, status=['succeed', 'inprogress']):
            L.info(f"Starting replication {repl['name']}")
            ret = prometheus_api("/replication/executions", method='post',
                             json={'policy_id': repl['id']}, expect=201)
        else:
            L.info(f"Replication {repl['name']} is in place")
        wait_repl_finished(repl)
    REPLICATIONS['repls'][repl['id']] = repl


def filter_execs(repl, status=None):
    if not status:
        status = []
    if not isinstance(status, (list, tuple, set)):
        status = list(status)
    status = [a.lower() for a in status]
    candidates = [a for a in replication_execs(repl)
                  if not status or a['status'].lower() in status]
    return candidates


class Timeout(Exception):
    """."""


def wait_repl_finished(repl, timeout=60 * 60 * 24):
    dt = datetime.datetime.now()
    i = 0
    while True:
        ndt = datetime.datetime.now()
        if (ndt - dt).total_seconds() > timeout:
            raise Timeout(
                f'Timeout({timeout}s) while waiting '
                f'for replication {repl["name"]} to finish'
            )
        try:
            filter_execs(repl, status=['inprogress', 'pending'])[0]
        except IndexError:
            break
        if i % 10 == 0:
            L.info(f'Waiting for replication {repl["name"]} to finish')
        time.sleep(1)
        i += 1


def replication_execs(repl):
    repl_id = repl
    if isinstance(repl, dict):
        repl_id = repl['id']
    execs = [a for a in get_batched('/replication/executions',
                                    params={'policy_id': repl_id})]
    return execs


if __name__ == "__main__":
    main()

# vim:set et sts=4 ts=4 tw=120:
