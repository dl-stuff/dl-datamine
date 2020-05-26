import json
import os

from loader.Database import DBViewIndex, DBView
from loader.Actions import CommandType
from exporter.Shared import AbilityData, SkillData, PlayerAction, ActionCondition
from exporter.Mappings import WEAPON_TYPES, ELEMENTS, CLASS_TYPES

MODE_CHANGE_TYPES = {
    1: 'Skill',
    2: 'Hud',
    3: 'Dragon'
}

class ExAbilityData(AbilityData):
    def __init__(self, index):
        DBView.__init__(self, index, 'ExAbilityData', labeled_fields=['_Name', '_Details'])

class CharaUniqueCombo(DBView):
    AVOID = {6}
    def __init__(self, index):
        super().__init__(index, 'CharaUniqueCombo')

    def get(self, pk, fields=None, exclude_falsy=True, full_query=True):
        res = super().get(pk, fields=fields, exclude_falsy=exclude_falsy)
        if not full_query:
            return res
        if '_ActionId' in res and res['_ActionId']:            
            base_action_id = res['_ActionId']
            res['_ActionId'] = [self.index['PlayerAction'].get(base_action_id+i, exclude_falsy=exclude_falsy) for i in range(0, res['_MaxComboNum'])]
        return res


class CharaModeData(DBView):
    def __init__(self, index):
        super().__init__(index, 'CharaModeData')

    def get(self, pk, fields=None, exclude_falsy=True, full_query=True):
        res = super().get(pk, fields=fields, exclude_falsy=exclude_falsy)
        if not res:
            return None
        if not full_query:
            return res
        if '_ActionId' in res and res['_ActionId']:
            res['_ActionId'] = self.index['PlayerAction'].get(res['_ActionId'], exclude_falsy=exclude_falsy)
        for s in ('_Skill1Id', '_Skill2Id'):
            if s in res and res[s]:
                res[s] = self.index['SkillData'].get(res[s], exclude_falsy=exclude_falsy)
        if '_UniqueComboId' in res and res['_UniqueComboId']:
            res['_UniqueComboId'] = self.index['CharaUniqueCombo'].get(res['_UniqueComboId'], exclude_falsy=exclude_falsy)
        if '_BurstAttackId' in res and res['_BurstAttackId']:
            res['_BurstAttackId'] = self.index['PlayerAction'].get(res['_BurstAttackId'], exclude_falsy=exclude_falsy)
        return res

class CharaData(DBView):
    def __init__(self, index):
        super().__init__(index, 'CharaData', labeled_fields=['_Name', '_SecondName', '_CvInfo', '_CvInfoEn', '_ProfileText'])

    @staticmethod
    def condense_stats(res):
        for s in ('Hp', 'Atk'):
            if res['_MaxLimitBreakCount'] > 4:
                MAX = f'_AddMax{s}1'
            else:
                MAX = f'_Max{s}'
                del res[f'_AddMax{s}1']
            PLUS = [f'_Plus{s}{i}' for i in range(res['_MaxLimitBreakCount']+1)]
            FULL = f'_McFullBonus{s}5'
            stat = 0
            OUT = f'_Max{s}'
            for key in (MAX, *PLUS, FULL):
                stat += res[key]
                if key != OUT:
                    del res[key]
            res[OUT] = stat
            if res['_MaxLimitBreakCount'] == 4:
                del res[f'_Plus{s}5']
            for m in [f'_Min{s}'+str(i) for i in range(3, 6)]:
                del res[m]
        return res

    def all_abilities(self, res, exclude_falsy=True):
        for i in (1, 2, 3):
            for j in (1, 2, 3, 4):
                ab = f'_Abilities{i}{j}'
                if ab in res and (abd := self.index['AbilityData'].get(res[ab], full_query=True, exclude_falsy=exclude_falsy)):
                    res[ab] = self.index['AbilityData'].get(res[ab], full_query=True, exclude_falsy=exclude_falsy)
        for i in (1, 2, 3, 4, 5):
            ex = f'_ExAbilityData{i}'
            if ex in res and res[ex]:
                res[ex] = self.index['ExAbilityData'].get(res[ex], exclude_falsy=exclude_falsy)
            ex2 = f'_ExAbility2Data{i}'
            if ex2 in res and res[ex2]:
                res[ex2] = self.index['AbilityData'].get(res[ex2], exclude_falsy=exclude_falsy)
        return res

    def last_abilities(self, res, exclude_falsy=True):
        for i in (1, 2, 3):
            j = 4
            ab = f'_Abilities{i}{j}'
            while not (ab in res and res[ab]) and j > 0:
                j -= 1
                ab = f'_Abilities{i}{j}'
            if j > 0:
                res[ab] = self.index['AbilityData'].get(res[ab], full_query=True, exclude_falsy=exclude_falsy)
        ex = f'_ExAbilityData5'
        if ex in res and res[ex]:
            res[ex] = self.index['ExAbilityData'].get(res[ex], exclude_falsy=exclude_falsy)
        ex2 = f'_ExAbility2Data5'
        if ex2 in res and res[ex2]:
            res[ex2] = self.index['AbilityData'].get(res[ex2], exclude_falsy=exclude_falsy)
        return res

    def process_result(self, res, exclude_falsy=True, condense=True):
        self.index['ActionParts'].animation_reference = ('CharacterMotion', int(f'{res["_BaseId"]:06}{res["_VariationId"]:02}'))
        if '_WeaponType' in res:
            res['_WeaponType'] = WEAPON_TYPES.get(res['_WeaponType'], res['_WeaponType'])
        if '_ElementalType' in res:
            res['_ElementalType'] = ELEMENTS.get(res['_ElementalType'], res['_ElementalType'])
        if '_CharaType' in res:
            res['_CharaType'] = CLASS_TYPES.get(res['_CharaType'], res['_CharaType'])
        if condense:
            res = self.condense_stats(res)
        
        if '_ModeChangeType' in res and res['_ModeChangeType']:
            res['_ModeChangeType'] = MODE_CHANGE_TYPES.get(res['_ModeChangeType'], res['_ModeChangeType'])
        for m in ('_ModeId1', '_ModeId2', '_ModeId3'):
            if m in res:
                res[m] = self.index['CharaModeData'].get(res[m], exclude_falsy=exclude_falsy, full_query=True)

        for s in ('_Skill1', '_Skill2'):
            if s in res and res[s]:
                res[s] = self.index['SkillData'].get(res[s], exclude_falsy=exclude_falsy, full_query=True)

        if condense:
            res = self.last_abilities(res)
        else:        
            res = self.all_abilities(res)
        
        if '_BurstAttack' in res and res['_BurstAttack'] and (ba := self.index['PlayerAction'].get(res['_BurstAttack'], exclude_falsy=exclude_falsy)):
            res['_BurstAttack'] = ba

        return res

    def get(self, pk, fields=None, exclude_falsy=True, full_query=True, condense=True):
        res = super().get(pk, fields=fields, exclude_falsy=exclude_falsy)
        if not full_query:
            return res
        return self.process_result(res, exclude_falsy=exclude_falsy, condense=True)

    @staticmethod
    def outfile_name(res, ext='.json'):
        name = 'UNKNOWN' if '_Name' not in res else res['_Name'] if '_SecondName' not in res else res['_SecondName']
        return f'{res["_BaseId"]}_{res["_VariationId"]:02}_{name}{ext}'

    def export_all_to_folder(self, out_dir='./out', ext='.json', exclude_falsy=True):
        out_dir = os.path.join(out_dir, 'adventurers')
        super().export_all_to_folder(out_dir, ext, exclude_falsy=exclude_falsy, condense=True)

import re
from unidecode import unidecode
def snakey(name):
    return re.sub(r'[^0-9a-zA-Z ]', '', unidecode(name)).replace(' ', '_').replace('_amp', '_and')

def same(lst):
    if lst[1:] == lst[:-1]:
        return lst[0]
    else:
        return lst[-1]

if __name__ == '__main__':
    index = DBViewIndex()
    view = CharaData(index)
    all_res = view.get_all(exclude_falsy=False)
    skill_share_data = {}
    for res in all_res:
        res_data = {
            'limit': res['_HoldEditSkillCost'],
        }
        name = f'{res["_BaseId"]}_{res["_VariationId"]:02}' if not res['_Name'] else snakey(res['_Name']) if not res['_SecondName'] else snakey(res['_SecondName'])
        skill_share_id = res['_EditSkillId']
        if res['_EditSkillLevelNum'] > 0:
            skill = index['SkillData'].get(res['_Skill'+str(res['_EditSkillLevelNum'])], exclude_falsy=False)
            res_data['s'] = res['_EditSkillLevelNum']
            # res_data['name'] = snakey(skill['_Name'])
            res_data['cost'] = res['_EditSkillCost']
            res_data['type'] = skill['_SkillType']
            sp_s_list = [
                skill['_SpEdit'],
                skill['_SpLv2Edit'],
                skill['_SpLv3Edit'],
                skill['_SpLv4Edit'],
            ]
            res_data['sp'] = same(sp_s_list)
        skill_share_data[name] = res_data

    with open('skillshare.json', 'w', newline='') as f:
        json.dump(skill_share_data, f, indent=2)
    # with open('skillshare.csv', 'w') as f:
    #     f.write('name')
    #     for k in res_data.keys():
    #         f.write(',')
    #         f.write(k)
    #     f.write('\n')
    #     for name, data in skill_share_data.items():
    #         f.write(name)
    #         for v in data.values():
    #             f.write(',')
    #             f.write(str(v))
    #         f.write('\n')