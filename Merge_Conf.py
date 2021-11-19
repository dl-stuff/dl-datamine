import argparse
import os
import json
import pprint
import shutil
import subprocess
from exporter.conf.common import fmt_conf

SIM = "../dl/conf"
GEN = "./out/gen"
TIMING = {"startup", "recovery", "charge", "interrupt", "cancel"}
DO_NOT_MERGE = {
    "adv": {"a", "attr"},
    "drg": {"a", "attr"},
    "wep": {"a"},
}
FMT_LIM = {"drg": 3, "wep": 4}


def get_gitdiff():
    os.chdir("out")
    result = subprocess.check_output(["git", "diff", "--name-only", "gen"])
    result = {os.path.abspath(p.decode("utf-8")) for p in result.split(b"\n")}
    os.chdir("..")
    return result


def merge_attrs(simattr, genattr):
    # for sattr, gattr in zip(simattr, genattr):
    #     if not isinstance(sattr, dict) or not isinstance(gattr, dict):
    #         continue
    #     sattr.update(gattr)
    # if len(genattr) > len(simattr):
    #     simattr.extend(genattr[len(simattr) :])
    for attr in genattr:
        if isinstance(attr, dict):
            for k, v in attr.copy().items():
                if k.startswith("DEBUG"):
                    del attr[k]
    return genattr


def merge_subconf(simconf, genconf, kind=None, mapdict=None):
    if not genconf:
        return
    no_merge = DO_NOT_MERGE.get(kind, set())
    for key, value in genconf.items():
        if key.startswith("DEBUG") or key in no_merge:
            continue
        skey = convert_map(key, mapdict)
        if isinstance(value, dict):
            if skey in TIMING:
                simconf[skey] = {}
            if skey in simconf:
                merge_subconf(simconf[skey], genconf[key], kind=kind, mapdict=mapdict)
        elif isinstance(value, list) and key.startswith("attr"):
            if not key in simconf:
                simconf[skey] = value
            else:
                simconf[skey] = merge_attrs(simconf[skey], genconf[key])
        else:
            if key in TIMING and (value is None or value < 0):
                continue
            simconf[skey] = value


def merge_conf_recurse(simconf, genconf, kind, mapdict, depth):
    no_merge = DO_NOT_MERGE.get(kind, set())
    if depth > 0:
        add_to_simconf = {}
        for key, subconf in genconf.items():
            if key in no_merge:
                continue
            try:
                merge_conf_recurse(simconf[key], subconf, kind, mapdict, depth - 1)
            except KeyError:
                add_to_simconf[key] = subconf
        simconf.update(add_to_simconf)
    else:
        for key, subconf in genconf.items():
            if key in no_merge:
                continue
            skey = convert_map(key, mapdict)
            if skey in simconf:
                merge_subconf(simconf[skey], subconf, kind, mapdict)


def merge_conf(name, kind, diff=None):
    mapdict = None
    if kind:
        target = f"{kind}/{name}.json"
    else:
        target = f"{name}.json"
        sim_path = os.path.join(SIM, target)
        gen_path = os.path.join(GEN, target)
        shutil.copy(gen_path, sim_path)
        return
    depth = FMT_LIM.get(kind, 2)
    sim_path = os.path.join(SIM, target)
    gen_path = os.path.join(GEN, target)

    if diff and os.path.abspath(gen_path) not in diff:
        return

    if not os.path.exists(sim_path):
        return shutil.copy(gen_path, sim_path)
    with open(sim_path) as fn:
        simconf = json.load(fn)
        try:
            # only support adv for now
            mapdict = simconf["c"]["suffixmap"]
        except KeyError:
            pass
    with open(gen_path) as fn:
        genconf = json.load(fn)
    merge_conf_recurse(simconf, genconf, kind, mapdict, depth - 2)
    # print("merge", sim_path)
    with open(sim_path, "w") as fn:
        fmt_conf(simconf, f=fn, lim=depth)
        fn.write("\n")
    # fmt_conf(simconf, f=sys.stdout)


def convert_map(key, mapdict):
    if not mapdict:
        return key
    try:
        pre, suf = key.split("_", 1)
        if gsuf := mapdict.get(suf):
            return f"{pre}_{gsuf}"
    except ValueError:
        pass
    return key


def merge_kind_conf(kind, diff=None):
    for _, _, files in os.walk(os.path.join(GEN, kind)):
        for fn in files:
            name, ext = os.path.splitext(fn)
            if ext != ".json":
                continue
            merge_conf(name, kind, diff=diff)


def merge_all_conf():
    for root, _, files in os.walk(GEN):
        if root == GEN:
            continue
        kind = root.replace(GEN, "").strip("\\/")
        for fn in files:
            name, ext = os.path.splitext(fn)
            if ext != ".json":
                continue
            merge_conf(name, kind)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Merge conf to sim directory")
    parser.add_argument("-name", type=str, help="target merge", default=None)
    parser.add_argument("-kind", type=str, help="target kind (adv/drg/wep/base)")
    parser.add_argument("-fmt", type=str, help="format a conf file")
    parser.add_argument("--all", action="store_true", help="run everything")
    parser.add_argument("--diff", action="store_true", help="run diff only")
    args = parser.parse_args()
    if args.all:
        merge_all_conf()
    elif args.fmt:
        with open(args.fmt, "r") as fn:
            data = json.load(fn)
        for k, v in data.items():
            data[k] = dict(sorted(v.items()))
        with open(args.fmt, "w") as fn:
            fmt_conf(data, f=fn, lim=3)
            fn.write("\n")
    else:
        diff = None
        if args.diff:
            diff = get_gitdiff()
        if args.name:
            merge_conf(args.name, args.kind, diff=diff)
        elif args.kind:
            merge_kind_conf(args.kind, diff=diff)
