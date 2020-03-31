import sqlite3
import json
import os

MASTER = ['AbilityData',
'AbilityGroup',
'AbilityLimitedGroup',
'AbilityShiftGroup',
'AbnormalStatusType',
'ActionCollision',
'ActionCondition',
'ActionGrant',
'ActionMarker',
'ActionTarget',
'AmuletData',
'AmuletLevel',
'AmuletLimitBreak',
'AmuletRarity',
'AmuletTrade',
'CharaAIOperation',
'CharaAIParam',
'CharaData',
'CharaLevel',
'CharaLimitBreak',
'CharaModeData',
'CharaRarity',
'CharaUniqueCombo',
'CommonAction',
'CommonActionHitAttribute',
'CommonReportCategory',
'DamageDamping',
'DragonData',
'DragonDecoration',
'DragonGiftData',
'DragonLevel',
'DragonLimitBreak',
'DragonRarity',
'DragonReliabilityLevel',
'DragonTalk',
'ElementalType',
'ExAbilityData',
'MC',
'PlayerAction',
'PlayerActionHitAttribute',
'PlayerBulletData',
'RemoveBuffAction',
'SkillChainData',
'SkillData',
'TextLabel',
'WeaponData',
'WeaponLevel',
'WeaponLimitBreak',
'WeaponRarity',
'WeaponType',]

class DBTable:
    def __init__(self, name, pk='_Id'):
        self.name = name
        self.pk = pk
        self.field_type = {}

    def init_from_row(self, row):
        for k, v in row.items():
            if isinstance(v, int):
                self.field_type[k] = 'INTEGER'
            elif isinstance(v, float):
                self.field_type[k] = 'REAL'
            elif isinstance(v, str):
                self.field_type[k] = 'TEXT'
            else:
                self.field_type[k] = 'BLOB'
            if k == self.pk:
                self.field_type[k] += ' PRIMARY KEY'

    def init_from_table_info(self, table_info):
        for c in table_info:
            if c['pk'] == 1:
                self.pk = c['name']
            self.field_type[c['name']] = c['type']

    @property
    def fields(self):
        return ','.join(self.field_type.keys())

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
    def select_builder(tables, key=None, where=None, order=None, distinct=False):
        if distinct:
            SELECT_FROM = 'SELECT DISTINCT {fields} FROM {first_table}'
        else:
            SELECT_FROM = 'SELECT {fields} FROM {first_table}'
        WHERE = 'WHERE {condition}'
        JOIN = 'LEFT JOIN {other_table} ON {first_table}.{key}={other_table}.{key}'
        ORDER = 'ORDER BY {order}'
        first_table = None
        fields_lst = []
        other_tables = []
        for table, fields in tables.items():
            if fields is not None:
                fields_lst.extend(['{}.{}'.format(table, f) for f in fields])
            if first_table is None:
                first_table = table
                if key is None:
                    break
            else:
                other_tables.append(table)
        query = [SELECT_FROM.format(first_table=first_table, fields=', '.join(fields_lst))]
        prev_table = first_table
        if key:
            for k, other in zip(key, other_tables):
                query.append(JOIN.format(first_table=prev_table, other_table=other, key=k))
                prev_table = other
        if where:
            query.append(WHERE.format(condition=where))
        if order:
            query.append(ORDER.format(order=order))
        return ' '.join(query)

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
            tbl = DBTable(table)
            tbl.init_from_table_info(table_info)
            self.tables[table] = tbl

    def create_table(self, table, row, pk='_Id'):
        query = f'DROP TABLE IF EXISTS {table}'
        self.conn.execute(query)
        tbl = DBTable(table, pk=pk)
        tbl.init_from_row(row)
        self.tables[table] = tbl
        query = f'CREATE TABLE {table} ({tbl.field_types})'
        self.conn.execute(query)
        self.conn.commit()

    def insert_many(self, table, data):
        tbl = self.tables[table]
        values = '('+'?,'*tbl.field_length
        values = values[:-1]+')'
        query = f'INSERT INTO {table} ({tbl.fields}) VALUES {values}'
        self.conn.executemany(query, self.list_dict_values(data, tbl.pk))
        self.conn.commit()

    def load_table_from_json(self, path):
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
            self.create_table(table, row, pk)
            self.insert_many(table, data.values())

    def load_master(self, path):
        for root, _, files in os.walk(path):
            for f in files:
                self.load_table_from_json(os.path.join(root, f))

    def select_all(self, table, d_type=dict):
        return self.query_many(
            query=self.select_builder(tables={table: self.tables[table].field_type.keys()}),
            param=(),
            d_type=d_type
        )

    def select_by_pk(self, table, pk, d_type=dict):
        tbl = self.tables[table]
        return self.query_one(
            query=self.select_builder(
                tables={table: tbl.field_type.keys()},
                where=f'{table}.{tbl.pk}=?'
            ),
            param=(pk,),
            d_type=d_type
        )


if __name__ == '__main__':
    db = DBManager()
    db.load_master('./extract/master')
    