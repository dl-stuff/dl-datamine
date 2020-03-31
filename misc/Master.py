import json
import os
from loader.Database import DBManager, DBTableMetadata

def load_table_from_json(db, path):
    with open(path) as f:
        data = json.load(f)
        try:
            row = data[next(iter(data))]
            pk = next(iter(row))
        except:
            row = False
        if not (row and isinstance(row, dict) and pk.startswith('_')):
            print(f'Skip {path}')
            return
        table = os.path.basename(os.path.splitext(path)[0])
        meta = DBTableMetadata(table, pk=pk)
        meta.init_from_row(row)
        db.create_table(meta)
        db.insert_many(table, data.values())

def load_master(db, path):
    for root, _, files in os.walk(path):
        for f in files:
            load_table_from_json(db, os.path.join(root, f))

if __name__ == '__main__':
    from loader.Database import DBManager
    db = DBManager()
    load_master(db, './extract/master')