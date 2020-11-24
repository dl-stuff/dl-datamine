import argparse
import sys
import os
import json
import shutil
from itertools import zip_longest
from exporter.AdvConf import fmt_conf

SIM = '../dl/conf'
GEN = './out/gen'
TIMING = {'startup', 'recovery', 'charge'}
DO_NOT_MERGE = {
    # 'adv': {'interrupt', 'cancel'},
    'drg': {'startup', 'recovery'},
}
FMT_LIM = {
    'drg': 3,
    'wep': 4,
    None: 1
}


def merge_subconf(simconf, genconf, kind=None):
    no_merge = DO_NOT_MERGE.get(kind, set())
    for key, value in genconf.items():
        if key.startswith('DEBUG') or key in no_merge:
            continue
        if isinstance(value, dict) and key in simconf:
            simconf[key].update(value)
        else:
            if key in TIMING and (value is None or value < 0):
                continue
            simconf[key] = value


def merge_conf_recurse(simconf, genconf, kind, mapdict, depth):
    if depth > 0:
        add_to_simconf = {}
        for key, subconf in genconf.items():
            try:
                merge_conf_recurse(simconf[key], subconf, kind, mapdict, depth-1)
            except KeyError:
                add_to_simconf[key] = subconf
        simconf.update(add_to_simconf)
    else:
        for key, subconf in simconf.items():
            gkey = key
            if mapdict:
                try:
                    pre, suf = key.split('_')
                except ValueError:
                    pre, suf = key, None
                if (gsuf := mapdict.get(suf)):
                    gkey = f'{pre}_{gsuf}'
            if gkey in genconf and genconf[gkey] != subconf:
                merge_subconf(subconf, genconf[gkey], kind)


def merge_conf(name, kind, maplist=None):
    mapdict = {}
    if maplist:
        mapdict = convert_map(maplist)
    if kind:
        target = f'{kind}/{name}.json'
    else:
        target = f'{name}.json'
    depth = FMT_LIM.get(kind, 2)
    sim_path = os.path.join(SIM, target)
    gen_path = os.path.join(GEN, target)
    if not os.path.exists(sim_path):
        return shutil.copy(gen_path, sim_path)
    with open(sim_path) as fn:
        simconf = json.load(fn)
    with open(gen_path) as fn:
        genconf = json.load(fn)
    merge_conf_recurse(simconf, genconf, kind, mapdict, depth-2)
    with open(sim_path, 'w') as fn:
        fmt_conf(simconf, f=fn, lim=depth)
    # fmt_conf(simconf, f=sys.stdout)


def merge_all_conf():
    for root, _, files in os.walk(GEN):
        kind = None
        if root != GEN:
            kind = os.path.basename(root)
        for fn in files:
            name, ext = os.path.splitext(fn)
            if ext != '.json':
                continue
            merge_conf(name, kind)


def convert_map(maplist):
    mapdict = {}
    for pair in maplist:
        try:
            a, b = pair.split(':')
        except ValueError:
            a, b = None, pair
        mapdict[a] = b
    return mapdict

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Merge conf to sim directory')
    parser.add_argument('-name', type=str, help='target merge', default=None)
    parser.add_argument('-kind', type=str, help='target kind (adv/drg/wep/base)')
    parser.add_argument('-map', type=str, nargs='*', help='suffix map')
    args = parser.parse_args()
    if args.name:
        merge_conf(args.name, args.kind, args.map)
    else:
        merge_all_conf()
