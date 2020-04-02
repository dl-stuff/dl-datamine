import json
import os

from loader.Database import DBManager, DBView
from loader.Actions import CommandType
from exporter.Shared import AbilityData, SkillData, PlayerAction, check_target_path
from exporter.Mappings import WEAPON_TYPES, ELEMENTS, CLASS_TYPES

MODE_CHANGE_TYPES = {
    0: 'Normal',
    1: 'Skill',
    2: 'Hud',
    3: 'Dragon'
}

class ExAbilityData(DBView):
    def __init__(self, db):
        super().__init__(db, 'ExAbilityData', labeled_fields=['_Name', '_Details'])

class CharaUniqueCombo(DBView):
    AVOID = {6}
    def __init__(self, db):
        super().__init__(db, 'CharaUniqueCombo')
        self.actions = PlayerAction(db)

    def get(self, pk, fields=None, exclude_falsy=True, full_query=True):
        res = super().get(pk, fields=fields, exclude_falsy=exclude_falsy)
        if not full_query:
            return res
        actions = []
        if '_ActionId' in res and res['_ActionId']:            
            base_action_id = res['_ActionId']
            for i in range(0, res['_MaxComboNum']):
                actions.append(self.actions.get(base_action_id+i, exclude_falsy=exclude_falsy))
        res['_ActionId'] = actions
        return res


class CharaModeData(DBView):
    def __init__(self, db):
        super().__init__(db, 'CharaModeData')
        self.actions = PlayerAction(db)
        self.skills = SkillData(db)
        self.combo = CharaUniqueCombo(db)

    def get(self, pk, fields=None, exclude_falsy=True, full_query=True):
        res = super().get(pk, fields=fields, exclude_falsy=exclude_falsy)
        if not res:
            return None
        if not full_query:
            return res
        if '_ActionId' in res and res['_ActionId']:
            res['_ActionId'] = self.actions.get(res['_ActionId'], exclude_falsy=exclude_falsy)
        for s in ('_Skill1Id', '_Skill2Id'):
            if s in res and res[s]:
                res[s] = self.skills.get(res[s], exclude_falsy=exclude_falsy)
        if '_UniqueComboId' and res['_UniqueComboId']:
            res['_UniqueComboId'] = self.combo.get(res['_UniqueComboId'], exclude_falsy=exclude_falsy)
        if '_BurstAttackId' in res and res['_BurstAttackId']:
            res['_BurstAttackId'] = self.actions.get(res['_BurstAttackId'], exclude_falsy=exclude_falsy)
        return res

class CharacterMotion(DBView):
    def __init__(self, db):
        super().__init__(db, 'CharacterMotion')

class CharaData(DBView):
    def __init__(self, db):
        super().__init__(db, 'CharaData', labeled_fields=['_Name', '_SecondName', '_CvInfo', '_CvInfoEn', '_ProfileText'])
        self.abilities = AbilityData(db)
        self.ex = ExAbilityData(db)
        self.skills = SkillData(db)
        self.motions = CharacterMotion(db)
        self.mode = CharaModeData(db)
        self.actions = PlayerAction(db)

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
                res[ab] = self.abilities.get(res[ab], full_query=True, exclude_falsy=exclude_falsy)
        for i in (1, 2, 3, 4, 5):
            ex = f'_ExAbilityData{i}'
            if ex in res and res[ex]:
                res[ex] = self.ex.get(res[ex], exclude_falsy=exclude_falsy)
            ex2 = f'_ExAbility2Data{i}'
            if ex2 in res and res[ex2]:
                res[ex2] = self.abilities.get(res[ex2], exclude_falsy=exclude_falsy)
        return res

    def last_abilities(self, res, exclude_falsy=True):
        for i in (1, 2, 3):
            j = 4
            ab = f'_Abilities{i}{j}'
            while not (ab in res and res[ab]) and j > 0:
                j -= 1
                ab = f'_Abilities{i}{j}'
            if j > 0:
                res[ab] = self.abilities.get(res[ab], full_query=True, exclude_falsy=exclude_falsy)
        ex = f'_ExAbilityData5'
        if ex in res and res[ex]:
            res[ex] = self.ex.get(res[ex], exclude_falsy=exclude_falsy)
        ex2 = f'_ExAbility2Data5'
        if ex2 in res and res[ex2]:
            res[ex2] = self.abilities.get(res[ex2], exclude_falsy=exclude_falsy)
        return res

    def process_result(self, res, exclude_falsy=True, condesnse=True):
        if '_WeaponType' in res:
            res['_WeaponType'] = WEAPON_TYPES.get(res['_WeaponType'], res['_WeaponType'])
        if '_ElementalType' in res:
            res['_ElementalType'] = ELEMENTS.get(res['_ElementalType'], res['_ElementalType'])
        if '_CharaType' in res:
            res['_CharaType'] = CLASS_TYPES.get(res['_CharaType'], res['_CharaType'])
        if condesnse:
            res = self.condense_stats(res)
        
        if '_ModeChangeType' in res and res['_ModeChangeType']:
            res['_ModeChangeType'] = MODE_CHANGE_TYPES.get(res['_ModeChangeType'], res['_ModeChangeType'])
            for m in ('_ModeId1', '_ModeId2', '_ModeId3'):
                if m in res:
                    res[m] = self.mode.get(res[m], exclude_falsy=exclude_falsy, full_query=True)

        for s in ('_Skill1', '_Skill2'):
            if s in res and res[s]:
                res[s] = self.skills.get(res[s], exclude_falsy=exclude_falsy, full_query=True, full_hitattr=not condesnse)

        if condesnse:
            res = self.last_abilities(res)
        else:
            res = self.all_abilities(res)
        chara_id = f'{res["_BaseId"]}{res["_VariationId"]:02}'
        res['_Animations'] = self.motions.get(chara_id, by='ref')

        return res

    def get(self, pk, fields=None, exclude_falsy=True, full_query=True, condesnse=True):
        res = super().get(pk, fields=fields, exclude_falsy=exclude_falsy)
        if not full_query:
            return res
        return self.process_result(res, exclude_falsy=exclude_falsy, condesnse=True)

    def export_all_to_folder(self, out_dir=None, ext='.json', exclude_falsy=True):
        if not out_dir:
            out_dir = f'./out/adventurers'
        all_res = self.get_all(exclude_falsy=exclude_falsy)
        check_target_path(out_dir)
        for res in all_res:
            res = self.process_result(res, exclude_falsy=exclude_falsy, condesnse=True)
            name = 'UNKNOWN' if '_Name' not in res else res['_Name'] if '_SecondName' not in res else res['_SecondName']
            output = os.path.join(out_dir, f'{res["_BaseId"]}_{res["_VariationId"]:02}_{name}{ext}')
            with open(output, 'w', newline='', encoding='utf-8') as fp:
                json.dump(res, fp, indent=2, ensure_ascii=False)


if __name__ == '__main__':
    db = DBManager()
    view = CharaData(db)
    view.export_all_to_folder()