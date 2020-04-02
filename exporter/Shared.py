from typing import List, Dict, Any, Callable
import re
import os
import errno

from loader.Database import DBManager, DBView, DBDict
from loader.Actions import CommandType
from exporter.Mappings import ACTION_CONDITION_TYPES, ABILITY_CONDITION_TYPES

def check_target_path(target):
    if not os.path.exists(target):
        try:
            os.makedirs(target)
        except OSError as exc: # Guard against race condition
            if exc.errno != errno.EEXIST:
                raise

class ActionCondition(DBView):
    def __init__(self, db):
        super().__init__(db, 'ActionCondition', labeled_fields=['_Text', '_TextEx'])

    def get(self, key, fields=None, exclude_falsy=True):
        res = super().get(key, fields=fields, exclude_falsy=exclude_falsy)
        try:
            res['_Type'] = ACTION_CONDITION_TYPES.get(res['_Type'], res['_Type'])
        except:
            pass
        return res


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
        43: lambda ids, _: f'ability_ref {0 if not ids else ids[0]}',
        44: lambda ids, _: f'action {ids[0]}',
        48: lambda ids, _: f'dragon_timer_decrease_rate',
        49: lambda ids, _: f'shapeshift_fill',
        51: lambda ids, _: f'random_buff {ids}',
        52: lambda ids, _: f'critical_rate',
        54: lambda _, s: f'combo_dmg_boost {s}',
        55: lambda ids, _: f'combo_time',
    }
    ACT_COND_TYPE = 14
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
        super().__init__(db, 'AbilityData', labeled_fields=['_Name', '_Details', '_HeadText'])
        self.action_condition = ActionCondition(db)
    
    def get(self, key, fields=None, full_query=True, exclude_falsy=True):
        ability_data = super().get(key, fields=fields, exclude_falsy=exclude_falsy)
        try:
            ability_data['_ConditionType'] = ABILITY_CONDITION_TYPES.get(ability_data['_ConditionType'], ability_data['_ConditionType'])
        except:
            pass
        if not fields:
            for i in (1, 2, 3):
                if f'_AbilityType{i}' in ability_data and ability_data[f'_AbilityType{i}']:
                    a_type = ability_data[f'_AbilityType{i}']
                    a_ids = {f'_VariousId{i}{a}': ability_data[f'_VariousId{i}{a}'] for a in ('a', 'b', 'c') if f'_VariousId{i}{a}' in ability_data and ability_data[f'_VariousId{i}{a}']}
                    a_str = ability_data.get(f'_VariousId{i}str', None)
                    if a_type in self.ABILITY_TYPES:
                        ability_data[f'_Description{i}'] = self.ABILITY_TYPES[a_type](list(a_ids.values()), a_str)
                    if full_query:
                        for ak, value in a_ids.items():
                            if a_type == self.REF_TYPE:
                                ability_data[ak] = self.get(value, fields=fields, full_query=True, exclude_falsy=exclude_falsy)
                            elif a_type == self.ACT_COND_TYPE:
                                ability_data[ak] = self.action_condition.get(value, exclude_falsy=exclude_falsy)
        return ability_data

class ActionParts(DBView):
    def __init__(self, db):
        super().__init__(db, 'ActionParts')

    def get(self, pk, by=None, fields=None, order=None, mode=DBManager.EXACT, exclude_falsy=False, hide_ref=True):
        res = super().get(pk, by=by, fields=fields, order=order, mode=mode, exclude_falsy=exclude_falsy)
        for r in res:
            if 'commandType' in r:
                r['commandType'] = CommandType(r['commandType']).name
            if hide_ref:
                del r['_Id']
                del r['_ref']
                try:
                    del r['_seq']
                except:
                    pass
        return res

    @staticmethod
    def remove_falsy_fields(res):
        return DBDict(filter(lambda x: bool(x[1]) or x[0] == '_seconds', res.items()))

class PlayerActionHitAttribute(DBView):
    def __init__(self, db):
        super().__init__(db, 'PlayerActionHitAttribute')

class PlayerAction(DBView):
    LV_SUFFIX = re.compile(r'(.*)(LV\d{2})')
    HIT_LABELS = ['_hitLabel', '_hitAttrLabel', '_abHitAttrLabel']
    def __init__(self, db):
        super().__init__(db, 'PlayerAction')
        self.parts = ActionParts(db)
        self.attrs = PlayerActionHitAttribute(db)

    def get(self, pk, fields=None, exclude_falsy=True, full_query=True, full_hitattr=False):
        player_action = super().get(pk, fields=fields, exclude_falsy=exclude_falsy)
        if not full_query:
            return player_action
        if not player_action:
            return False
        pa_id = player_action['_Id']
        action_parts = self.parts.get(pa_id, by='_ref', order='_seq ASC', exclude_falsy=exclude_falsy)
        for ap in action_parts:
            for label in self.HIT_LABELS:
                if label in ap and ap[label]:
                    res = self.LV_SUFFIX.match(ap[label])
                    if res:
                        base_label, _ = res.groups()
                        hit_attrs = self.attrs.get(base_label, by='_Id', order='_Id DESC', mode=DBManager.LIKE, exclude_falsy=exclude_falsy)
                        if hit_attrs:
                            if isinstance(hit_attrs, dict) or full_hitattr:
                                ap[label] = hit_attrs
                            elif len(hit_attrs) > 0:
                                ap[label] = hit_attrs[0]
                    else:
                        ap[label] = self.attrs.get(ap[label], by='_Id', exclude_falsy=exclude_falsy)
        player_action['_Parts'] = action_parts
        return player_action

class SkillChainData(DBView):
    def __init__(self, db):
        super().__init__(db, 'SkillChainData')

class SkillData(DBView):
    TRANS_PREFIX = '_Trans'
    def __init__(self, db):
        super().__init__(db, 'SkillData', labeled_fields=['_Name', '_Description1', '_Description2', '_Description3', '_Description4', '_TransText'])
        self.actions = PlayerAction(db)
        self.abilities = AbilityData(db)
        self.chain_group = SkillChainData(db)

    @staticmethod
    def get_all(view, prefix, data, **kargs):
        for i in range(1, 5):
            a_id = f'{prefix}{i}'
            if a_id in data and data[a_id]:
                data[a_id] = view.get(data[a_id], **kargs)
        return data

    @staticmethod
    def get_last(view, prefix, data, **kargs):
        i = 4
        a_id = f'{prefix}{i}'
        while i > 0 and (not a_id in data or not data[a_id]):
            i -= 1
            a_id = f'{prefix}{i}'
        if i > 0:
            data[a_id] = view.get(data[a_id], **kargs)
        return data

    def get(self, pk, fields=None, exclude_falsy=True, 
            full_query=True, full_abilities=False, full_transSkill=True,
            full_hitattr=False):
        skill_data = super().get(pk, fields=fields, exclude_falsy=exclude_falsy)
        if not full_query:
            return skill_data
        # Actions
        skill_data = self.get_all(self.actions, '_ActionId', skill_data, exclude_falsy=exclude_falsy, full_hitattr=full_hitattr)
        if '_AdvancedSkillLv1' in skill_data and skill_data['_AdvancedSkillLv1']:
            skill_data['_AdvancedActionId1'] = (self.actions.get(skill_data['_AdvancedActionId1'], exclude_falsy=exclude_falsy, full_hitattr=full_hitattr))
        # Abilities
        if full_abilities:
            skill_data = self.get_all(self.abilities, '_Ability', skill_data, exclude_falsy=exclude_falsy)
        else:
            skill_data = self.get_last(self.abilities, '_Ability', skill_data, exclude_falsy=exclude_falsy)
        if full_transSkill and '_TransSkill' in skill_data and skill_data['_TransSkill']:
            next_trans_skill = self.get(skill_data['_TransSkill'], exclude_falsy=exclude_falsy, full_query=full_query, full_abilities=full_abilities, full_transSkill=False)
            trans_skill_group = {
                skill_data['_Id']: None,
                next_trans_skill['_Id']: next_trans_skill
            }
            while next_trans_skill['_TransSkill'] != skill_data['_Id']:
                next_trans_skill = self.get(next_trans_skill['_TransSkill'], exclude_falsy=exclude_falsy, full_query=full_query, full_abilities=full_abilities, full_transSkill=False)
                trans_skill_group[next_trans_skill['_Id']] = next_trans_skill
            skill_data['_TransSkill'] = trans_skill_group
        # ChainGroupId
        if '_ChainGroupId' in skill_data and skill_data['_ChainGroupId']:
            skill_data['_ChainGroupId'] = self.chain_group.get(skill_data['_ChainGroupId'], by='_GroupId', exclude_falsy=exclude_falsy)
        return skill_data