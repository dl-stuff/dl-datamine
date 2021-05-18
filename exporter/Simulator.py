import json
import os
from glob import glob
from tqdm import tqdm
from itertools import count

from loader.Database import DBManager, DBTableMetadata
from loader.Actions import CommandType

SIM_TABLE_LIST = (
    "AbilityCrest",
    "AbilityData",
    "AbilityLimitedGroup",
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
    "TextLabel",
    "PlayerAction",
    "PlayerActionHitAttribute",
    "UnionAbility",
)

ACTION_PARTS = DBTableMetadata(
    "ActionParts",
    pk="_Id",
    field_type={
        "_Id": DBTableMetadata.INT + DBTableMetadata.PK,
        "data": DBTableMetadata.BLOB,
    },
)

DL9_DB = "../dl9/core/conf.sqlite"


def transfer_sim_db(dl_sim_db):
    db = DBManager()
    db.transfer(dl_sim_db, SIM_TABLE_LIST)


# Trying to be smart about this makes db bigger


def process_action_part_one(action_id, seq, data, processed, field_type, cnt=None):
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
        cnt = count()
    else:
        pk += f"{next(cnt):03}"
    for k, v in data.items():
        if isinstance(v, dict):
            if v.get("commandType"):
                child_pk = process_action_part_one(action_id, seq, v, processed, field_type, cnt=cnt)
                if child_pk:
                    data[k] = child_pk
                else:
                    data[k] = None
                field_type[k] = DBTableMetadata.TEXT
            else:
                field_type[k] = DBTableMetadata.BLOB
        elif isinstance(v, list):
            if not v or not any(v):
                data[k] = None
            field_type[k] = DBTableMetadata.BLOB
        elif isinstance(v, int):
            field_type[k] = DBTableMetadata.INT
        elif isinstance(v, float):
            field_type[k] = DBTableMetadata.REAL
        elif isinstance(v, str):
            field_type[k] = DBTableMetadata.TEXT
        else:
            field_type[k] = DBTableMetadata.BLOB

    data["pk"] = pk
    data["act"] = action_id
    data["seq"] = seq

    if pk in processed and processed[pk] != data:
        raise ValueError(f"Collision {pk}:\n{processed[pk]}\n{data}")
    processed[pk] = data

    return pk


def transfer_actions_as_one_schema(actions_dir, dl_sim_db):
    processed = {}
    field_type = {
        "pk": DBTableMetadata.INT + DBTableMetadata.PK,
        "act": DBTableMetadata.INT,
        "seq": DBTableMetadata.INT,
    }
    for filename in tqdm(glob(actions_dir + "/PlayerAction_*.json"), desc="actions"):
        action_id = filename.split("_")[-1].replace(".json", "")
        with open(filename, "r") as fn:
            for seq, part in enumerate(json.load(fn)):
                process_action_part_one(action_id, seq, part, processed, field_type)

    db = DBManager(dl_sim_db)
    meta = DBTableMetadata("ActionParts", pk="pk", field_type=field_type)
    db.drop_table(meta.name)
    db.create_table(meta)
    db.insert_many(meta.name, processed.values(), mode=DBManager.REPLACE)


def process_action_part_multi(action_id, seq, data, processed, tablemetas, key=None, cnt=None):
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

    try:
        tbl = "Parts" + CommandType(data["commandType"]).name
    except KeyError:
        tbl = "PartsParam" + key.strip("_")
    pk = f"{action_id}{seq:03}"
    if key is None:
        processed["PartsIndex"].append(
            {
                "pk": pk,
                "act": action_id,
                "seq": seq,
                "part": tbl,
            }
        )
    if cnt is None:
        cnt = count()
    else:
        pk += f"{next(cnt):03}"
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

    for k, v in data.items():
        if isinstance(v, dict):
            # if v.get("commandType"):
            child_result = process_action_part_multi(action_id, seq, v, processed, tablemetas, key=k, cnt=cnt)
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
            meta.field_type[k] = DBTableMetadata.BLOB
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


def transfer_actions_as_many_schema(actions_dir, dl_sim_db):
    processed = {"PartsIndex": []}
    tablemetas = {
        "PartsIndex": DBTableMetadata(
            "PartsIndex",
            pk="pk",
            field_type={
                "pk": DBTableMetadata.INT + DBTableMetadata.PK,
                "act": DBTableMetadata.INT,
                "seq": DBTableMetadata.INT,
                "part": DBTableMetadata.TEXT,
            },
        )
    }
    for filename in tqdm(glob(actions_dir + "/PlayerAction_*.json"), desc="actions"):
        action_id = filename.split("_")[-1].replace(".json", "")
        with open(filename, "r") as fn:
            for seq, part in enumerate(json.load(fn)):
                process_action_part_multi(action_id, seq, part, processed, tablemetas)

    db = DBManager(dl_sim_db)
    for tbl, meta in tablemetas.items():
        # print(tbl, meta.name)
        # for k, v in meta.field_type.items():
        #     print("field", k, v)
        # for k, v in meta.foreign_keys.items():
        #     print("foreign", k, v)
        # print()
        db.drop_table(tbl)
        db.create_table(meta)
        db.insert_many(tbl, processed[tbl], mode=DBManager.REPLACE)


def prune_falsy(data):
    try:
        pruned = {}
        for k, v in data.items():
            if k[0] == "_":
                k = k[1:]
            pv = prune_falsy(v)
            if pv:
                pruned[k] = pv
        return pruned
    except AttributeError:
        try:
            return any(data) and data
        except TypeError:
            return data


def transfer_actions(actions_dir, dl_sim_db):
    db = DBManager(dl_sim_db)
    db.drop_table(ACTION_PARTS.name)
    db.create_table(ACTION_PARTS)
    sorted_data = []
    for filename in tqdm(glob(actions_dir + "/PlayerAction_*.json"), desc="actions"):
        action_id = filename.split("_")[-1].replace(".json", "")
        pruned_parts = []
        with open(filename, "r") as fn:
            for part in json.load(fn):
                pruned_parts.append(prune_falsy(part))
        sorted_data.append({"_Id": int(action_id), "data": pruned_parts})
    db.insert_many(ACTION_PARTS.name, sorted_data)


if __name__ == "__main__":
    if os.path.exists(DL9_DB):
        os.remove(DL9_DB)
    transfer_sim_db(DL9_DB)
    # transfer_actions("./_ex_sim/jp/actions", "../dl9/conf.sqlite")
    # transfer_actions_as_one_schema("./_ex_sim/jp/actions", DL9_DB)
    transfer_actions_as_many_schema("./_ex_sim/jp/actions", DL9_DB)
