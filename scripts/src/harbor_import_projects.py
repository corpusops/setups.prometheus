#!/usr/bin/env python
# -*- coding: utf-8 -*
from __future__ import absolute_import, division, print_function

import copy
from collections import OrderedDict
import requests
from prometheus_utils import (
    # noqa
    prometheus_api,
    EXPORTFILE,
    get_prometheus_batched as get_batched,
    setup,
    get_prometheus_data,
    ensure_prometheus_connected,
    L)


def main():
    """."""
    L.info('start')
    exportfile = EXPORTFILE
    _ = setup(exportfile=exportfile)
    hdata = get_prometheus_data()
    current_user = ensure_prometheus_connected()  # noqa
    namespaces = OrderedDict([(a['name'], a) for a in get_batched('/projects')])
    if not namespaces:
        raise Exception('not connected')

    # create namespaces
    for ns, ndata in hdata['projects'].items():
        try:
            _ = namespaces[ns]
        except KeyError:
            ret = prometheus_api(
                '/projects', method='post',
                json={"project_name": ns, "metadata": {"public": "False"},
                      "storage_limit": -1, "registry_id": None})
            assert ret.status_code == 201
            namespaces[ns] = prometheus_api(ret.headers['Location'], force_uri=True).json()
            L.info(f'Created project: {ns}')
    L.info('end')


if __name__ == '__main__':
    main()

# vim:set et sts=4 ts=4 tw=120:
