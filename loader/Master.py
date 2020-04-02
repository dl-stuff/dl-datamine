import json
import os
from loader.Database import DBManager, DBTableMetadata

EntryId = 'EntryId'
def load_table(db, data, table, key=None):
    if isinstance(data, dict):
        keys = data.keys()
        values = data.values()
    elif isinstance(data, list):
        keys = range(0, len(data))
        values = data
    else:
        return
    if len(values) == 0:
        print(f'Skip {table}')
        return
    row = next(iter(values))
    pk = next(iter(row))
    if isinstance(row, dict) and pk.startswith('_'):
        if key:
            if '_Id' in row:
                for v in values:
                    v[EntryId] = int(f'{key}{v["_Id"]:04}')
            else:
                for idx, v in enumerate(values):
                    v[EntryId] = int(f'{key}{idx:04}')
            row = next(iter(values))
            pk = EntryId
        if not db.check_table(table):
            meta = DBTableMetadata(table, pk=pk)
            meta.init_from_row(row, auto_pk=not key and '_Id' not in row)
            db.create_table(meta)
        db.insert_many(table, values, mode=DBManager.REPLACE)
    else:
        for k, v in zip(keys, values):
            load_table(db, v, table, key=k)

def load_json(db, path, table):
    db.drop_table(table)
    with open(path) as f:
        load_table(db, json.load(f), table)

def load_master(db, path):
    for root, _, files in os.walk(path):
        for fn in files:
            path = os.path.join(root, fn)
            table = os.path.basename(os.path.splitext(path)[0])
            load_json(db, path, table)

if __name__ == '__main__':
    db = DBManager()
    # path = './extract/en/master/InteractiveBGM.json'
    # table = 'InteractiveBGM'
    # with open(path) as f:
    #     load_table(db, json.load(f), table)
    load_master(db, './extract/en/master')