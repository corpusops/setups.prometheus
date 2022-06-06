#!/usr/bin/env python
# -*- coding: utf-8 -*
from __future__ import absolute_import, division, print_function

import importlib
import os
from prometheus_utils import (
    # noqa
    setup,
    save,
    EXPORTFILE,
    get_prometheus_data,
    write_prometheus_data,
    L)


def main():
    """."""
    L.info('start')
    exportfile = EXPORTFILE
    hdata = get_prometheus_data()
    _ = setup(exportfile=exportfile)
    # activate to sync back prometheus to portus data
    # done = 0
    # for u, ud in hdata['users'].items():
    #     try:
    #         pw = ud['password']
    #         _['tokens'][u] = pw
    #         done += 1
    #     except KeyError:
    #         continue
    # save(_)
    os.environ['SMTP_NOTIFY'] = '0'
    os.environ['DRYRUN'] = '1'
    steps = [
        'portus_export',
        'portus_to_prometheus',
        'prometheus_ldap_invite',
        'prometheus_invite',
    ]
    steps += [
        'prometheus_import_projects',
        'prometheus_link',
        'prometheus_create_replications',
    ]
    for i in steps:
        if os.environ.get(f'SKIP_{i}'.upper(), '0') == '1':
            L.info(f'Skip {i}')
            continue
        L.info(f'Running {i}')
        mod = importlib.import_module(i)
        mod.main()


if __name__ == '__main__':
    main()

# vim:set et sts=4 ts=4 tw=120:
