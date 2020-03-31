import sqlite3
import json
import os

class DBTableMetadata:
    PK = ' PRIMARY KEY'
    INT = 'INTEGER'
    REAL = 'REAL'
    TEXT = 'TEXT'
    BLOB = 'BLOB'

    def __init__(self, name, pk='_Id', field_type={}):
        self.name = name
        self.pk = pk
        self.field_type = field_type

    def init_from_row(self, row):
        self.field_type = {}
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
        return ','.join(self.field_type.keys())

    @property
    def named_fields(self):
        return ','.join([f'{self.name}.{k}' for k in self.field_type.keys()])

    @property
    def field_types(self):
        return ','.join([f'{k} {v}' for k, v in self.field_type.items()])

    @property
    def field_length(self):
        return len(self.field_type)

class DBManager:
    def __init__(self, db_file='dl.sqlite'):
        self.conn = None
        if db_file is not None:
            self.open(db_file)
        self.tables = {}

    def open(self, db_file):
        self.conn = sqlite3.connect(db_file)
        self.conn.row_factory = sqlite3.Row

    def close(self):
        self.conn.close()
        self.conn = None

    @staticmethod
    def list_dict_values(data, pk):
        for entry in data:
            if entry[pk]:
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

    def check_table(self, table):
        if table not in self.tables:
            table_info = self.query_many(f'PRAGMA table_info({table})', (), dict)
            tbl = DBTableMetadata(table)
            tbl.init_from_table_info(table_info)
            self.tables[table] = tbl
        return self.tables[table]

    def create_table(self, meta):
        table = meta.name
        query = f'DROP TABLE IF EXISTS {table}'
        self.conn.execute(query)
        self.tables[table] = meta
        query = f'CREATE TABLE {table} ({meta.field_types})'
        self.conn.execute(query)
        self.conn.commit()

    def insert_one(self, table, data):
        tbl = self.check_table(table)
        values = '('+'?,'*tbl.field_length
        values = values[:-1]+')'
        query = f'INSERT INTO {table} ({tbl.fields}) VALUES {values}'
        self.conn.execute(query, data)
        self.conn.commit()

    def insert_many(self, table, data):
        tbl = self.check_table(table)
        values = '('+'?,'*tbl.field_length
        values = values[:-1]+')'
        query = f'INSERT INTO {table} ({tbl.fields}) VALUES {values}'
        self.conn.executemany(query, self.list_dict_values(data, tbl.pk))
        self.conn.commit()

    def select_all(self, table, d_type=dict):
        tbl = self.check_table(table)
        query = f'SELECT {tbl.named_fields} FROM {table}'
        return self.query_many(
            query=query,
            param=(),
            d_type=d_type
        )

    def select_one(self, table, value, field=None, fields=None, d_type=dict):
        tbl = self.check_table(table)
        field = field or tbl.pk
        if fields:
            named_fields = [f'{table}.{k}' for k in fields()]
        else:
            named_fields = tbl.named_fields
        query = f'SELECT {named_fields} FROM {table} WHERE {table}.{field}=?'
        return self.query_one(
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
            if k in references:
                rtbl = references[k][0]
                rk = references[k][1]
                rv = references[k][2:]
                rtbl = self.check_table(rtbl)
                if len(rv) == 1:
                    fields.append(f'{rtbl.name}{k}.{rv[0]} AS {k}')
                else:
                    for v in rv:
                        fields.append(f'{tbl.name}.{k}')
                        fields.append(f'{rtbl.name}{k}.{v} AS {k}{v}')
                joins.append(f'{join_mode} JOIN {rtbl.name} AS {rtbl.name}{k} ON {tbl.name}.{k}={rtbl.name}{k}.{rk}')
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
    def __init__(self, database, table, references={}, labeled_fields=[]):
        self.database = database
        self.name = f'View_{table}'
        self.references = references
        for label in labeled_fields:
            self.references[label] = ('TextLabel', '_Id', '_Text')
        self.base_table = table
        self.database.create_view(self.name, self.base_table, self.references)

    def get(self, pk, fields=None, exclude_falsy=True):
        res = self.database.select_one(self.name, pk, fields)
        if exclude_falsy:
            res = dict(filter(lambda x: bool(x[1]), res.items()))
        return res