#!/usr/bin/env python
# -*- coding: utf-8 -*
from __future__ import absolute_import, division, print_function

import copy
from collections import OrderedDict
import requests
from prometheus_utils import (
    # noqa
    filter_dict,
    prometheus_api,
    EXPORTFILE,
    DEFAULT_ACCESS,
    DEFAULT_ROBOT_PERMISSION,
    ROLES,
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
    sortperm,
    equivalent_permissions,
    L)


def main():
    """."""
    L.info('start')
    exportfile = EXPORTFILE
    _ = setup(exportfile=exportfile)
    current_user = ensure_prometheus_connected()  # noqa
    users = OrderedDict([(a['username'], a) for a in get_batched('/users')])
    namespaces = OrderedDict([(a['name'], a) for a in get_batched('/projects')])
    hdata = get_prometheus_data()
    husers = hdata['users']
    if not namespaces:
        raise Exception('not connected')

    # link users to projects
    for ns, nsdata in hdata['projects'].items():
        pmembers = nsdata["members"]
        project = namespaces[ns]
        members = get_batched(f'/projects/{project["project_id"]}/members')
        memberperms = dict([(a['entity_name'], {'role': a['role_id'],
                                                'perm': a}) for a in members])
        for huser in pmembers:
            udata = husers[huser]
            try:
                _ = users[huser]
            except KeyError:
                L.info(f'{huser} does not exist, skipping')
                continue
            role_id = udata.get('portus_bot', udata.get('bot', False)) and 4 or 1
            role_n = ROLES[role_id]
            try:
                curperm = memberperms[huser]
            except KeyError:
                L.info(f'Adding {huser} as {role_n} to {ns}')
                prometheus_api(
                    f'/projects/{project["project_id"]}/members',
                    method='post', json={
                        'role_id': role_id, 'member_user': {'username': huser}
                    }, expect=201)
            else:
                if curperm['role'] != role_id:
                    L.info(f'Editing {huser} as {role_n} for {ns}')
                    prometheus_api(
                        f'/projects/{project["project_id"]}/members/{curperm["perm"]["id"]}',
                        method='put', json={'role_id': role_id}, expect=200)
                else:
                    L.info(f'Nothing to do: {huser} already {role_n} for {ns}')
    L.info('end')


if __name__ == '__main__':
    main()
# vim:set et sts=4 ts=4 tw=120:
