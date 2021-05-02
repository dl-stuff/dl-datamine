import glob
import re
import os

from loader.Database import DBManager
from exporter.Mappings import ELEMENTS, WEAPON_TYPES

FOLLOWER_GLOB = "_apk/Assembly-CSharp/Gluon/FollowerAI_*"
FUNC_OVERRIDE_PATTERN = re.compile(r"\s*public override (\w+) (\w+)\(.*")

QUERY_CHARA_NAME = "SELECT _Name, _SecondName FROM View_CharaData WHERE _Id=?"


def chara_id_to_ele_wt(chara_id):
    chara_id = str(chara_id)
    ele = ELEMENTS.get(int(chara_id[5]), "Null")
    wt = WEAPON_TYPES.get(int(chara_id[2]), "Blord")
    return ele, wt


def find_unique_follower_ai():
    found_ai = {}
    for filepath in glob.glob(FOLLOWER_GLOB):
        chara_id = int(os.path.splitext(os.path.basename(filepath))[0].split("_")[1])
        found_ai[chara_id] = set()
        with open(filepath, "r") as fn:
            for line in fn:
                if (res := FUNC_OVERRIDE_PATTERN.match(line)) :
                    found_ai[chara_id].add(res.groups())

    dbm = DBManager()
    known_ai, unknown_ai = {}, {}
    for chara_id, func_defs in found_ai.items():
        query_res = dbm.query_one(QUERY_CHARA_NAME, (chara_id,), dict)
        chara_name = None
        if query_res:
            chara_name = query_res["_SecondName"] or query_res["_Name"]
            known_ai[chara_id] = {"name": chara_name, "func": sorted(func_defs)}
        if not chara_name:
            ele, wt = chara_id_to_ele_wt(chara_id)
            chara_name = f"UNKNOWN {ele} {wt}"
            unknown_ai[chara_id] = {"name": chara_name, "func": sorted(func_defs)}

    return known_ai, unknown_ai


if __name__ == "__main__":
    known_ai, unknown_ai = find_unique_follower_ai()
    for chara_id, ai_data in known_ai.items():
        print(chara_id, ai_data["name"])
        for retype, name in ai_data["func"]:
            print(" ", retype, name)
    print()
    for chara_id, ai_data in unknown_ai.items():
        print(chara_id, ai_data["name"])
        for retype, name in ai_data["func"]:
            print(" ", retype, name)
