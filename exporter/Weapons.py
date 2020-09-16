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
        return get_valid_filename(f'{res["_Id"]:02}_{name}{ext}')

    def export_all_to_folder(self, out_dir='./out', ext='.json', exclude_falsy=True):
        out_dir = os.path.join(out_dir, 'weapons')
        super().export_all_to_folder(out_dir, ext, exclude_falsy=exclude_falsy, full_query=True)

class WeaponType(DBView):
    ACTION_IDS = (
        '_DefaultSkill01',
        '_DefaultSkill02',
        '_DefaultSkill03',
        '_DefaultSkill04',
        '_DefaultSkill05',
        '_DefaultSkill05Ex',
        '_BurstChargePhase1',
        '_BurstChargePhase2',
        '_BurstPhase1',
        '_BurstPhase2',
        '_ChargeCancel',
        '_ChargeMarker',
        '_DashSkill'
    )
    def __init__(self, index):
        super().__init__(index, 'WeaponType')

    def process_result(self, res, exclude_falsy=True, full_query=True):
        if not full_query:
            return res
        for act in WeaponType.ACTION_IDS:
            if act in res and res[act] and (action := self.index['PlayerAction'].get(res[act], exclude_falsy=exclude_falsy)):
                res[act] = action
        return res

    @staticmethod
    def outfile_name(res, ext='.json'):
        return f'{res["_Label"]}{ext}'

    def export_all_to_folder(self, out_dir='./out', ext='.json', exclude_falsy=True):
        out_dir = os.path.join(out_dir, '_weapon_types')
        super().export_all_to_folder(out_dir, ext, exclude_falsy=exclude_falsy, full_query=True)


# class Agito2_Mjolnir(WeaponBase):
#     ele = ['flame']
#     wt = 'axe'
#     att = 1781
#     s3 = agito_buffs['flame'][1]

from unidecode import unidecode
def export_py_def():
    index = DBViewIndex()
    view = WeaponData(index)
    all_res = view.get_all(exclude_falsy=False)
    with open('weapons.py', 'w') as f:
        for r in filter(lambda r: r['_FormId'] >= 60000 and r['_ElementalType'] == 4, all_res):
            r = view.process_result(r)
            f.write('class Agito')
            f.write(str(r['_GradeId']))
            f.write('_')
            f.write(re.sub(r'[^0-9a-zA-Z ]', '', unidecode(r['_Name'].strip())).replace(' ', '_'))
            # f.write('(WeaponBase):\n    ele = [\'')
            f.write('(LightAgitoWeaponBase):\n    wt = \'')
            # f.write(r['_ElementalType'].lower())
            # f.write('\']\n    wt = \'')
            f.write(r['_Type'].lower())
            f.write('\'\n    att = ')
            f.write(str(r['_MaxAtk']))
            f.write('''\n    s3a = {
        'dmg': 
        'startup': 0.1,
        'recovery': 
    }''')
            # f.write('\n    s3 = agito_buffs[\'')
            # f.write(r['_ElementalType'].lower())
            # f.write('\'][1]\n\n')
            f.write('\n\n')


if __name__ == '__main__':
    export_py_def()
    # index = DBViewIndex()
    # view = WeaponData(index)
    # view.export_all_to_folder()