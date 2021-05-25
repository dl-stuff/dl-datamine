import json
import os
import itertools
import re
from glob import glob
from tqdm import tqdm
import shutil

from loader.Database import DBManager, DBTableMetadata
from loader.Actions import CommandType

SIM_TABLE_LIST = (
    "AbilityCrest",
    "AbilityData",
    "ExAbilityData",
    "ActionCondition",
    "ActionGrant",
    "AuraData",
    "CharaData",
    "CharaModeData",
    "CharaUniqueCombo",
    "DragonData",
    "SkillData",
    "WeaponBody",
    "WeaponType",
    "PlayerAction",
    "PlayerActionHitAttribute",
    "UnionAbility",
    "EnemyParam",
    "MotionData",
)

DL9_DB = "../dl9/core/conf.sqlite"


def transfer_sim_db(dl_sim_db):
    db = DBManager()
    db.transfer(dl_sim_db, SIM_TABLE_LIST)


HIT_LABEL_FIELDS = (
    "_hitLabel",
    "_hitAttrLabel",
    "_hitAttrLabelSubList",
    "_abHitAttrLabel",
)
LV_PATTERN = re.compile(r"_LV\d{2}.*")


PARTS_INDEX = DBTableMetadata(
    "PartsIndex",
    pk="pk",
    field_type={
        "pk": DBTableMetadata.INT + DBTableMetadata.PK,
        "act": DBTableMetadata.INT,
        "seq": DBTableMetadata.INT,
        "part": DBTableMetadata.TEXT,
    },
)

PARTS_HITLABEL = DBTableMetadata(
    "PartsHitLabel",
    pk="pk",
    field_type={
        "pk": DBTableMetadata.INT + DBTableMetadata.PK,
        "act": DBTableMetadata.INT,
        "seq": DBTableMetadata.INT,
        "source": DBTableMetadata.TEXT,
        "hitLabel": DBTableMetadata.TEXT,
        "hitLabelGlob": DBTableMetadata.TEXT,
    },
)


def process_action_part_label(pk, cnt, label, processed, action_id, seq, k, data, meta):
    label_pk = pk + f"{next(cnt):03}"
    if label.startswith("CMN_AVOID"):
        label_glob = label
    elif LV_PATTERN.search(label):
        label_glob = LV_PATTERN.sub("_LV[0-9][0-9]*", label)
    else:
        label_glob = f"{label}*"
    processed[PARTS_HITLABEL.name].append(
        {
            "pk": label_pk,
            "act": action_id,
            "seq": seq,
            "source": k,
            "hitLabel": label,
            "hitLabelGlob": label_glob,
        }
    )
    data[k] = label_pk
    meta.foreign_keys[k] = (PARTS_HITLABEL.name, "pk")
    return label_pk


def process_action_part(action_id, seq, data, processed, tablemetas, key=None, cnt=None):
    non_empty = False
    for v in data.values():
        try:
            non_empty = any(v)
        except TypeError:
            non_empty = bool(v)
        if non_empty:
            break
    if not non_empty:
        return None

    pk = f"{action_id}{seq:03}"
    if cnt is None:
        cnt = itertools.count()
    else:
        pk += f"{next(cnt):03}"
    try:
        tbl = "Parts_" + CommandType(data["commandType"]).name
    except KeyError:
        tbl = "PartsParam" + "_" + key.strip("_")
    if key is None:
        processed[PARTS_INDEX.name].append(
            {
                "pk": pk,
                "act": action_id,
                "seq": seq,
                "part": tbl,
            }
        )
    try:
        meta = tablemetas[tbl]
    except KeyError:
        meta = DBTableMetadata(
            tbl,
            pk="pk",
            field_type={
                "pk": DBTableMetadata.INT + DBTableMetadata.PK,
                "act": DBTableMetadata.INT,
                "seq": DBTableMetadata.INT,
            },
        )
        tablemetas[tbl] = meta
        processed[tbl] = []

    for k, v in data.copy().items():
        if isinstance(v, dict):
            # if v.get("commandType"):
            child_result = process_action_part(action_id, seq, v, processed, tablemetas, key=k, cnt=cnt)
            if child_result:
                child_tbl, child_pk = child_result
                data[k] = child_pk
                meta.foreign_keys[k] = (child_tbl, "pk")
            else:
                data[k] = None
            meta.field_type[k] = DBTableMetadata.INT
            # else:
            #     meta.field_type[k] = DBTableMetadata.BLOB
        elif isinstance(v, list):
            if not v or not any(v):
                data[k] = None
            for idx, subv in enumerate(v):
                new_k = k
                if idx:
                    new_k = f"{k}{idx}"
                if isinstance(subv, dict):
                    child_result = process_action_part(action_id, seq, subv, processed, tablemetas, key=k, cnt=cnt)
                    if child_result:
                        child_tbl, child_pk = child_result
                        data[new_k] = child_pk
                        meta.foreign_keys[new_k] = (child_tbl, "pk")
                    else:
                        data[new_k] = None
                    meta.field_type[new_k] = DBTableMetadata.INT
                else:
                    data[new_k] = subv
                    if isinstance(subv, int):
                        meta.field_type[new_k] = DBTableMetadata.INT
                    elif isinstance(subv, float):
                        meta.field_type[new_k] = DBTableMetadata.REAL
                    elif isinstance(subv, str):
                        meta.field_type[new_k] = DBTableMetadata.TEXT
        elif isinstance(v, int):
            meta.field_type[k] = DBTableMetadata.INT
        elif isinstance(v, float):
            meta.field_type[k] = DBTableMetadata.REAL
        elif isinstance(v, str):
            meta.field_type[k] = DBTableMetadata.TEXT
        else:
            meta.field_type[k] = DBTableMetadata.BLOB

    data["pk"] = pk
    data["act"] = action_id
    data["seq"] = seq

    processed[tbl].append(data)

    return tbl, pk


def transfer_actions_db(db_file, actions_dir):
    processed = {
        PARTS_INDEX.name: [],
        # PARTS_HITLABEL.name: [],
    }
    tablemetas = {
        PARTS_INDEX.name: PARTS_INDEX,
        # PARTS_HITLABEL.name: PARTS_HITLABEL,
    }
    for filename in tqdm(glob(actions_dir + "/PlayerAction_*.json"), desc="read_actions"):
        action_id = filename.split("_")[-1].replace(".json", "")
        with open(filename, "r") as fn:
            for seq, part in enumerate(json.load(fn)):
                process_action_part(action_id, seq, part, processed, tablemetas)

    db = DBManager(db_file)
    for tbl, meta in tqdm(tablemetas.items(), desc="load_actions"):
        db.drop_table(tbl)
        db.create_table(meta)
        db.insert_many(tbl, processed[tbl], mode=DBManager.REPLACE)


def transfer_actions_json(output_dir, actions_dir):
    for filename in tqdm(glob(actions_dir + "/PlayerAction_*.json"), desc="copy_actions"):
        shutil.copy(filename, os.path.join(output_dir, os.path.basename(filename)))


if __name__ == "__main__":
    if os.path.exists(DL9_DB):
        os.remove(DL9_DB)
    transfer_sim_db(DL9_DB)
    # transfer_actions_db(DL9_DB, "./_ex_sim/jp/actions")
    transfer_actions_json("../dl9/action/data", "./_ex_sim/jp/actions")
