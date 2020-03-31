import sqlite3
import json
import os
from typing import List, Dict, Any, Callable
from Mappings import ACTION_CONDITION_TYPES, ABILITY_CONDITION_TYPES


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

class DBTableMetadata:
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
            tbl = DBTableMetadata(table)
            tbl.init_from_table_info(table_info)
            self.tables[table] = tbl
        return self.tables[table]

    def create_table(self, table, row, pk='_Id'):
        query = f'DROP TABLE IF EXISTS {table}'
        self.conn.execute(query)
        tbl = DBTableMetadata(table, pk=pk)
        tbl.init_from_row(row)
        self.tables[table] = tbl
        query = f'CREATE TABLE {table} ({tbl.field_types})'
        self.conn.execute(query)
        self.conn.commit()

    def insert_many(self, table, data):
        tbl = self.check_table(table)
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
        tbl = self.check_table(table)
        return self.query_many(
            query=self.select_builder(tables={table: tbl.field_type.keys()}),
            param=(),
            d_type=d_type
        )

    def select_by_pk(self, table, pk, fields=None, d_type=dict):
        tbl = self.check_table(table)
        fields = fields or tbl.field_type.keys()
        return self.query_one(
            query=self.select_builder(
                tables={table: fields},
                where=f'{table}.{tbl.pk}=?'
            ),
            param=(pk,),
            d_type=d_type
        )

    def select_by_pk_labeled(self, table, pk, labeled_fields, fields=None, d_type=dict):
        entry = self.select_by_pk(table, pk, fields, d_type)
        for l in labeled_fields:
            try:
                entry[l] = self.select_by_pk('TextLabel', entry[l])['_Text']
            except:
                continue
        return entry


class DBTable:
    def __init__(self, database: DBManager, name, labeled_fields=[]):
        self.name = name
        self.database = database
        self.labeled_fields = labeled_fields

    def get(self, key, fields=None):
        return self.database.select_by_pk_labeled(self.name, key, self.labeled_fields, fields)

class AbilityData(DBTable):
    STAT_ABILITIES = {
        2: 'strength',
        3: 'defense',
        4: 'skill_haste',
        8: 'shapeshift_time',
        10: 'attack_speed',
        12: 'fs_charge_rate'
    }

    ABILITY_TYPES: Dict[int, Callable[[List[int], str], str]] = {
        1: lambda ids, _: AbilityData.STAT_ABILITIES.get(ids[0], f'stat {ids[0]}'),
        2: lambda ids, _: f'affliction_res {ACTION_CONDITION_TYPES.get(ids[0], ids[0])}',
        3: lambda ids, _: f'affliction_proc_rate {ACTION_CONDITION_TYPES.get(ids[0], ids[0])}',
        4: lambda ids, _: f'tribe_res {ids[0]}',
        5: lambda ids, _: f'bane {ids[0]}',
        6: lambda ids, _: 'damage',
        7: lambda ids, _: f'critical_rate',
        8: lambda ids, _: f'recovery_potency',
        9: lambda ids, _: f'gauge_accelerator',
        11: lambda ids, _: f'striking_haste',
        14: lambda ids, _: f'action_condition {[i for i in ids if i]}',
        16: lambda ids, _: f'debuff_chance',
        17: lambda ids, _: f'skill_prep',
        18: lambda ids, _: f'buff_tim',
        20: lambda ids, _: f'punisher {ACTION_CONDITION_TYPES.get(ids[0], ids[0])}',
        21: lambda ids, _: f'player_exp',
        25: lambda ids, _: f'cond_action_grant {ids[0]}',
        26: lambda ids, _: f'critical_damage',
        27: lambda ids, _: f'shapeshift_prep',
        30: lambda ids, _: f'specific_bane {ids[0]}',
        35: lambda ids, _: f'gauge_inhibitor',
        36: lambda ids, _: f'dragon damage',
        39: lambda ids, _: f'action_grant {ids[0]}',
        40: lambda _, s: f'gauge def/skillboost {s}',
        43: lambda ids, _: f'ability_ref {ids[0]}',
        44: lambda ids, _: f'action {ids[0]}',
        48: lambda ids, _: f'dragon_timer_decrease_rate',
        49: lambda ids, _: f'shapeshift_fill',
        51: lambda ids, _: f'random_buff {ids}',
        52: lambda ids, _: f'critical_rate',
        54: lambda _, s: f'combo_dmg_boost {s}',
        55: lambda ids, _: f'combo_time',
    }
    REF_TYPE = 43

    def __init__(self, db):
        super().__init__(db, 'AbilityData', ['_Name', '_Details', '_HeadText'])
    
    def get(self, key, fields=None, with_references=True, with_description=True):
        res = super().get(key, fields)
        ref = None
        if not fields:
            for i in (1, 2, 3):
                a_type = res[f'_AbilityType{i}']
                if with_description and a_type in self.ABILITY_TYPES:
                    a_ids = [res[f'_VariousId{i}a'], res[f'_VariousId{i}b'], res[f'_VariousId{i}c']]
                    a_str = res[f'_VariousId{i}str']
                    res[f'_AbilityDescription{i}'] = self.ABILITY_TYPES[a_type](a_ids, a_str)
                if with_references and a_type == self.REF_TYPE:
                    ref = self.get(res[f'_VariousId{i}a'])
        if isinstance(ref, list):
            return [res, *ref]
        elif ref:
            return [res, ref]
        else:
            return res

if __name__ == '__main__':
    db = DBManager()
    tbl = AbilityData(db)
    res = tbl.get(445)
    for k, v in res.items():
        print(k, v)