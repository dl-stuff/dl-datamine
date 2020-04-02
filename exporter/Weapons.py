import json
import os
import re

from loader.Database import DBManager, DBView
from exporter.Shared import AbilityData, SkillData, PlayerAction, check_target_path

from exporter.Mappings import ELEMENTS, WEAPON_TYPES

def get_valid_filename(s):
    return re.sub(r'(?u)[^-\w. ]', '', s)

class WeaponData(DBView):
    def __init__(self, db):
        super().__init__(db, 'WeaponData', labeled_fields=['_Name', '_Text'])
        self.abilities = AbilityData(db)
        self.skills = SkillData(db)

    def process_result(self, res, exclude_falsy, full_query):
        if not full_query:
            return res
        if '_Type' in res:
            res['_Type'] = WEAPON_TYPES.get(res['_Type'], res['_Type'])
        if '_ElementalType' in res:
            res['_ElementalType'] = ELEMENTS.get(res['_ElementalType'], res['_ElementalType'])
        if '_Skill' in res:
            res['_Skill'] = self.skills.get(res['_Skill'], exclude_falsy=exclude_falsy, full_abilities=True)
        for k in ('_Abilities11', '_Abilities21'):
            if k in res and res[k]:
                res[k] = self.abilities.get(res[k], full_query=True, exclude_falsy=exclude_falsy)
        return res

    def get(self, pk, fields=None, exclude_falsy=False, full_query=True):
        res = super().get(pk, fields=fields, exclude_falsy=exclude_falsy)
        return self.process_result(res, exclude_falsy, full_query)

    def export_all_to_folder(self, out_dir=None, ext='.json', exclude_falsy=True):
        if not out_dir:
            out_dir = f'./out/weapons'
        all_res = self.get_all(exclude_falsy=exclude_falsy)
        check_target_path(out_dir)
        for res in all_res:
            res = self.process_result(res, exclude_falsy, True)
            if '_BaseId' in res:
                name = 'UNKNOWN' if '_Name' not in res else res['_Name']
                output = os.path.join(out_dir, get_valid_filename(f'{res["_BaseId"]}_{res["_VariationId"]:02}_{name}{ext}'))
                with open(output, 'w', newline='', encoding='utf-8') as fp:
                    json.dump(res, fp, indent=2, ensure_ascii=False)

if __name__ == '__main__':
    db = DBManager()
    view = WeaponData(db)
    view.export_all_to_folder()