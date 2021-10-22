import json
import os
import re

from loader.Database import DBViewIndex, DBView
from exporter.Shared import AbilityData, SkillData, PlayerAction, snakey

from exporter.Mappings import ELEMENTS, WEAPON_TYPES, WEAPON_LABEL


class WeaponSkin(DBView):
    def __init__(self, index):
        super().__init__(index, "WeaponSkin", labeled_fields=["_Name"])


class WeaponBodyGroupSeries(DBView):
    def __init__(self, index):
        super().__init__(
            index,
            "WeaponBodyGroupSeries",
            labeled_fields=["_GroupSeriesName", "_SeriesLockText"],
        )


class WeaponBodyRarity(DBView):
    def __init__(self, index):
        super().__init__(index, "WeaponBodyRarity")


class WeaponBodyBuildupGroup(DBView):
    def __init__(self, index):
        super().__init__(index, "WeaponBodyBuildupGroup")


class WeaponBodyBuildupLevel(DBView):
    def __init__(self, index):
        super().__init__(index, "WeaponBodyBuildupLevel")


class WeaponPassiveAbility(DBView):
    def __init__(self, index):
        super().__init__(index, "WeaponPassiveAbility")


class WeaponBody(DBView):
    WEAPON_SKINS = (
        "_WeaponSkinId",
        "_WeaponSkinId2",
        "_RewardWeaponSkinId1",
        "_RewardWeaponSkinId2",
        "_RewardWeaponSkinId3",
        "_RewardWeaponSkinId4",
        "_RewardWeaponSkinId5",
    )

    def __init__(self, index):
        super().__init__(index, "WeaponBody", labeled_fields=["_Name", "_Text"])

    def set_animation_reference(self, res):
        self.index["ActionParts"].animation_reference = (WEAPON_LABEL[res["_WeaponType"]], None)

    def process_result(self, res, full_query=True):
        if not full_query:
            return res
        self.set_animation_reference(res)
        self.link(res, "_WeaponSeriesId", "WeaponBodyGroupSeries")
        if res.get("_WeaponPassiveAbilityGroupId"):
            res["_WeaponPassiveAbilityGroupId"] = self.index["WeaponPassiveAbility"].get(res["_WeaponPassiveAbilityGroupId"], by="_WeaponPassiveAbilityGroupId")
        if res.get("_WeaponType"):
            res["_WeaponType"] = WEAPON_TYPES.get(res["_WeaponType"], res["_WeaponType"])
        if res.get("_ElementalType"):
            res["_ElementalType"] = ELEMENTS.get(res["_ElementalType"], res["_ElementalType"])
        skill_ids = {0}
        for i in (3, 2, 1):
            key = f"_ChangeSkillId{i}"
            if key in res and res[key] not in skill_ids:
                skill_ids.add(res[key])
                res[key] = self.index["SkillData"].get(res[key], full_abilities=True)
        ab_ids = {0}
        for i in (1, 2, 3):
            for j in (3, 2, 1):
                key = f"_Abilities{i}{j}"
                if key in res and res[key] not in ab_ids:
                    ab_ids.add(res[key])
                    res[key] = self.index["AbilityData"].get(res[key], full_query=True)
        for skin in WeaponBody.WEAPON_SKINS:
            self.link(res, skin, "WeaponSkin")
        self.index["ActionParts"].animation_reference = None
        return res

    @staticmethod
    def outfile_name(res, ext=".json"):
        name = "UNKNOWN" if "_Name" not in res else res["_Name"]
        return snakey(f'{res["_Id"]:02}_{name}{ext}')

    def export_all_to_folder(self, out_dir="./out", ext=".json"):
        out_dir = os.path.join(out_dir, "weapons")
        super().export_all_to_folder(out_dir, ext, full_query=True)


class WeaponType(DBView):
    ACTION_IDS = (
        "_DefaultSkill01",
        "_DefaultSkill02",
        "_DefaultSkill03",
        "_DefaultSkill04",
        "_DefaultSkill05",
        "_DefaultSkill05Ex",
        "_BurstChargePhase1",
        "_BurstChargePhase2",
        "_BurstPhase1",
        "_BurstPhase2",
        "_ChargeCancel",
        "_ChargeMarker",
        "_DashSkill",
    )

    def __init__(self, index):
        super().__init__(index, "WeaponType")

    def process_result(self, res):
        for act in WeaponType.ACTION_IDS:
            if act in res and res[act] and (action := self.index["PlayerAction"].get(res[act])):
                res[act] = action
        return res

    @staticmethod
    def outfile_name(res, ext=".json"):
        return f'{res["_Label"]}{ext}'

    def export_all_to_folder(self, out_dir="./out", ext=".json"):
        out_dir = os.path.join(out_dir, "_weapon_types")
        super().export_all_to_folder(out_dir, ext)


if __name__ == "__main__":
    index = DBViewIndex()
    view = WeaponBody(index)
    view.export_all_to_folder()
