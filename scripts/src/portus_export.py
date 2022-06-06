#!/usr/bin/env python
# -*- coding: utf-8 -*
from __future__ import absolute_import, division, print_function

from prometheus_utils import (
    # noqa
    re,
    os,
    filter_dict,
    EXPORTFILE,
    PORTUS_TAGS_WHITELIST,
    PORTUS_TAGS_FILTER,
    setup,
    save,
    get_username,
    portus_api as api,
    L)


def export_structure(export, exportfile):
    UMAP = export.setdefault('usermap', {})
    PUSERS = export.setdefault('portusnames', {})
    USERS = export.setdefault('users', {})
    NAMESPACES = export.setdefault('namespaces', {})
    TOKENS = export.setdefault('tokens', {})
    GROUPS = export.setdefault('groups', {})
    ret = api('/users')
    try:
        ret.json()
    except:
        import pdb;pdb.set_trace()  ## Breakpoint ##

    for item in sorted(ret.json(), key=lambda x: x['username'].lower()):
        # treat portus users as real users
        if (item['id'] in [1]):
            L.info(f'Skip {item["username"]}')
            continue
        item = filter_dict(item, ['id', 'username', 'email', 'admin', 'bot'])
        if item['bot']:
            item['portus_bot'] = True
            item['bot'] = False
        n = get_username(item)
        item['prometheusname'] = UMAP.get(n, n)
        item['namespaces'] = []
        item.setdefault('groups', [])
        PUSERS[item['username']] = item['prometheusname']
        USERS[item['prometheusname']] = item
        L.info(f"Export USER: {item['prometheusname']}")
        if item['bot']:
            try:
                token = TOKENS[item["prometheusname"]]
            except KeyError:
                rtokens = api(f'/users/{item["id"]}/application_tokens').json()
                tokens = dict([(a["application"], a) for a in rtokens])
                for i in range(1000):
                    try:
                        _ = tokens[f'portusmigration{i}']
                    except KeyError:
                        break
                rtoken = api(f'/users/{item["id"]}/application_tokens', method='post',
                             json={'application': f'portusmigration{i}'}).json()
                token = rtoken["plain_token"]
            TOKENS[item["prometheusname"]] = item["token"] = token
            save(export, exportfile)
    ret = api('/namespaces')
    for ns in sorted(ret.json(), key=lambda x: x['name'].lower()):
        if ns['id'] in [1]:
            continue
        ns = filter_dict(ns, ['id', 'name', 'description'])
        L.info(f"Export NS: {ns['name']}")
        NAMESPACES[ns['name']] = ns
        ns.setdefault('groups', [])
    ret = api('/teams').json()
    for team in sorted(ret, key=lambda x: x['name'].lower()):
        team = filter_dict(team, ['id', 'name', 'description'])
        tn = team['name']
        L.info(f"Export team: {team['name']}")
        if team['id'] in [1]:
            continue
        namespaces = list(
            filter(
                lambda x: x['id'] not in [1],
                api(f'/teams/{team["id"]}/namespaces').json()))
        members = list(
            filter(
                lambda x: x['id'] not in [1],
                api(f'/teams/{team["id"]}/members').json()))
        group = GROUPS.setdefault(tn, team)
        group['members'] = [a['username'] for a in members]
        group['users'] = [PUSERS[a['username']] for a in members]
        group['namespaces'] = [a['name'] for a in namespaces]
        for ns in group['namespaces']:
            if tn not in NAMESPACES[ns]['groups']:
                NAMESPACES[ns]['groups'].append(tn)
        for user in group['users']:
            if tn not in USERS[user]['groups']:
                USERS[user]['groups'].append(tn)
            for ns in group['namespaces']:
                USERS[user]['namespaces'].append(ns)
    # complete groups
    save(export, exportfile)
    return export


def is_filtered(x, repo):
    return True
    # img = f"{repo}:{x}"
    # ret = None
    # moved to portus_to_prometheus.py
    # for matcher, testmatch in (
    #     (PORTUS_TAGS_WHITELIST, True),
    #     (PORTUS_TAGS_FILTER, False),
    # ):
    #     m = matcher.search(img)
    #     if m:
    #         ret = testmatch
    #         break
    # if ret is False:
    #     L.debug(f'{img} was filtered out')
    # return ret is None and True or ret


def export_tags(export, exportfile):
    images = export.setdefault("images", {})
    images = export['images'] = {}
    PUSERS = export.setdefault('portusnames', {})
    repos = api('/repositories').json()
    for repo in sorted(repos, key=lambda x: x['full_name'].lower()):
        tags = list(sorted([
            a["name"]
            for a in filter(
                lambda x: is_filtered(x['name'], repo['full_name']),
                api(f'/repositories/{repo["id"]}/tags').json(),
            )
        ]))
        repo = filter_dict(repo, ['name', 'full_name', 'namespace'])
        repo['namespace_id'] = repo['namespace'].pop('id')
        ns = repo['namespace'] = repo['namespace']['name']
        nsdata = export['namespaces'][ns]
        img = f'{repo["full_name"]}'
        L.info(f"Exported image: {img}")
        nsdesc = nsdata.get('description', '')
        if not export['namespaces'][ns]['groups'] and ('personal namespace' in nsdesc):
            personalns = ns
            export['namespaces'][ns]['groups'].append(personalns)
            export['groups'][personalns] = {
                'description': nsdesc, 'id': -1, 'members': [ns], 'users': [PUSERS[ns]],
                'name': personalns, 'namespaces': [personalns]}
        repo["tags"] = tags
        images[img] = repo
    save(export, exportfile)
    return export


def main():
    """."""
    L.info('start')
    exportfile = EXPORTFILE
    export = setup(exportfile=exportfile)
    export = export_structure(export, exportfile)
    export = export_tags(export, exportfile)
    save(export, exportfile)
    L.info('end')


if __name__ == '__main__':
    main()

# vim:set et sts=4 ts=4 tw=120:
