import json
import os

from loader.Database import DBViewIndex, DBView
from exporter.Shared import AbilityData, SkillData, PlayerAction

class DragonMotion(DBView):
    def __init__(self, index):
        super().__init__(index, 'DragonMotion')

class DragonData(DBView):
    ACTIONS = ['_AvoidActionFront', '_AvoidActionBack', '_Transform']
    def __init__(self, index):
        super().__init__(index, 'DragonData', labeled_fields=['_Name', '_SecondName', '_Profile', '_CvInfo', '_CvInfoEn'])

    def process_result(self, res, exclude_falsy, full_query=True, full_abilities=False):
        if not full_query:
            return res
        self.index['ActionParts'].chara_id = None
        if '_Skill1' in res:
            res['_Skill1'] = self.index['SkillData'].get(res['_Skill1'], exclude_falsy=exclude_falsy, full_abilities=full_abilities)
        inner = (1, 2) if full_abilities else (2,)
        outer = (1, 2)
        for i in outer:
            for j in inner:
                k = f'_Abilities{i}{j}'
                if k in res and res[k]:
                    res[k] = self.index['AbilityData'].get(res[k], full_query=True, exclude_falsy=exclude_falsy)
        for act in self.ACTIONS:
            if act in res:
                res[act] = self.index['PlayerAction'].get(res[act], exclude_falsy=exclude_falsy)
        if '_DefaultSkill' in res and res['_DefaultSkill']:
            base_action_id = res['_DefaultSkill']
            res['_DefaultSkill'] = [self.index['PlayerAction'].get(base_action_id+i, exclude_falsy=exclude_falsy) for i in range(0, res['_ComboMax'])]
        if '_AnimFileName' in res and res['_AnimFileName']:
            anim_key = int(res['_AnimFileName'][1:].replace('_', ''))
        else:
            anim_key = f'{res["_BaseId"]}{res["_VariationId"]:02}'
        res['_Animations'] = self.index['DragonMotion'].get(anim_key, by='ref')
        return res

    def get(self, pk, fields=None, exclude_falsy=False, full_query=True, full_abilities=False):
        res = super().get(pk, fields=fields, exclude_falsy=exclude_falsy)
        return self.process_result(res, exclude_falsy, full_query, full_abilities)

    @staticmethod
    def outfile_name(res, ext='.json'):
        name = 'UNKNOWN' if '_Name' not in res else res['_Name'] if '_SecondName' not in res else res['_SecondName']
        return f'{res["_BaseId"]}_{res["_VariationId"]:02}_{name}{ext}'

    def export_all_to_folder(self, out_dir='./out', ext='.json', exclude_falsy=True):
        out_dir = os.path.join(out_dir, 'dragons')
        super().export_all_to_folder(out_dir, ext, exclude_falsy=exclude_falsy, full_query=True, full_abilities=False)

if __name__ == '__main__':
    index = DBViewIndex()
    view = DragonData(index)
    view.export_all_to_folder()