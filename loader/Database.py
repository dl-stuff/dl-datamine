import sqlite3
import json
import os

class DBDict(dict):
    def __repr__(self):
        return json.dumps(self, indent=2)

class DBTableMetadata:
    PK = ' PRIMARY KEY'
    AUTO = ' AUTOINCREMENT'
    INT = 'INTEGER'
    REAL = 'REAL'
    TEXT = 'TEXT'
    BLOB = 'BLOB'
    DBID = 'DBID'

    def __init__(self, name, pk='_Id', field_type={}):
        self.name = name
        self.pk = pk
        self.field_type = field_type

    def init_from_row(self, row, auto_pk=False):
        self.field_type = {}
        if auto_pk:
            self.pk = self.DBID
            self.field_type[self.DBID] = DBTableMetadata.INT + DBTableMetadata.PK + DBTableMetadata.AUTO
        for k, v in row.items():
            if isinstance(v, int):
                self.field_type[k] = DBTableMetadata.INT
            elif isinstance(v, float):
                self.field_type[k] = DBTableMetadata.REAL
            elif isinstance(v, str):
                self.field_type[k] = DBTableMetadata.TEXT
            else:
                self.field_type[k] = DBTableMetadata.BLOB
            if k == self.pk:
                self.field_type[k] += DBTableMetadata.PK

    def init_from_table_info(self, table_info):
        self.field_type = {}
        for c in table_info:
            if c['pk'] == 1:
                self.pk = c['name']
            self.field_type[c['name']] = c['type']

    @property
    def fields(self):
        return ','.join(filter(lambda k: k != self.DBID, self.field_type.keys()))

    @property
    def named_fields(self):
        return ','.join([f'{self.name}.{k}' for k in self.field_type.keys() if k != self.DBID])

    @property
    def field_types(self):
        return ','.join([f'{k} {v}' for k, v in self.field_type.items()])

    @property
    def field_length(self):
        return len(self.field_type) - 1 * int(self.pk == self.DBID)

    @property
    def blob_fields(self):
        return dict(filter(lambda x: x[1] == DBTableMetadata.BLOB, self.field_type.items())).keys()

    def __eq__(self, other):
        return self.name == other.name and self.pk == other.pk and self.field_type == other.field_type


class DBManager:
    def __init__(self, db_file='dl.sqlite', drop_on_reload=False):
        self.conn = None
        if db_file is not None:
            self.open(db_file)
        self.tables = {}
        self.drop_on_reload = True

    def open(self, db_file):
        self.conn = sqlite3.connect(db_file)
        self.conn.row_factory = sqlite3.Row

    def close(self):
        self.conn.close()
        self.conn = None

    @staticmethod
    def list_dict_values(data, tbl):
        for entry in data:
            if tbl.pk == DBTableMetadata.DBID or entry[tbl.pk]:
                for field in tbl.blob_fields:
                    entry[field] = json.dumps(entry[field])
                yield tuple(entry.values())

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
            table_info = self.query_many(f'PRAGMA table_info({table})', (), dict)
            if len(table_info) == 0:
                return False
            tbl = DBTableMetadata(table)
            tbl.init_from_table_info(table_info)
            if update_table_dict:
                self.tables[table] = tbl
            else:
                return tbl
        return self.tables[table]

    def drop_table(self, table):
        query = f'DROP TABLE IF EXISTS {table}'
        self.conn.execute(query)
        self.conn.commit()

    def create_table(self, meta):
        table = meta.name
        # query = f'DROP TABLE IF EXISTS {table}'
        # self.conn.execute(query)
        # self.tables[table] = meta
        query = f'CREATE TABLE IF NOT EXISTS {table} ({meta.field_types})'
        self.conn.execute(query)
        self.conn.commit()

    INSERT = 'INSERT'
    REPLACE = 'REPLACE'
    def insert_one(self, table, data, mode='INSERT'):
        tbl = self.check_table(table)
        values = '('+'?,'*tbl.field_length
        values = values[:-1]+')'
        query = f'{mode} INTO {table} ({tbl.fields}) VALUES {values}'
        self.conn.execute(query, data)
        self.conn.commit()

    def insert_many(self, table, data, mode='INSERT'):
        tbl = self.check_table(table)
        values = '('+'?,'*tbl.field_length
        values = values[:-1]+')'
        query = f'{mode} INTO {table} ({tbl.fields}) VALUES {values}'
        self.conn.executemany(query, self.list_dict_values(data, tbl))
        self.conn.commit()

    def select_all(self, table, d_type=DBDict):
        tbl = self.check_table(table)
        query = f'SELECT {tbl.named_fields} FROM {table}'
        return self.query_many(
            query=query,
            param=(),
            d_type=d_type
        )

    EXACT = 'exact'
    LIKE  = 'like'
    def select(self, table, value=None, by=None, fields=None, order=None, mode=EXACT, d_type=DBDict):
        tbl = self.check_table(table)
        by = by or tbl.pk
        if fields:
            named_fields = ','.join([f'{table}.{k}' for k in fields])
        else:
            named_fields = tbl.named_fields
        if mode == self.EXACT:
            query = f'SELECT {named_fields} FROM {table} WHERE {table}.{by}=?'
        elif mode == self.LIKE:
            query = f'SELECT {named_fields} FROM {table} WHERE {table}.{by} LIKE ? || \'%\''
        if order:
            query += f' ORDER BY {order}'
        return self.query_many(
            query=query,
            param=(value,),
            d_type=d_type
        )

    def create_view(self, name, table, references, join_mode='LEFT'):
        query = f'DROP VIEW IF EXISTS {name}'
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
                    fields.append(f'{rtbl.name}{k}.{rv[0]} AS {k}')
                else:
                    for v in rv:
                        fields.append(f'{rtbl.name}{k}.{v} AS {k}{v}')
                joins.append(f'{join_mode} JOIN {rtbl.name} AS {rtbl.name}{k} ON {tbl.name}.{k}={rtbl.name}{k}.{rk}')
                if rtbl.name == 'TextLabel' and not k.endswith('En'): # special case bolb
                    fields.append(f'{rtbl.name}JP{k}.{rv[0]} AS {k}JP')
                    joins.append(f'{join_mode} JOIN {rtbl.name}JP AS {rtbl.name}JP{k} ON {tbl.name}.{k}={rtbl.name}JP{k}.{rk}')
            else:
                fields.append(f'{tbl.name}.{k}')
        field_str = ','.join(fields)
        joins_str = '\n'+'\n'.join(joins)
        query = f'CREATE VIEW {name} AS SELECT {field_str} FROM {tbl.name} {joins_str}'
        self.conn.execute(query)
        self.conn.commit()

    def delete_view(self, name):
        query = f'DROP VIEW IF EXISTS {name}'
        self.conn.execute(query)
        self.conn.commit()

class DBView:
    def __init__(self, database, table, references=None, labeled_fields=None):
        self.database = database
        self.references = references or {}
        if table not in self.references and labeled_fields:
            self.references[table] = {}
            for label in labeled_fields:
                self.references[table][label] = ('TextLabel', '_Id', '_Text')
        self.name = table
        self.base_table = table
        if len(self.references) > 0:
            self.open()

    def get(self, pk, by=None, fields=None, order=None, mode=DBManager.EXACT, exclude_falsy=False):
        if order and '.' not in order:
            order = self.name + '.' + order
        res = self.database.select(self.name, pk, by, fields, order, mode)
        if exclude_falsy:
            res = [self.remove_falsy_fields(r) for r in res]
        if len(res) == 1:
            res = res[0]
        return res

    def get_all(self, exclude_falsy=False):
        res = self.database.select_all(self.name)
        if exclude_falsy:
            res = [self.remove_falsy_fields(r) for r in res]
        return res

    @staticmethod
    def remove_falsy_fields(res):
        return DBDict(filter(lambda x: bool(x[1]), res.items()))

    def open(self):
        self.name = f'View_{self.base_table}'
        self.database.create_view(self.name, self.base_table, self.references)

    def close(self):
        self.database.delete_view(self.name)
        self.name = self.base_table