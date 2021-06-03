import sqlite3
import json
import os
import errno
from tqdm import tqdm
from collections import defaultdict
from enum import Enum

DB_FILE = "dl.sqlite"

TEXT_REGIONS = ["JP", "CN"]


def check_target_path(target):
    if not os.path.exists(target):
        try:
            os.makedirs(target)
        except OSError as exc:  # Guard against race condition
            if exc.errno != errno.EEXIST:
                raise


class ShortEnum(Enum):
    def __str__(self):
        return f"{self.value:03}-{self.name}"


class DBDict(dict):
    def __repr__(self):
        return json.dumps(self, indent=2, default=str)


class DBTableMetadata:
    PK = " PRIMARY KEY"
    AUTO = " AUTOINCREMENT"
    INT = "INTEGER"
    REAL = "REAL"
    TEXT = "TEXT"
    BLOB = "BLOB"
    DBID = "DBID"

    def __init__(self, name, pk="_Id", field_type=None, foreign_keys=None):
        self.name = name
        self.pk = pk
        self.field_type = field_type or {}
        self.foreign_keys = foreign_keys or {}

    def init_from_row(self, row, auto_pk=False, extra_fields={}):
        self.field_type = {}
        if auto_pk:
            self.pk = self.DBID
            self.field_type[self.DBID] = DBTableMetadata.INT + DBTableMetadata.PK + DBTableMetadata.AUTO
        self.field_type.update(extra_fields)
        for k, v in row.items():
            if isinstance(v, int):
                self.field_type[k] = DBTableMetadata.INT
            elif isinstance(v, float):
                self.field_type[k] = DBTableMetadata.REAL
            elif isinstance(v, str):
                if v.isdigit():
                    self.field_type[k] = DBTableMetadata.INT
                else:
                    self.field_type[k] = DBTableMetadata.TEXT
            else:
                self.field_type[k] = DBTableMetadata.BLOB
            if k == self.pk:
                self.field_type[k] += DBTableMetadata.PK

    def init_from_table_info(self, table_info, foreign_key_info=None):
        self.field_type = {}
        self.foreign_keys = {}
        for c in table_info:
            if c["pk"] == 1:
                self.pk = c["name"]
            self.field_type[c["name"]] = c["type"]
        if foreign_key_info:
            for fk in foreign_key_info:
                self.foreign_keys[fk["from"]] = (fk["table"], fk["to"])

    def get_field(self, key):
        return self.field_type[key]

    @property
    def fields(self):
        return ",".join(filter(lambda k: k != self.DBID, self.field_type.keys()))

    @property
    def named_fields(self):
        return ",".join([f"{self.name}.{k}" for k in self.field_type.keys() if k != self.DBID])

    @property
    def field_types(self):
        fieldstr = ",".join([f"{k} {v}" for k, v in self.field_type.items()])
        fkstr = ",".join([f"FOREIGN KEY({k}) REFERENCES {v[0]}({v[1]})" for k, v in self.foreign_keys.items()])
        if fkstr:
            fieldstr += "," + fkstr
        return fieldstr

    @property
    def field_length(self):
        return len(self.field_type) - 1 * int(self.pk == self.DBID)

    @property
    def blob_fields(self):
        return dict(filter(lambda x: x[1] == DBTableMetadata.BLOB, self.field_type.items())).keys()

    def __eq__(self, other):
        return self.name == other.name and self.pk == other.pk and self.field_type == other.field_type


class DBManager:
    def __init__(self, db_file=DB_FILE):
        self.conn = None
        if db_file is not None:
            self.open(db_file)
        self.tables = {}

    def __del__(self):
        self.close()

    def open(self, db_file):
        self.conn = sqlite3.connect(db_file)
        self.conn.row_factory = sqlite3.Row

    def close(self):
        self.conn.close()
        self.conn = None

    def transfer(self, new_db_file, table_list):
        self.conn.execute(f"ATTACH DATABASE '{new_db_file}' AS target;")
        self.conn.commit()
        for table in tqdm(table_list, desc="transfer"):
            meta = self.check_table(f"View_{table}")
            if not meta:
                meta = self.check_table(table)
            self.conn.execute(f"DROP TABLE IF EXISTS target.{table}")
            self.conn.execute(f"CREATE TABLE target.{table} ({meta.field_types});")
            self.conn.execute(f"INSERT INTO target.{table} SELECT * FROM main.{meta.name};")
            self.conn.commit()
        self.conn.execute(f"DETACH DATABASE target;")
        self.conn.commit()

    @staticmethod
    def list_dict_values(data, tbl):
        for entry in data:
            if tbl.pk == DBTableMetadata.DBID or entry[tbl.pk]:
                for field in tbl.blob_fields:
                    if entry.get(field):
                        entry[field] = json.dumps(entry[field])
                yield tuple(entry.get(field) for field in tbl.field_type.keys() if field != DBTableMetadata.DBID)

    def query_one(self, query, param, d_type):
        cursor = self.conn.cursor()
        cursor.execute(query, param)
        res = cursor.fetchone()
        if res is not None:
            return d_type(res)
        return None

    def query_many(self, query, param, d_type, idx_key=None):
        cursor = self.conn.cursor()
        cursor.execute(query, param)
        if cursor.rowcount == 0:
            return []
        if idx_key is None:
            return [d_type(res) for res in cursor.fetchall()]
        else:
            return dict({res[idx_key]: d_type(res) for res in cursor.fetchall()})

    def check_table(self, table, update_table_dict=True):
        if table not in self.tables:
            table_info = self.query_many(f"PRAGMA table_info({table})", (), dict)
            if len(table_info) == 0:
                return False
            foreign_key_info = self.query_many(f"PRAGMA foreign_key_list({table})", (), dict)
            tbl = DBTableMetadata(table)
            tbl.init_from_table_info(table_info, foreign_key_info)
            if update_table_dict:
                self.tables[table] = tbl
            else:
                return tbl
        return self.tables[table]

    def drop_table(self, table):
        query = f"DROP TABLE IF EXISTS {table}"
        self.conn.execute(query)
        self.conn.commit()

    def create_table(self, meta):
        table = meta.name
        # query = f'DROP TABLE IF EXISTS {table}'
        # self.conn.execute(query)
        # self.tables[table] = meta
        query = f"CREATE TABLE IF NOT EXISTS {table} ({meta.field_types})"
        self.conn.execute(query)
        self.conn.commit()

    INSERT = "INSERT"
    REPLACE = "INSERT OR REPLACE"

    def insert_one(self, table, data, mode="INSERT"):
        tbl = self.check_table(table)
        values = "(" + "?," * tbl.field_length
        values = values[:-1] + ")"
        query = f"{mode} INTO {table} ({tbl.fields}) VALUES {values}"
        self.conn.execute(query, data)
        self.conn.commit()

    def insert_many(self, table, data, mode="INSERT"):
        tbl = self.check_table(table)
        values = "(" + "?," * tbl.field_length
        values = values[:-1] + ")"
        query = f"{mode} INTO {table} ({tbl.fields}) VALUES {values}"
        self.conn.executemany(query, self.list_dict_values(data, tbl))
        self.conn.commit()

    def select_all(self, table, where=None, order=None, d_type=DBDict):
        tbl = self.check_table(table)
        query = f"SELECT {tbl.named_fields} FROM {table}"
        if where:
            query += " WHERE " + where
        if order:
            query += " ORDER BY " + order
        return self.query_many(query=query, param=(), d_type=d_type)

    EXACT = "exact"
    LIKE = "like"
    RANGE = "range"
    GLOB = "glob"

    def select(self, table, value=None, by=None, fields=None, where=None, order=None, mode=EXACT, d_type=DBDict):
        tbl = self.check_table(table)
        by = by or tbl.pk
        if fields:
            named_fields = ",".join([f"{table}.{k}" for k in fields])
        else:
            named_fields = tbl.named_fields
        query = f"SELECT {named_fields} FROM {table}"
        if mode == self.LIKE:
            query += f" WHERE {table}.{by} LIKE ? || '%'"
        elif mode == self.GLOB:
            query += f" WHERE {table}.{by} GLOB ?"
        elif mode == self.RANGE:
            query += f" WHERE {table}.{by} >= ? AND {table}.{by} < ?"
        else:  # mode == self.EXACT
            query += f" WHERE {table}.{by}=?"
        if where:
            query += f" AND {where}"
        if order:
            query += f" ORDER BY {order}"
        value = (value,) if not isinstance(value, tuple) else value
        return self.query_many(query=query, param=value, d_type=d_type)

    def create_view(self, name, table, references, join_mode="LEFT"):
        query = f"DROP VIEW IF EXISTS {name}"
        self.conn.execute(query)
        tbl = self.check_table(table)
        fields = []
        joins = []
        for k in tbl.field_type.keys():
            if table in references and k in references[table]:
                rtbl_tpl = references[table][k]
                rtbl = rtbl_tpl[0]
                rk = rtbl_tpl[1]
                rv = rtbl_tpl[2:]
                rtbl = self.check_table(rtbl)
                if len(rv) == 1:
                    fields.append(f"{rtbl.name}{k}.{rv[0]} AS {k}")
                else:
                    for v in rv:
                        fields.append(f"{rtbl.name}{k}.{v} AS {k}{v}")
                joins.append(f"{join_mode} JOIN {rtbl.name} AS {rtbl.name}{k} ON {tbl.name}.{k}={rtbl.name}{k}.{rk}")
                if rtbl.name == "TextLabel" and not k.endswith("En"):  # special case bolb
                    for region in TEXT_REGIONS:
                        fields.append(f"{rtbl.name}{region}{k}.{rv[0]} AS {k}{region}")
                        joins.append(f"{join_mode} JOIN {rtbl.name}{region} AS {rtbl.name}{region}{k} ON {tbl.name}.{k}={rtbl.name}{region}{k}.{rk}")
            else:
                fields.append(f"{tbl.name}.{k}")
        field_str = ",".join(fields)
        joins_str = "\n" + "\n".join(joins)
        query = f"CREATE VIEW {name} AS SELECT {field_str} FROM {tbl.name} {joins_str}"
        self.conn.execute(query)
        self.conn.commit()

    def delete_view(self, name):
        query = f"DROP VIEW IF EXISTS {name}"
        self.conn.execute(query)
        self.conn.commit()


class DBView:
    EXCLUDE_FALSY = True

    def __init__(self, index, table, references=None, labeled_fields=None, override_view=False):
        self.index = index
        self.database = index.db
        self.references = references or {}
        if table not in self.references and labeled_fields:
            self.references[table] = {}
            for label in labeled_fields:
                self.references[table][label] = ("TextLabel", "_Id", "_Text")
        self.name = table
        self.base_table = table
        if len(self.references) > 0 or override_view:
            self.open()

    def process_result(self, res, **kargs):
        return res

    @staticmethod
    def outfile_name(res, ext=".json"):
        name = "_" + res.get("_Name", "")
        return f'{res["_Id"]}{name}{ext}'

    def link(self, res, key, view, **kwargs):
        if (idx := res.get(key)) and (linked := self.index[view].get(idx, **kwargs)):
            res[key] = linked

    def get(self, pk, by=None, fields=None, where=None, order=None, mode=DBManager.EXACT, expand_one=True, full_query=True, **kwargs):
        if order and "." not in order:
            order = self.name + "." + order
        res = self.database.select(self.name, pk, by, fields, where, order, mode)
        if self.EXCLUDE_FALSY:
            res = [self.remove_falsy_fields(r) for r in res]
        if expand_one and len(res) == 1:
            res = res[0]
        if res and full_query:
            return self.process_result(res, **kwargs)
        return res

    def get_all(self, where=None, order=None):
        res = self.database.select_all(self.name, where, order)
        if self.EXCLUDE_FALSY:
            res = [self.remove_falsy_fields(r) for r in res]
        return res

    @staticmethod
    def remove_falsy_fields(res):
        return DBDict(filter(lambda x: bool(x[1]), res.items()))

    def open(self):
        self.name = f"View_{self.base_table}"
        self.database.create_view(self.name, self.base_table, self.references)

    def close(self):
        self.database.delete_view(self.name)
        self.name = self.base_table

    def export_all_to_folder(self, out_dir, ext=".json", where=None, order=None, **kargs):
        all_res = self.get_all(where=where, order=order)
        check_target_path(out_dir)
        for res in tqdm(all_res, desc=os.path.basename(out_dir)):
            res = self.process_result(res, **kargs)
            out_name = self.outfile_name(res, ext)
            output = os.path.join(out_dir, out_name)
            with open(output, "w", newline="", encoding="utf-8") as fp:
                json.dump(res, fp, indent=2, ensure_ascii=False, default=str)

    def export_one_to_folder(self, pk, out_dir, ext=".json", **kargs):
        res = self.get(pk, **kargs)
        check_target_path(out_dir)
        out_name = self.outfile_name(res, ext)
        output = os.path.join(out_dir, out_name)
        with open(output, "w", newline="", encoding="utf-8") as fp:
            json.dump(res, fp, indent=2, ensure_ascii=False, default=str)


class DBViewIndex:
    @staticmethod
    def all_subclasses(c):
        return set(c.__subclasses__()).union([s for c in c.__subclasses__() for s in DBViewIndex.all_subclasses(c)])

    def __init__(self, db_file=DB_FILE):
        super().__init__()
        self.db = DBManager(db_file=db_file)
        self.class_dict = {view_class.__name__: view_class for view_class in DBViewIndex.all_subclasses(DBView)}
        self.instance_dict = {}

    def __getitem__(self, key):
        if key in self.instance_dict:
            return self.instance_dict[key]
        elif key in self.class_dict:
            self.instance_dict[key] = self.class_dict[key](self)
        else:
            self.instance_dict[key] = DBView(self, key)
        return self.instance_dict[key]
