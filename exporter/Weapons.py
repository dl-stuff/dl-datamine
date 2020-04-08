import json
import os
import re

from loader.Database import DBViewIndex, DBView
from exporter.Shared import AbilityData, SkillData, PlayerAction, get_valid_filename

from exporter.Mappings import ELEMENTS, WEAPON_TYPES

class WeaponData(DBView):
    def __init__(self, index):
        super().__init__(index, 'WeaponData', labeled_fields=['_Name', '_Text'])

    def process_result(self, res, exclude_falsy=True, full_query=True):
        if not full_query:
            return res
        if '_Type' in res:
            res['_Type'] = WEAPON_TYPES.get(res['_Type'], res['_Type'])
        if '_ElementalType' in res:
            res['_ElementalType'] = ELEMENTS.get(res['_ElementalType'], res['_ElementalType'])
        if '_Skill' in res:
            res['_Skill'] = self.index['SkillData'].get(res['_Skill'], exclude_falsy=exclude_falsy, full_abilities=True)
        for k in ('_Abilities11', '_Abilities21'):
            if k in res and res[k]:
                res[k] = self.index['AbilityData'].get(res[k], full_query=True, exclude_falsy=exclude_falsy)
        return res

    def get(self, pk, fields=None, exclude_falsy=False, full_query=True):
        res = super().get(pk, fields=fields, exclude_falsy=exclude_falsy)
        return self.process_result(res, exclude_falsy, full_query)

    @staticmethod
    def outfile_name(res, ext='.json'):
        name = 'UNKNOWN' if '_Name' not in res else res['_Name']
        if '_BaseId' in res:
            return get_valid_filename(f'{res["_BaseId"]}_{res["_VariationId"]:02}_{name}{ext}')
        else:
            return get_valid_filename(f'{res["_Id"]:02}_{name}{ext}')

    def export_all_to_folder(self, out_dir='./out', ext='.json', exclude_falsy=True):
        out_dir = os.path.join(out_dir, 'weapons')
        super().export_all_to_folder(out_dir, ext, exclude_falsy=exclude_falsy, full_query=True)

if __name__ == '__main__':
    index = DBViewIndex()
    view = WeaponData(index)
    view.export_all_to_folder()