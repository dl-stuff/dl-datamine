import shutil
import json
import os
from glob import glob
from tqdm import tqdm
from itertools import count

from loader.Database import DBManager, DBTableMetadata

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

DL9_DB = "../dl9/conf.sqlite"


def transfer_sim_db(dl_sim_db):
    db = DBManager()
    db.transfer(dl_sim_db, SIM_TABLE_LIST)


# Trying to be smart about this makes db bigger


def process_action_part_one(action_id, seq, data, processed, field_type, foreign_keys, cnt=None):
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
    foreign_keys = {}
    for filename in tqdm(glob(actions_dir + "/PlayerAction_*.json"), desc="actions"):
        action_id = filename.split("_")[-1].replace(".json", "")
        with open(filename, "r") as fn:
            for seq, part in enumerate(json.load(fn)):
                process_action_part_one(action_id, seq, part, processed, foreign_keys, field_type)

    db = DBManager(dl_sim_db)
    meta = DBTableMetadata("ActionParts", pk="pk", field_type=field_type)
    db.drop_table(meta.name)
    db.create_table(meta)
    db.insert_many(meta.name, processed.values(), mode=DBManager.REPLACE)


def process_action_part_multi(action_id, seq, data, processed, tablemetas, cnt=None):
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

    field_type = {
        "pk": DBTableMetadata.INT + DBTableMetadata.PK,
        "act": DBTableMetadata.INT,
        "seq": DBTableMetadata.INT,
    }

    pk = f"{action_id}{seq:03}"
    if cnt is None:
        cnt = count()
    else:
        pk += f"{next(cnt):03}"
    for k, v in data.items():
        if isinstance(v, dict):
            if v.get("commandType"):
                child_pk = process_action_part_multi(action_id, seq, v, processed, field_type, cnt=cnt)
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


def transfer_actions_as_many_schema(actions_dir, dl_sim_db):
    processed = {}
    for filename in tqdm(glob(actions_dir + "/PlayerAction_*.json"), desc="actions"):
        action_id = filename.split("_")[-1].replace(".json", "")
        with open(filename, "r") as fn:
            for seq, part in enumerate(json.load(fn)):
                process_action_part_multi(action_id, seq, part, processed, field_type)

    db = DBManager(dl_sim_db)
    meta = DBTableMetadata("ActionParts", pk="pk", field_type=field_type)
    db.drop_table(meta.name)
    db.create_table(meta)
    db.insert_many(meta.name, processed.values(), mode=DBManager.REPLACE)


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
    os.remove(DL9_DB)
    transfer_sim_db(DL9_DB)
    # transfer_actions("./_ex_sim/jp/actions", "../dl9/conf.sqlite")
    transfer_actions_as_one_schema("./_ex_sim/jp/actions", DL9_DB)