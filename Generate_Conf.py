import argparse
from pprint import pprint
from time import monotonic
from exporter.Shared import AbilityData
from loader.Database import DBViewIndex

from exporter.conf.adv import AdvConf
from exporter.conf.drg import DrgConf
from exporter.conf.wep import WepConf
from exporter.conf.wp import WpConf
from exporter.conf.fort import write_fort_passives
from exporter.conf.common import AuraConf, AbilityConf, ActCondConf, fmt_conf

import exporter.conf.common


OUT_DIR = "./out/gen"
Q_HANDLERS = {
    "adv": lambda index, q: fmt_conf(AdvConf(index).get(q, exss=True)),
    "drg": lambda index, q: fmt_conf(DrgConf(index).get(q)),
    "wep": lambda index, q: fmt_conf(WepConf(index).get(q)),
    "wp": lambda index, q: fmt_conf(WpConf(index).get(q)),
    "ab": lambda index, q: pprint(AbilityConf(index).get(q)),
    "actcond": lambda index, q: pprint(ActCondConf(index).get(q)),
}

ALL_HANDLERS = {
    "adv": lambda index: AdvConf(index).export_all_to_folder(out_dir=OUT_DIR),
    "drg": lambda index: DrgConf(index).export_all_to_folder(out_dir=OUT_DIR),
    "wep": lambda index: WepConf(index).export_all_to_folder(out_dir=OUT_DIR),
    "wp": lambda index: WpConf(index).export_all_to_folder(out_dir=OUT_DIR),
    "aura": lambda index: AuraConf(index).export_all_to_folder(out_dir=OUT_DIR),
    "fort": lambda _: write_fort_passives(OUT_DIR),
    # "actcond": lambda index: ActCondConf(index).export_all_to_folder(out_dir=OUT_DIR),
    "talisman": lambda index: AbilityConf(index).export_all_talisman_to_folder(out_dir=OUT_DIR),
}

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-k", help="type of conf ({})".format(" ".join(Q_HANDLERS.keys())))
    parser.add_argument("-q", help="query value (id or name)")
    args = parser.parse_args()
    start = monotonic()

    index = DBViewIndex()
    exporter.conf.common.ACTCOND_CONF = index["ActCondConf"]
    # index.instance_dict["ActionCondition"] = index["ActCondConf"]
    index.class_dict["PlayerActionHitAttribute"].LINK_ACTCOND = False

    if args.k:
        if args.q:
            Q_HANDLERS[args.k](index, args.q)
            # print()
            # fmt_conf(index["ActionCondition"].all_actcond_conf, lim=1)
        else:
            ALL_HANDLERS[args.k](index)
    else:
        for handle in ALL_HANDLERS.values():
            handle(index)
        # index["ActionCondition"].export_all_to_folder(out_dir=OUT_DIR)

    print(f"total: {monotonic()-start:.4f}s")
