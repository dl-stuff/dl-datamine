import json
import os
import re

from loader.Database import DBViewIndex, DBView
from exporter.Shared import AbilityData, SkillData, PlayerAction, get_valid_filename

from exporter.Mappings import ELEMENTS, WEAPON_TYPES

class WeaponData(DBView):
    """deprecated as of 2.0"""
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

class WeaponSkin(DBView):
    def __init__(self, index):
        super().__init__(index, 'WeaponSkin', labeled_fields=['_Name'])

class WeaponBodyGroupSeries(DBView):
    def __init__(self, index):
        super().__init__(index, 'WeaponBodyGroupSeries', labeled_fields=['_GroupSeriesName', '_SeriesLockText'])

class WeaponBodyRarity(DBView):
    def __init__(self, index):
        super().__init__(index, 'WeaponBodyRarity')

class WeaponBodyBuildupGroup(DBView):
    def __init__(self, index):
        super().__init__(index, 'WeaponBodyBuildupGroup')

class WeaponBody(DBView):
    WEAPON_SKINS = (
        '_WeaponSkinId',
        '_RewardWeaponSkinId1',
        '_RewardWeaponSkinId2',
        '_RewardWeaponSkinId3',
        '_RewardWeaponSkinId4',
        '_RewardWeaponSkinId5'
    )
    def __init__(self, index):
        super().__init__(index, 'WeaponBody', labeled_fields=['_Name', '_Text'])

    def process_result(self, res, exclude_falsy=True, full_query=True):
        if not full_query:
            return res
        if res.get('_WeaponSeriesId'):
            res['_WeaponSeriesId'] = self.index['WeaponBodyGroupSeries'].get(res['_WeaponSeriesId'], exclude_falsy=exclude_falsy)
        if res.get('_WeaponType'):
            res['_WeaponType'] = WEAPON_TYPES.get(res['_WeaponType'], res['_WeaponType'])
        if res.get('_ElementalType'):
            res['_ElementalType'] = ELEMENTS.get(res['_ElementalType'], res['_ElementalType'])
        skill_ids = {0}
        for i in (3, 2, 1):
            key = f'_ChangeSkillId{i}'
            if key in res and res[key] not in skill_ids:
                skill_ids.add(res[key])
                res[key] = self.index['SkillData'].get(res[key], exclude_falsy=exclude_falsy, full_abilities=True)
        ab_ids = {0}
        for i in (1, 2):
            for j in range(3, 2, 1):
                key = f'_Abilities{i}{j}'
                if key in res and res[key] not in ab_ids:
                    ab_ids.add(res[key])
                    res[key] = self.index['AbilityData'].get(res[key], full_query=True, exclude_falsy=exclude_falsy)
        for skin in WeaponBody.WEAPON_SKINS:
            if res.get(skin):
                res[skin] = self.index['WeaponSkin'].get(res[skin], exclude_falsy=exclude_falsy)
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


if __name__ == '__main__':
    index = DBViewIndex()
    view = WeaponBody(index)
    view.export_all_to_folder()