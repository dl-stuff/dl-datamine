import json
import os
from collections import defaultdict
from itertools import count

from tqdm import tqdm
from loader.Database import DBManager, DBTableMetadata
from pprint import pprint

EntryId = "EntryId"


def flatten_data(data, table, parent_keys=None):
    if not data:
        return {}
    if isinstance(data, list):
        row = data[0]
        pk = "_Id" if "_Id" in row else next(iter(row))
        if not isinstance(row, dict) or not pk.startswith("_"):
            return {}
        if parent_keys is None:
            parent_keys = []
        flattened = {}
        for seq, entry in enumerate(data):
            pk = f"{table}_0"
            entry[pk] = "".join(map(str, parent_keys)) + str(seq)
            if parent_keys:
                for idx, parent_key in enumerate(parent_keys):
                    entry[f"{table}_{idx+1}"] = parent_key
                entry[f"{table}_{idx+2}"] = seq
            flattened[entry[pk]] = entry
        return flattened
    if not isinstance(data, dict):
        return {}
    row = next(iter(data.values()))
    pk = "_Id" if "_Id" in row else next(iter(row))
    if isinstance(row, dict) and pk.startswith("_"):
        flattened = data
        if parent_keys is not None:
            flattened = {}
            for key, row in data.items():
                pk = f"{table}_0"
                row[pk] = "".join(map(str, parent_keys)) + str(key)
                if parent_keys:
                    for idx, parent_key in enumerate(parent_keys):
                        row[f"{table}_{idx+1}"] = parent_key
                    row[f"{table}_{idx+2}"] = key
                flattened[row[pk]] = row
        return flattened
    flattened = {}
    if parent_keys is None:
        parent_keys = []
    for key, row in data.items():
        flattened.update(flatten_data(row, table, parent_keys=(parent_keys + [key])))
    return flattened


def load_table(db, data, table, stdout_log=False, extra_proc=None):
    data = flatten_data(data, table)
    if extra_proc:
        data = extra_proc(data)
    if not data:
        if stdout_log:
            print(f"Skip {table}")
        return
    row = next(iter(data.values()))
    auto_pk = False
    if f"{table}_0" in row:
        pk = f"{table}_0"
    elif "_Id" in row:
        pk = "_Id"
    else:
        auto_pk = True
    if not db.check_table(table):
        meta = DBTableMetadata(table, pk=pk)
        meta.init_from_row(row, auto_pk=auto_pk)
        db.create_table(meta)
    db.insert_many(table, data.values(), mode=DBManager.REPLACE)


def proc_MC(data):
    id_piece_count = defaultdict(count)
    for key, row in data.items():
        row["_ManaCircleName"] = f"MC_{int(row['MC_1']):04}"
        row["_Step"] = next(id_piece_count[(row["MC_1"], row["_ManaPieceType"])]) + 1
    return data


def load_json(db, path, table, stdout_log=False):
    db.drop_table(table)
    extra_proc = proc_MC if table == "MC" else None
    with open(path) as f:
        load_table(db, json.load(f), table, stdout_log=stdout_log, extra_proc=extra_proc)


def load_master(db, path, stdout_log=False):
    for root, _, files in os.walk(path):
        for fn in tqdm(files, desc="master"):
            path = os.path.join(root, fn)
            base, ext = os.path.splitext(path)
            if ext != ".json":
                continue
            table = os.path.basename(base)
            load_json(db, path, table, stdout_log)


if __name__ == "__main__":
    db = DBManager()
    # table = "MC"
    # path = f"./_ex_sim/en/master/{table}.json"
    # with open(path) as f:
    #     load_json(db, path, table)
    load_master(db, "./_ex_sim/en/master")
