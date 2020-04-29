from typing import List, Dict, Any, Callable
import json
import re
import os
import errno
from collections import defaultdict

from loader.Database import DBViewIndex, DBManager, DBView, DBDict, check_target_path
from loader.Actions import CommandType
from exporter.Mappings import AFFLICTION_TYPES, ABILITY_CONDITION_TYPES, KILLER_STATE

def get_valid_filename(s):
    return re.sub(r'(?u)[^-\w. ]', '', s)

class ActionCondition(DBView):
    def __init__(self, index):
        super().__init__(index, 'ActionCondition', labeled_fields=['_Text', '_TextEx'])
        self.get_skills = True

    def process_result(self, res, exclude_falsy=True):
        if '_Type' in res:
            res['_Type'] = AFFLICTION_TYPES.get(res['_Type'], res['_Type'])
        if '_EnhancedBurstAttack' in res and res['_EnhancedBurstAttack']:
            res['_EnhancedBurstAttack'] = self.index['PlayerAction'].get(res['_EnhancedBurstAttack'], exclude_falsy=exclude_falsy, burst_action=True)
        if self.get_skills:
            for s in ('_EnhancedSkill1', '_EnhancedSkill2', '_EnhancedSkillWeapon'):
                if s in res and res[s]:
                    self.get_skills = False
                    skill = self.index['SkillData'].get(res[s], exclude_falsy=exclude_falsy)
                    if skill:
                        res[s] = skill
                    self.get_skills = True
        return res

    def get(self, key, fields=None, exclude_falsy=True):
        res = super().get(key, fields=fields, exclude_falsy=exclude_falsy)
        return self.process_result(res, exclude_falsy=exclude_falsy)

    def export_all_to_folder(self, out_dir='./out', ext='.json', exclude_falsy=True):
        # super().export_all_to_folder(out_dir, ext, fn_mode='a', exclude_falsy=exclude_falsy, full_actions=False)
        out_dir = os.path.join(out_dir, '_act_cond')
        all_res = self.get_all(exclude_falsy=exclude_falsy)
        check_target_path(out_dir)
        sorted_res = defaultdict(lambda: [])
        for res in all_res:
            res = self.process_result(res, exclude_falsy=exclude_falsy)
            try:
                sorted_res[int(res['_Id'] / 100000000)].append(res)
            except:
                sorted_res[0].append(res)
        for group_name, res_list in sorted_res.items():
            out_name = get_valid_filename(f'{group_name}00000000{ext}')
            output = os.path.join(out_dir, out_name)
            with open(output, 'w', newline='', encoding='utf-8') as fp:
                json.dump(res_list, fp, indent=2, ensure_ascii=False)

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
        2: lambda ids, _: f'affliction_res {AFFLICTION_TYPES.get(ids[0], ids[0])}',
        3: lambda ids, _: f'affliction_proc_rate {AFFLICTION_TYPES.get(ids[0], ids[0])}',
        4: lambda ids, _: f'tribe_res {ids}',
        5: lambda ids, _: f'bane {ids}',
        6: lambda ids, _: 'damage',
        7: lambda ids, _: f'critical_rate',
        8: lambda ids, _: f'recovery_potency',
        9: lambda ids, _: f'gauge_accelerator',
        11: lambda ids, _: f'striking_haste',
        14: lambda ids, s: f'action_condition {ids, s}',
        16: lambda ids, _: f'debuff_chance',
        17: lambda ids, _: f'skill_prep',
        18: lambda ids, _: f'buff_tim',
        20: lambda ids, _: f'punisher {AFFLICTION_TYPES.get(ids[0], ids[0])}',
        21: lambda ids, _: f'player_exp',
        25: lambda ids, _: f'cond_action_grant {ids}',
        26: lambda ids, _: f'critical_damage',
        27: lambda ids, _: f'shapeshift_prep',
        30: lambda ids, _: f'specific_bane {ids}',
        35: lambda ids, _: f'gauge_inhibitor',
        36: lambda ids, _: f'dragon_damage',
        39: lambda ids, _: f'action_grant {ids}',
        40: lambda _, s: f'gauge_def/skillboost {s}',
        43: lambda ids, _: f'ability_ref {ids}',
        44: lambda ids, _: f'action {ids}',
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

    def __init__(self, index):
        super().__init__(index, 'AbilityData', labeled_fields=['_Name', '_Details', '_HeadText'])
    
    def process_result(self, ability_data, fields=None, full_query=True, exclude_falsy=True):
        try:
            ability_data['_ConditionType'] = ABILITY_CONDITION_TYPES.get(ability_data['_ConditionType'], ability_data['_ConditionType'])
        except:
            pass
        for i in (1, 2, 3):
            if f'_AbilityType{i}' in ability_data and ability_data[f'_AbilityType{i}']:
                a_type = ability_data[f'_AbilityType{i}']
                a_ids = {f'_VariousId{i}{a}': ability_data[f'_VariousId{i}{a}'] for a in ('a', 'b', 'c') if f'_VariousId{i}{a}' in ability_data and ability_data[f'_VariousId{i}{a}']}
                if f'_VariousId{i}' in ability_data and ability_data[f'_VariousId{i}']:
                    a_ids[f'_VariousId{i}'] = ability_data[f'_VariousId{i}']
                a_str = ability_data.get(f'_VariousId{i}str', None)
                if a_type in self.ABILITY_TYPES:
                    ability_data[f'_Description{i}'] = self.ABILITY_TYPES[a_type](list(a_ids.values()), a_str)
                if full_query:
                    for ak, value in a_ids.items():
                        if a_type == self.REF_TYPE:
                            ability_data[ak] = self.get(value, fields=fields, full_query=True, exclude_falsy=exclude_falsy)
                        elif a_type == self.ACT_COND_TYPE:
                            ability_data[ak] = self.index['ActionCondition'].get(value, exclude_falsy=exclude_falsy)
                    if a_type == self.ACT_COND_TYPE and a_str:
                        ak = f'_VariousId{i}str'
                        ability_data[ak] = self.index['PlayerActionHitAttribute'].get(ability_data[ak], by='_Id', exclude_falsy=exclude_falsy)
        return ability_data

    def get(self, key, fields=None, full_query=True, exclude_falsy=True):
        ability_data = super().get(key, fields=fields, exclude_falsy=exclude_falsy)
        if not full_query:
            return ability_data
        return self.process_result(ability_data, fields, full_query, exclude_falsy)

class PlayerActionHitAttribute(DBView):
    def __init__(self, index):
        super().__init__(index, 'PlayerActionHitAttribute')

    def process_result(self, res, exclude_falsy=True):
        res_list = [res] if isinstance(res, dict) else res
        for r in res_list:
            if '_ActionCondition1' in r and r['_ActionCondition1']:
                act_cond = self.index['ActionCondition'].get(r['_ActionCondition1'], exclude_falsy=exclude_falsy)
                if act_cond:
                    r['_ActionCondition1'] = act_cond
            for ks in ('_KillerState1', '_KillerState2', '_KillerState3'):
                if ks in r and r[ks] in KILLER_STATE:
                    r[ks] = KILLER_STATE[r[ks]]
        return res

    def get(self, pk, by=None, fields=None, order=None, mode=DBManager.EXACT, exclude_falsy=False):
        res = super().get(pk, by, fields, order, mode, exclude_falsy)
        return self.process_result(res, exclude_falsy=exclude_falsy)
        
    def export_all_to_folder(self, out_dir='./out', ext='.json', exclude_falsy=True):
        # super().export_all_to_folder(out_dir, ext, fn_mode='a', exclude_falsy=exclude_falsy, full_actions=False)
        out_dir = os.path.join(out_dir, '_hit_attr')
        all_res = self.get_all(exclude_falsy=exclude_falsy)
        check_target_path(out_dir)
        sorted_res = defaultdict(lambda: [])
        for res in all_res:
            res = self.process_result(res, exclude_falsy=exclude_falsy)
            try:
                k1, _ = res['_Id'].split('_', 1)
                sorted_res[k1].append(res)
            except:
                sorted_res[res['_Id']].append(res)
        for group_name, res_list in sorted_res.items():
            out_name = get_valid_filename(f'{group_name}{ext}')
            output = os.path.join(out_dir, out_name)
            with open(output, 'w', newline='', encoding='utf-8') as fp:
                json.dump(res_list, fp, indent=2, ensure_ascii=False)


class CharacterMotion(DBView):
    def __init__(self, index):
        super().__init__(index, 'CharacterMotion')

    def get_by_state_ref(self, state, ref, exclude_falsy=True):
        tbl = self.database.check_table(self.name)
        query = f'SELECT {tbl.named_fields} FROM {self.name} WHERE {self.name}.state=? AND {self.name}.ref=?;'
        return self.database.query_many(
            query=query,
            param=(state,ref),
            d_type=DBDict
        )


class ActionParts(DBView):
    LV_SUFFIX = re.compile(r'(.*LV)(\d{2})')
    HIT_LABELS = ['_hitLabel', '_hitAttrLabel', '_abHitAttrLabel']
    BURST_ATK_DISPLACEMENT = 5
    def __init__(self, index):
        super().__init__(index, 'ActionParts')
        self.animation_reference = None

    def get_burst_action_parts(self, pk, fields=None, exclude_falsy=True, hide_ref=False):
        sub_parts = super().get((pk, pk+self.BURST_ATK_DISPLACEMENT), by='_ref', fields=fields, order='_ref ASC', mode=DBManager.RANGE, exclude_falsy=exclude_falsy)
        return self.process_result(sub_parts, exclude_falsy=exclude_falsy, hide_ref=hide_ref)

    def process_result(self, action_parts, exclude_falsy=True, hide_ref=True):
        if isinstance(action_parts, dict):
            action_parts = [action_parts]
        for r in action_parts:
            if 'commandType' in r:
                r['commandType'] = CommandType(r['commandType']).name
            del r['_Id']
            if hide_ref:
                del r['_ref']

            for label in self.HIT_LABELS:
                if label not in r or not r[label]:
                    continue
                res = self.LV_SUFFIX.match(r[label])
                if res:
                    base_label, _ = res.groups()
                    hit_attrs = self.index['PlayerActionHitAttribute'].get(base_label, by='_Id', order='_Id ASC', mode=DBManager.LIKE, exclude_falsy=exclude_falsy)
                    if hit_attrs:
                        r[label] = hit_attrs
                else:
                    hit_attr = self.index['PlayerActionHitAttribute'].get(r[label], by='_Id', exclude_falsy=exclude_falsy)
                    if hit_attr:
                        r[label] = hit_attr

            if '_actionConditionId' in r and r['_actionConditionId']:
                r['_actionConditionId'] = self.index['ActionCondition'].get(r['_actionConditionId'], exclude_falsy=exclude_falsy)

            if '_motionState' in r and r['_motionState']:
                ms = r['_motionState']
                animation = []
                if self.animation_reference is not None:
                    animation = self.index[self.animation_reference[0]].get_by_state_ref(ms, self.animation_reference[1], exclude_falsy=exclude_falsy)
                if not animation:
                    animation = self.index['CharacterMotion'].get(ms, exclude_falsy=exclude_falsy)
                if animation:
                    r['_animation'] = animation

        return action_parts

    def get(self, pk, by=None, fields=None, order=None, mode=DBManager.EXACT, exclude_falsy=True, hide_ref=True):
        action_parts = super().get(pk, by=by, fields=fields, order=order, mode=mode, exclude_falsy=exclude_falsy)
        return self.process_result(action_parts, exclude_falsy=exclude_falsy, hide_ref=hide_ref)

    @staticmethod
    def remove_falsy_fields(res):
        return DBDict(filter(lambda x: bool(x[1]) or x[0] in ('_seconds', '_seq'), res.items()))

class PlayerAction(DBView):
    def __init__(self, index):
        super().__init__(index, 'PlayerAction')

    def process_result(self, player_action, exclude_falsy=True, full_query=True, burst_action=False):
        pa_id = player_action['_Id']
        if burst_action:
            action_parts = self.index['ActionParts'].get_burst_action_parts(pa_id, exclude_falsy=exclude_falsy)
        else:
            action_parts = self.index['ActionParts'].get(pa_id, by='_ref', order='_seq ASC', exclude_falsy=exclude_falsy)
        if action_parts:
            player_action['_Parts'] = action_parts
        return player_action

    def get(self, pk, fields=None, exclude_falsy=True, full_query=True, burst_action=False):
        player_action = super().get(pk, fields=fields, exclude_falsy=exclude_falsy)
        if not full_query or not player_action:
            return player_action
        return self.process_result(player_action, exclude_falsy=exclude_falsy, full_query=full_query, burst_action=burst_action)

    def export_all_to_folder(self, out_dir='./out', ext='.json', exclude_falsy=True):
        # super().export_all_to_folder(out_dir, ext, fn_mode='a', exclude_falsy=exclude_falsy, full_actions=False)
        out_dir = os.path.join(out_dir, '_actions')
        all_res = self.get_all(exclude_falsy=exclude_falsy)
        check_target_path(out_dir)
        sorted_res = defaultdict(lambda: [])
        for res in all_res:
            res = self.process_result(res, exclude_falsy=exclude_falsy)
            try:
                k1, _ = res['_ActionName'].split('_', 1)
                if k1[0] == 'D' and k1 != 'DAG':
                    k1 = 'DRAGON'
                sorted_res[k1].append(res)
            except:
                sorted_res[res['_ActionName']].append(res)
        for group_name, res_list in sorted_res.items():
            out_name = get_valid_filename(f'{group_name}{ext}')
            output = os.path.join(out_dir, out_name)
            with open(output, 'w', newline='', encoding='utf-8') as fp:
                json.dump(res_list, fp, indent=2, ensure_ascii=False)

class SkillChainData(DBView):
    def __init__(self, index):
        super().__init__(index, 'SkillChainData')

class SkillData(DBView):
    TRANS_PREFIX = '_Trans'
    def __init__(self, index):
        super().__init__(index, 'SkillData', labeled_fields=['_Name', '_Description1', '_Description2', '_Description3', '_Description4', '_TransText'])

    @staticmethod
    def get_all_from(view, prefix, data, **kargs):
        for i in range(1, 5):
            a_id = f'{prefix}{i}'
            if a_id in data and data[a_id]:
                data[a_id] = view.get(data[a_id], **kargs)
        return data

    @staticmethod
    def get_last_from(view, prefix, data, **kargs):
        i = 4
        a_id = f'{prefix}{i}'
        while i > 0 and (not a_id in data or not data[a_id]):
            i -= 1
            a_id = f'{prefix}{i}'
        if i > 0:
            data[a_id] = view.get(data[a_id], **kargs)
        return data

    def process_result(self, skill_data, exclude_falsy=True, 
        full_query=True, full_abilities=False, full_transSkill=True):
        if not full_query:
            return skill_data
        # Actions
        skill_data = self.get_all_from(self.index['PlayerAction'], '_ActionId', skill_data, exclude_falsy=exclude_falsy)
        if '_AdvancedSkillLv1' in skill_data and skill_data['_AdvancedSkillLv1'] and (adv_act := self.index['PlayerAction'].get(skill_data['_AdvancedActionId1'], exclude_falsy=exclude_falsy)):
            skill_data['_AdvancedActionId1'] = adv_act

        # Abilities
        if full_abilities:
            skill_data = self.get_all_from(self.index['AbilityData'], '_Ability', skill_data, exclude_falsy=exclude_falsy)
        else:
            skill_data = self.get_last_from(self.index['AbilityData'], '_Ability', skill_data, exclude_falsy=exclude_falsy)
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
            skill_data['_ChainGroupId'] = self.index['SkillChainData'].get(skill_data['_ChainGroupId'], by='_GroupId', exclude_falsy=exclude_falsy)
        return skill_data

    def get(self, pk, fields=None, exclude_falsy=True, 
        full_query=True, full_abilities=False, full_transSkill=True):
        skill_data = super().get(pk, fields=fields, exclude_falsy=exclude_falsy)
        return self.process_result(skill_data, exclude_falsy=exclude_falsy, 
        full_query=full_query, full_abilities=full_abilities, full_transSkill=full_transSkill)

if __name__ == '__main__':
    index = DBViewIndex()
    view = SkillData(index)
    test = view.get(106505012)
    print(test)