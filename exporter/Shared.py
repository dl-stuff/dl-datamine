from typing import List, Dict, Any, Callable

from loader.Mappings import ACTION_CONDITION_TYPES, ABILITY_CONDITION_TYPES

class DBView:
    def __init__(self, database, name, labeled_fields=[]):
        self.database = database
        self.tables = {
            name: labeled_fields
        }

    def get(self, key, fields=None, for_display=False):
        return self.database.select_by_pk_labeled(self.tables, key, fields)

class AbilityData(DBView):
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
    SUB_ABILITY_FIELDS = [
        '_AbilityType{i}', 
        '_VariousId{i}a', '_VariousId{i}b', '_VariousId{i}c',
        '_VariousId{i}str',
        '_AbilityLimitedGroupId{i}',
        '_TargetAction{i}',
        '_AbilityType{i}UpValue'
    ]

    def __init__(self, db):
        super().__init__(db, 'AbilityData', ['_Name', '_Details', '_HeadText'])
    
    def get(self, key, fields=None, for_display=False, with_references=True):
        res = super().get(key, fields)
        ref = None
        if not fields:
            for i in (1, 2, 3):
                a_type = res[f'_AbilityType{i}']
                a_ids = [res[f'_VariousId{i}a'], res[f'_VariousId{i}b'], res[f'_VariousId{i}c']]
                a_str = res[f'_VariousId{i}str']
                if for_display:
                    a_dict = {}
                    for k in self.SUB_ABILITY_FIELDS:
                        a_dict[k.format(i='')] = res[k.format(i=i)]
                        del res[k.format(i=i)]
                    if a_type in self.ABILITY_TYPES:
                        a_dict['_Description'] = self.ABILITY_TYPES[a_type](a_ids, a_str)
                    try:
                        res['_Abilities'].append(a_dict)
                    except:
                        res['_Abilities'] = [a_dict]
                if with_references and a_type == self.REF_TYPE:
                    ref = self.get(a_ids[0])
        if isinstance(ref, list):
            return [res, *ref]
        elif ref:
            return [res, ref]
        else:
            return res

class ActionCondition(DBView):
    def __init__(self, db):
        super().__init__(db, 'ActionCondition', ['_Text', '_TextEx'])

    def get(self, key, fields=None, for_display=True, include_filename=True):
        res = super().get(key, fields)
        res['_Type'] = ACTION_CONDITION_TYPES.get(res['_Type'], res['_Type'])
        if for_display:
            res = dict(filter(lambda x: bool(x[1]), res.items()))
        if include_filename:
            ac_id = res['_Id']
            if res['_Type'] != 'Normal':
                res['_Filename'] = f'{ac_id}_{res["_Type"]}'
            elif not res['_Text'].startswith('ACTION_CONDITION'):
                res['_Filename'] = f'{ac_id}_{res["_Text"]}'
            elif res['_EfficacyType'] == 100:
                res['_Filename'] = f'{ac_id}_Dispel'
            else:
                res['_Filename'] = f'{ac_id}'
        return res

class SkillData(DBView):
    def __init__(self, db):
        super().__init__(db, 'SkillData', ['_Name', '_Description1', '_Description2', '_Description3', '_Description4', '_TransText'])