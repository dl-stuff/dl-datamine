from typing import List, Dict, Any, Callable
import json
import re
import os
import errno
from collections import defaultdict
from tqdm import tqdm

from loader.Database import DBViewIndex, DBManager, DBView, DBDict, check_target_path
from loader.Actions import CommandType
from exporter.Mappings import AFFLICTION_TYPES, ABILITY_CONDITION_TYPES, KILLER_STATE, TRIBE_TYPES, TARGET_ACTION_TYPES, ELEMENTS


def get_valid_filename(s):
    return re.sub(r'(?u)[^-\w. ]', '', s)


class ActionCondition(DBView):
    def __init__(self, index):
        super().__init__(index, 'ActionCondition',
                         labeled_fields=['_Text', '_TextEx'])
        self.seen_skills = set()

    def process_result(self, res, exclude_falsy=True):
        if '_Type' in res:
            res['_Type'] = AFFLICTION_TYPES.get(res['_Type'], res['_Type'])
        if '_EnhancedBurstAttack' in res and res['_EnhancedBurstAttack']:
            res['_EnhancedBurstAttack'] = self.index['PlayerAction'].get(
                res['_EnhancedBurstAttack'], exclude_falsy=exclude_falsy)
        if '_AdditionAttack' in res and res['_AdditionAttack']:
            res['_AdditionAttack'] = self.index['PlayerActionHitAttribute'].get(
                res['_AdditionAttack'], exclude_falsy=exclude_falsy)
        reset_seen_skills = len(self.seen_skills) == 0
        if res['_Id'] not in self.seen_skills:
            self.seen_skills.add(res['_Id'])
            for s in ('_EnhancedSkill1', '_EnhancedSkill2', '_EnhancedSkillWeapon'):
                if s in res and res[s] and res[s] not in self.seen_skills:
                    skill = self.index['SkillData'].get(
                        res[s], exclude_falsy=exclude_falsy)
                    if skill:
                        res[s] = skill
        if reset_seen_skills:
            self.seen_skills = set()
        return res

    def get(self, key, fields=None, exclude_falsy=True):
        res = super().get(key, fields=fields, exclude_falsy=exclude_falsy)
        if not res:
            return None
        return self.process_result(res, exclude_falsy=exclude_falsy)

    def export_all_to_folder(self, out_dir='./out', ext='.json', exclude_falsy=True):
        # super().export_all_to_folder(out_dir, ext, fn_mode='a', exclude_falsy=exclude_falsy, full_actions=False)
        out_dir = os.path.join(out_dir, '_act_cond')
        all_res = self.get_all(exclude_falsy=exclude_falsy)
        check_target_path(out_dir)
        sorted_res = defaultdict(lambda: [])
        for res in tqdm(all_res, desc='_act_cond'):
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


class ActionGrant(DBView):
    def __init__(self, index):
        super().__init__(index, 'ActionGrant')

    def process_result(self, res, exclude_falsy=True):
        res['_TargetAction'] = TARGET_ACTION_TYPES.get(
            res['_TargetAction'], res['_TargetAction'])
        grant_cond = self.index['ActionCondition'].get(
            res['_GrantCondition'], exclude_falsy=exclude_falsy)
        if grant_cond:
            res['_GrantCondition'] = grant_cond
        return res

    def get(self, pk, by=None, fields=None, order=None, exclude_falsy=False):
        res = super().get(pk, by=by, fields=fields, order=order, exclude_falsy=exclude_falsy)
        return self.process_result(res, exclude_falsy=exclude_falsy)


class AbilityData(DBView):
    STAT_ABILITIES = {
        2: 'strength',
        3: 'defense',
        4: 'skill haste',
        5: 'dragon haste',
        8: 'shapeshift time',
        10: 'attack speed',
        12: 'fs charge rate'
    }

    @staticmethod
    def a_ids(res, i):
        a_ids = [res[f'_VariousId{i}{a}'] for a in (
            'a', 'b', 'c', '') if f'_VariousId{i}{a}' in res and res[f'_VariousId{i}{a}']]
        return a_ids

    @staticmethod
    def a_str(res, i):
        return res.get(f'_VariousId{i}str', None)

    @staticmethod
    def generic_description(name):
        def f(ad, res, i):
            a_ids = AbilityData.a_ids(res, i)
            a_str = AbilityData.a_str(res, i)
            if a_ids or a_str:
                res[f'_Description{i}'] = f'{name} {a_ids, a_str}'
            else:
                res[f'_Description{i}'] = name
            return res
        return f

    @staticmethod
    def link_various_ids(ad, res, i, view='ActionCondition'):
        a_ids = []
        for a in ('a', 'b', 'c', ''):
            key = f'_VariousId{i}{a}'
            if key in res and res[key]:
                a_ids.append(res[key])
                res[key] = ad.index[view].get(res[key], exclude_falsy=True)
        return res, a_ids

    @staticmethod
    def link_various_str(ad, res, i, view='PlayerActionHitAttribute'):
        a_str = None
        key = f'_VariousId{i}str'
        if key in res and res[key]:
            a_str = res[key]
            res[key] = ad.index[view].get(
                res[key], by='_Id', exclude_falsy=True)
        return res, a_str

    @staticmethod
    def stat_ability(ad, res, i):
        a_id = AbilityData.a_ids(res, i)[0]
        res[f'_Description{i}'] = f'stat {AbilityData.STAT_ABILITIES.get(a_id, a_id)}'
        return res

    @staticmethod
    def affliction_resist(ad, res, i):
        a_id = AbilityData.a_ids(res, i)[0]
        res[f'_Description{i}'] = f'affliction resist {AFFLICTION_TYPES.get(a_id, a_id)}'
        return res

    @staticmethod
    def affliction_proc_rate(ad, res, i):
        a_id = AbilityData.a_ids(res, i)[0]
        res[f'_Description{i}'] = f'affliction proc rate {AFFLICTION_TYPES.get(a_id, a_id)}'
        return res

    @staticmethod
    def tribe_resist(ad, res, i):
        a_id = AbilityData.a_ids(res, i)[0]
        res[f'_Description{i}'] = f'tribe resist {TRIBE_TYPES.get(a_id, a_id)}'
        return res

    @staticmethod
    def tribe_bane(ad, res, i):
        a_id = AbilityData.a_ids(res, i)[0]
        res[f'_Description{i}'] = f'tribe bane {TRIBE_TYPES.get(a_id, a_id)}'
        return res

    @staticmethod
    def action_condition(ad, res, i):
        res, a_ids = AbilityData.link_various_ids(ad, res, i)
        res, a_str = AbilityData.link_various_str(ad, res, i)
        res[f'_Description{i}'] = f'action condition {a_ids, a_str}'
        return res

    @staticmethod
    def affliction_punisher(ad, res, i):
        a_id = AbilityData.a_ids(res, i)[0]
        res[f'_Description{i}'] = f'affliction punisher {AFFLICTION_TYPES.get(a_id, a_id)}'
        return res

    @staticmethod
    def conditional_action_grant(ad, res, i):
        res, a_ids = AbilityData.link_various_ids(
            ad, res, i, view='ActionGrant')
        res[f'_Description{i}'] = f'conditional action grant {a_ids}'
        return res

    @staticmethod
    def elemental_resist(ad, res, i):
        a_id = AbilityData.a_ids(res, i)[0]
        res[f'_Description{i}'] = f'elemental resist {ELEMENTS.get(a_id, a_id)}'
        return res

    @staticmethod
    def action_grant(ad, res, i):
        res, a_ids = AbilityData.link_various_ids(
            ad, res, i, view='ActionGrant')
        res[f'_Description{i}'] = f'action grant {a_ids}'
        return res

    @staticmethod
    def ability_reference(ad, res, i):
        res, a_ids = AbilityData.link_various_ids(
            ad, res, i, view='AbilityData')
        res[f'_Description{i}'] = f'ability reference {a_ids}'
        return res

    @staticmethod
    def skill_reference(ad, res, i):
        res, a_ids = AbilityData.link_various_ids(
            ad, res, i, view='SkillData')
        res[f'_Description{i}'] = f'skill reference {a_ids}'
        return res

    @staticmethod
    def action_reference(ad, res, i):
        res, a_ids = AbilityData.link_various_ids(
            ad, res, i, view='PlayerAction')
        res[f'_Description{i}'] = f'action reference {a_ids}'
        return res

    @staticmethod
    def random_action_condition(ad, res, i):
        res, a_ids = AbilityData.link_various_ids(ad, res, i)
        res, a_str = AbilityData.link_various_str(ad, res, i)
        res[f'_Description{i}'] = f'random action condition {a_ids, a_str}'
        return res

    @staticmethod
    def elemental_damage(ad, res, i):
        a_id = AbilityData.a_ids(res, i)[0]
        res[f'_Description{i}'] = f'elemental damage {ELEMENTS.get(a_id, a_id)}'
        return res

    @staticmethod
    def action_condition_timer(ad, res, i):
        res, a_ids = AbilityData.link_various_ids(ad, res, i)
        res[f'_Description{i}'] = 'action condition timer'
        return res

    def __init__(self, index):
        super().__init__(index, 'AbilityData', labeled_fields=[
            '_Name', '_Details', '_HeadText'])

    def process_result(self, res, fields=None, full_query=True, exclude_falsy=True):
        try:
            res['_ConditionType'] = ABILITY_CONDITION_TYPES.get(
                res['_ConditionType'], res['_ConditionType'])
        except:
            pass
        for i in (1, 2, 3):
            try:
                res[f'_TargetAction{i}'] = TARGET_ACTION_TYPES[res[f'_TargetAction{i}']]
            except:
                pass
            try:
                res = ABILITY_TYPES[res[f'_AbilityType{i}']](self, res, i)
            except KeyError:
                pass
        return res

    def get(self, key, fields=None, full_query=True, exclude_falsy=True):
        res = super().get(key, fields=fields, exclude_falsy=exclude_falsy)
        if not full_query:
            return res
        return self.process_result(res, fields, full_query, exclude_falsy)

    def export_all_to_folder(self, out_dir='./out', ext='.json', exclude_falsy=True):
        processed_res = [self.process_result(res, exclude_falsy=exclude_falsy) for res in self.get_all(exclude_falsy=exclude_falsy)]
        with open(os.path.join(out_dir, f'_abilities{ext}'), 'w', newline='', encoding='utf-8') as fp:
            json.dump(processed_res, fp, indent=2, ensure_ascii=False)


ABILITY_TYPES = {
    1: AbilityData.stat_ability,
    2: AbilityData.affliction_resist,
    3: AbilityData.affliction_proc_rate,
    4: AbilityData.tribe_resist,
    5: AbilityData.tribe_bane,
    6: AbilityData.generic_description('damage'),
    7: AbilityData.generic_description('critical rate'),
    8: AbilityData.generic_description('recovery potency'),
    9: AbilityData.generic_description('gauge accelerator'),
    # 10
    11: AbilityData.generic_description('striking haste'),
    # 12 13
    14: AbilityData.action_condition,
    # 15
    16: AbilityData.generic_description('debuff chance'),
    17: AbilityData.generic_description('skill prep'),
    18: AbilityData.generic_description('buff time'),
    # 19
    20: AbilityData.affliction_punisher,
    21: AbilityData.generic_description('player exp'),
    22: AbilityData.generic_description('adv exp'),
    23: AbilityData.generic_description('rupies'),
    24: AbilityData.generic_description('mana'),
    25: AbilityData.conditional_action_grant,
    26: AbilityData.generic_description('critical damage'),
    27: AbilityData.generic_description('shapeshift prep'),
    28: AbilityData.elemental_resist,
    29: AbilityData.generic_description('specific enemy resist'),
    30: AbilityData.generic_description('specific enemy bane'),
    # 31 32
    33: AbilityData.generic_description('event points'),
    34: AbilityData.generic_description('event drops'),
    35: AbilityData.generic_description('gauge inhibitor'),
    36: AbilityData.generic_description('dragon damage'),
    37: AbilityData.generic_description('enemy ability resist'),
    # 38
    39: AbilityData.action_grant,
    40: AbilityData.generic_description('gauge defense & skill damage'),
    41: AbilityData.generic_description('event point feh'),
    # 42: something dragonform related
    43: AbilityData.ability_reference,
    44: AbilityData.skill_reference,
    45: AbilityData.action_reference,
    46: AbilityData.generic_description('dragon gauge flat increaase'),
    # 47
    48: AbilityData.generic_description('dragon gauge decrease rate'),
    49: AbilityData.generic_description('conditional shapeshift fill'),
    51: AbilityData.random_action_condition,
    52: AbilityData.generic_description('buff icon critical rate'),
    # 53
    54: AbilityData.generic_description('combo damage boost'),
    55: AbilityData.generic_description('combo time'),
    56: AbilityData.generic_description('dragondrive'),
    57: AbilityData.elemental_damage,
    58: AbilityData.generic_description('dragondrive defense'),
    59: AbilityData.generic_description('debuff time'),
    # 60 61 - galaxi
    # 62 - ssinoa
    #   "_AbilityType1": 62,
    #   "_VariousId1a": 435,
    #   "_VariousId1b": 304030301,
    #   "_VariousId1c": 1084,
    63: AbilityData.action_condition_timer
}


class PlayerActionHitAttribute(DBView):
    def __init__(self, index):
        super().__init__(index, 'PlayerActionHitAttribute')

    def process_result(self, res, exclude_falsy=True):
        res_list = [res] if isinstance(res, dict) else res
        for r in res_list:
            if '_ActionCondition1' in r and r['_ActionCondition1']:
                act_cond = self.index['ActionCondition'].get(
                    r['_ActionCondition1'], exclude_falsy=exclude_falsy)
                if act_cond:
                    r['_ActionCondition1'] = act_cond
            for ks in ('_KillerState1', '_KillerState2', '_KillerState3'):
                if ks in r and r[ks] in KILLER_STATE:
                    r[ks] = KILLER_STATE[r[ks]]
        return res

    def get(self, pk, by=None, fields=None, order=None, mode=DBManager.EXACT, exclude_falsy=False):
        res = super().get(pk, by, fields, order, mode, exclude_falsy)
        return self.process_result(res, exclude_falsy=exclude_falsy)

    S_PATTERN = re.compile(r'S\d+')

    def export_all_to_folder(self, out_dir='./out', ext='.json', exclude_falsy=True):
        # super().export_all_to_folder(out_dir, ext, fn_mode='a', exclude_falsy=exclude_falsy, full_actions=False)
        out_dir = os.path.join(out_dir, '_hit_attr')
        all_res = self.get_all(exclude_falsy=exclude_falsy)
        check_target_path(out_dir)
        sorted_res = defaultdict(lambda: [])
        for res in tqdm(all_res, desc='_hit_attr'):
            res = self.process_result(res, exclude_falsy=exclude_falsy)
            try:
                k1, _ = res['_Id'].split('_', 1)
                if PlayerActionHitAttribute.S_PATTERN.match(k1):
                    sorted_res['S'].append(res)
                else:
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
            param=(state, ref),
            d_type=DBDict
        )


class ActionParts(DBView):
    LV_SUFFIX = re.compile(r'(.*LV)(\d{2})')
    HIT_LABELS = ['_hitLabel', '_hitAttrLabel', '_abHitAttrLabel']
    # BURST_ATK_DISPLACEMENT = 1

    def __init__(self, index):
        super().__init__(index, 'ActionParts')
        self.animation_reference = None

    # # figure out how it works again bleh
    # def get_burst_action_parts(self, pk, fields=None, exclude_falsy=True, hide_ref=False):
    #     # sub_parts = super().get((pk, pk+self.BURST_ATK_DISPLACEMENT), by='_ref', fields=fields, order='_ref ASC', mode=DBManager.RANGE, exclude_falsy=exclude_falsy)
    #     # return self.process_result(sub_parts, exclude_falsy=exclude_falsy, hide_ref=hide_ref)

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
                    hit_attrs = self.index['PlayerActionHitAttribute'].get(
                        base_label, by='_Id', order='_Id ASC', mode=DBManager.LIKE, exclude_falsy=exclude_falsy)
                    if hit_attrs:
                        r[label] = hit_attrs
                elif 'CMB' in r[label]:
                    base_label = r[label]
                    hit_attrs = self.index['PlayerActionHitAttribute'].get(
                        base_label, by='_Id', order='_Id ASC', mode=DBManager.LIKE, exclude_falsy=exclude_falsy)
                    if hit_attrs:
                        r[label] = hit_attrs
                else:
                    hit_attr = self.index['PlayerActionHitAttribute'].get(
                        r[label], by='_Id', exclude_falsy=exclude_falsy)
                    if hit_attr:
                        r[label] = hit_attr

            if '_actionConditionId' in r and r['_actionConditionId'] and (act_cond := self.index['ActionCondition'].get(r['_actionConditionId'], exclude_falsy=exclude_falsy)):
                r['_actionConditionId'] = act_cond

            if '_motionState' in r and r['_motionState']:
                ms = r['_motionState']
                animation = []
                if self.animation_reference is not None:
                    animation = self.index[self.animation_reference[0]].get_by_state_ref(
                        ms, self.animation_reference[1], exclude_falsy=exclude_falsy)
                if not animation:
                    animation = self.index['CharacterMotion'].get(
                        ms, exclude_falsy=exclude_falsy)
                if animation:
                    r['_animation'] = animation

        return action_parts

    def get(self, pk, by=None, fields=None, order=None, mode=DBManager.EXACT, exclude_falsy=True, hide_ref=True):
        action_parts = super().get(pk, by=by, fields=fields, order=order,
                                   mode=mode, exclude_falsy=exclude_falsy)
        return self.process_result(action_parts, exclude_falsy=exclude_falsy, hide_ref=hide_ref)

    @staticmethod
    def remove_falsy_fields(res):
        return DBDict(filter(lambda x: bool(x[1]) or x[0] in ('_seconds', '_seq'), res.items()))


class PlayerAction(DBView):
    BURST_MARKER_DISPLACEMENT = 4
    # REF = set()

    def __init__(self, index):
        super().__init__(index, 'PlayerAction')

    def process_result(self, player_action, exclude_falsy=True, full_query=True):
        pa_id = player_action['_Id']
        action_parts = self.index['ActionParts'].get(
            pa_id, by='_ref', order='_seconds ASC', exclude_falsy=exclude_falsy)
        if action_parts:
            player_action['_Parts'] = action_parts
        if '_BurstMarkerId' in player_action and player_action['_BurstMarkerId'] and (marker := self.get(player_action['_BurstMarkerId'], exclude_falsy=exclude_falsy)):
            player_action['_BurstMarkerId'] = marker
        else:
            try:
                if action_parts[0]['_motionState'] == 'charge_13':
                    player_action['_BurstMarkerId'] = pa_id + \
                        PlayerAction.BURST_MARKER_DISPLACEMENT
                    if marker := self.get(player_action['_BurstMarkerId'], exclude_falsy=exclude_falsy):
                        player_action['_BurstMarkerId'] = marker
            except:
                pass
        if '_NextAction' in player_action and player_action['_NextAction']:
            player_action['_NextAction'] = self.get(player_action['_NextAction'], exclude_falsy=exclude_falsy)
        return player_action

    def get(self, pk, fields=None, exclude_falsy=True, full_query=True):
        player_action = super().get(pk, fields=fields, exclude_falsy=exclude_falsy)
        if not full_query or not player_action:
            return player_action
        # PlayerAction.REF.add(pk)
        return self.process_result(player_action, exclude_falsy=exclude_falsy, full_query=full_query)

    def export_all_to_folder(self, out_dir='./out', ext='.json', exclude_falsy=True):
        # super().export_all_to_folder(out_dir, ext, fn_mode='a', exclude_falsy=exclude_falsy, full_actions=False)
        out_dir = os.path.join(out_dir, '_actions')
        all_res = self.get_all(exclude_falsy=exclude_falsy)
        check_target_path(out_dir)
        sorted_res = defaultdict(lambda: [])
        for res in tqdm(all_res, desc='_actions'):
            res = self.process_result(res, exclude_falsy=exclude_falsy)
            try:
                k1, _ = res['_ActionName'].split('_', 1)
                if k1[0] == 'D' and k1 != 'DAG':
                    k1 = 'DRAGON'
                sorted_res[k1].append(res)
            except:
                sorted_res[res['_ActionName']].append(res)
            # if res['_Id'] not in PlayerAction.REF:
            #     sorted_res['UNUSED'].append(res)
        for group_name, res_list in sorted_res.items():
            out_name = get_valid_filename(f'{group_name}{ext}')
            output = os.path.join(out_dir, out_name)
            with open(output, 'w', newline='', encoding='utf-8') as fp:
                json.dump(res_list, fp, indent=2, ensure_ascii=False)


class SkillChainData(DBView):
    def __init__(self, index):
        super().__init__(index, 'SkillChainData')

    def process_result(self, res):
        for r in res:
            r['_Skill'] = self.index['SkillData'].get(
                r['_Id'], full_chainSkill=False)
        return res

    def get(self, pk, by=None, fields=None, order=None, mode=DBManager.EXACT, exclude_falsy=False, expand_one=True):
        res = super().get(pk, by=by, fields=fields, order=order, mode=mode,
                          exclude_falsy=exclude_falsy, expand_one=expand_one)
        return self.process_result(res)


class SkillData(DBView):
    TRANS_PREFIX = '_Trans'

    def __init__(self, index):
        super().__init__(index, 'SkillData', labeled_fields=[
            '_Name', '_Description1', '_Description2', '_Description3', '_Description4', '_TransText'])

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
                       full_query=True, full_abilities=False, full_transSkill=True, full_chainSkill=True):
        if not full_query:
            return skill_data
        # Actions
        skill_data = self.get_all_from(
            self.index['PlayerAction'], '_ActionId', skill_data, exclude_falsy=exclude_falsy)
        if '_AdvancedSkillLv1' in skill_data and skill_data['_AdvancedSkillLv1'] and (adv_act := self.index['PlayerAction'].get(skill_data['_AdvancedActionId1'], exclude_falsy=exclude_falsy)):
            skill_data['_AdvancedActionId1'] = adv_act

        # Abilities
        if full_abilities:
            skill_data = self.get_all_from(
                self.index['AbilityData'], '_Ability', skill_data, exclude_falsy=exclude_falsy)
        else:
            skill_data = self.get_last_from(
                self.index['AbilityData'], '_Ability', skill_data, exclude_falsy=exclude_falsy)
        if full_transSkill and '_TransSkill' in skill_data and skill_data['_TransSkill']:
            next_trans_skill = self.get(skill_data['_TransSkill'], exclude_falsy=exclude_falsy,
                                        full_query=full_query, full_abilities=full_abilities, full_transSkill=False)
            trans_skill_group = {
                skill_data['_Id']: None,
                next_trans_skill['_Id']: next_trans_skill
            }
            while next_trans_skill['_TransSkill'] != skill_data['_Id']:
                next_trans_skill = self.get(next_trans_skill['_TransSkill'], exclude_falsy=exclude_falsy,
                                            full_query=full_query, full_abilities=full_abilities, full_transSkill=False)
                trans_skill_group[next_trans_skill['_Id']] = next_trans_skill
            skill_data['_TransSkill'] = trans_skill_group

        if '_TransBuff' in skill_data and skill_data['_TransBuff'] and (tb := self.index['PlayerAction'].get(skill_data['_TransBuff'], exclude_falsy=exclude_falsy)):
            skill_data['_TransBuff'] = tb

        # ChainGroupId
        if full_chainSkill and '_ChainGroupId' in skill_data and skill_data['_ChainGroupId']:
            skill_data['_ChainGroupId'] = self.index['SkillChainData'].get(
                skill_data['_ChainGroupId'], by='_GroupId', exclude_falsy=exclude_falsy)
        return skill_data

    def get(self, pk, fields=None, exclude_falsy=True,
            full_query=True, full_abilities=False, full_transSkill=True, full_chainSkill=True):
        skill_data = super().get(pk, fields=fields, exclude_falsy=exclude_falsy)
        return self.process_result(skill_data, exclude_falsy=exclude_falsy,
                                   full_query=full_query, full_abilities=full_abilities, full_transSkill=full_transSkill, full_chainSkill=full_chainSkill)


if __name__ == '__main__':
    index = DBViewIndex()
    view = SkillData(index)
    test = view.get(106505012)
    print(test)
