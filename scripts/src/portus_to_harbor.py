#!/usr/bin/env python
# -*- coding: utf-8 -*
from __future__ import absolute_import, division, print_function

import copy
from collections import OrderedDict
import requests
from prometheus_utils import (
    # noqa
    filter_dict,
    write_prometheus_data,
    prometheus_api,
    gen_pw,
    EXPORTFILE,
    DEFAULT_ROBOT_PERMISSION,
    PORTUS_TAGS_FILTER,
    PORTUS_TAGS_WHITELIST,
    DEFAULT_ROBOT,
    get_username,
    get_prometheus_batched as get_batched,
    default,
    setup,
    create_robot,
    get_prometheus_data,
    update_robot_secret,
    ensure_prometheus_connected,
    get_or_patch_user,
    L)


def main():
    """."""
    L.info('start')
    exportfile = EXPORTFILE
    export = setup(exportfile=exportfile)
    hdata = get_prometheus_data()
    hns = hdata.setdefault('projects', {})
    husers = hdata.setdefault('users', {})
    pnames = export.setdefault('portusnames', {})
    # export portus users infos to prometheus users
    for u, udata in export['users'].items():
        hn = udata["prometheusname"]
        hu = husers.setdefault(hn, {})
        try:
            pw = export["tokens"][u]
        except KeyError:
            pw = gen_pw()
        udata["password"] = pw
        for i in 'password', :
            try:
                hu[i] = udata[i]
            except KeyError:
                continue
        for i in 'email', 'password', 'portus_bot':
            try:
                hu.setdefault(i, udata[i])
            except KeyError:
                continue
    # export portus repos to prometheus projets
    for ns, ndata in export['namespaces'].items():
        # filter out imported namespaces without any tags
        nstags = list(sorted([
            a for a in export['images']
            if (export['images'][a]['namespace'] == ns and
                len(export['images'][a]['tags']))
        ]))
        if not nstags:
            continue
        d = hns.setdefault(ns, {})
        d.update(copy.deepcopy(ndata))
        tags = d.setdefault('repos', {})
        for t in nstags:
            repo = tags.setdefault(t, {})
            filtered = repo.setdefault('filtered', [])
            rtags = repo['raw_tags'] = export['images'][t]["tags"][:]
            _ = [filtered.append(a) for a in repo['raw_tags']
                 if (a not in filtered) and PORTUS_TAGS_FILTER.search(f'{repo}:{a}')]

            repo['tags'] = [a for a in rtags if (a not in filtered)]
        members = d.setdefault("members", [])
        for g in d["groups"]:
            for m in export["groups"][g]['members']:
                pm = pnames.get(m, m)
                if pm not in members:
                    members.append(pm)
        if not members:
            if 'personal' in d['description']:
                members = d['name']
        for i in ['id', 'description', 'name', 'groups', 'tags']:
            d.pop(i, None)
    write_prometheus_data(hdata)
    L.info('end')


if __name__ == '__main__':
    main()

# vim:set et sts=4 ts=4 tw=120:
