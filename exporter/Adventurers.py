import json
import os
from operator import itemgetter

from loader.Database import DBViewIndex, DBView, DBManager
from loader.Actions import CommandType
from exporter.Shared import AbilityData, SkillData, PlayerAction, ActionCondition
from exporter.Mappings import WEAPON_TYPES, ELEMENTS, CLASS_TYPES

MODE_CHANGE_TYPES = {1: "Skill", 2: "Hud", 3: "Dragon", 4: "Buff", 5: "Ability"}


class EditSkillCharaOffset(DBView):
    def __init__(self, index):
        super().__init__(index, "EditSkillCharaOffset")


class ExAbilityData(AbilityData):
    def __init__(self, index):
        DBView.__init__(
            self, index, "ExAbilityData", labeled_fields=["_Name", "_Details"]
        )


class CharaUniqueCombo(DBView):
    AVOID = {6}

    def __init__(self, index):
        super().__init__(index, "CharaUniqueCombo")

    def get(self, pk, fields=None, exclude_falsy=True, full_query=True):
        res = super().get(pk, fields=fields, exclude_falsy=exclude_falsy)
        if not full_query:
            return res
        if "_ActionId" in res and res["_ActionId"]:
            base_action_id = res["_ActionId"]
            res["_ActionId"] = list(
                filter(
                    None,
                    (
                        self.index["PlayerAction"].get(
                            base_action_id + i, exclude_falsy=exclude_falsy
                        )
                        for i in range(0, res["_MaxComboNum"])
                    ),
                )
            )
        if "_ExActionId" in res and res["_ExActionId"]:
            base_action_id = res["_ExActionId"]
            res["_ExActionId"] = [
                self.index["PlayerAction"].get(
                    base_action_id + i, exclude_falsy=exclude_falsy
                )
                for i in range(0, res["_MaxComboNum"])
            ]
        if "_BuffHitAttribute" in res and res["_BuffHitAttribute"]:
            res["_BuffHitAttribute"] = self.index["PlayerActionHitAttribute"].get(
                res["_BuffHitAttribute"], exclude_falsy=exclude_falsy
            )
        return res


class CharaModeData(DBView):
    def __init__(self, index):
        super().__init__(index, "CharaModeData")

    def get(self, pk, fields=None, exclude_falsy=True, full_query=True):
        res = super().get(pk, fields=fields, exclude_falsy=exclude_falsy)
        if not res:
            return None
        if not full_query:
            return res
        self.link(res, "_ChargeBreakId", "PlayerAction", exclude_falsy=exclude_falsy)
        self.link(res, "_ActionId", "PlayerAction", exclude_falsy=exclude_falsy)
        self.link(res, "_Skill1Id", "SkillData", exclude_falsy=exclude_falsy)
        self.link(res, "_Skill2Id", "SkillData", exclude_falsy=exclude_falsy)
        self.link(
            res, "_UniqueComboId", "CharaUniqueCombo", exclude_falsy=exclude_falsy
        )
        self.link(res, "_BurstAttackId", "PlayerAction", exclude_falsy=exclude_falsy)
        return res


class CharaData(DBView):
    def __init__(self, index):
        super().__init__(
            index,
            "CharaData",
            labeled_fields=[
                "_Name",
                "_SecondName",
                "_CvInfo",
                "_CvInfoEn",
                "_ProfileText",
            ],
        )

    @staticmethod
    def condense_stats(res):
        for s in ("Hp", "Atk"):
            if res["_MaxLimitBreakCount"] > 4:
                MAX = f"_AddMax{s}1"
            else:
                MAX = f"_Max{s}"
                del res[f"_AddMax{s}1"]
            PLUS = [f"_Plus{s}{i}" for i in range(res["_MaxLimitBreakCount"] + 1)]
            FULL = f"_McFullBonus{s}5"
            stat = 0
            OUT = f"_Max{s}"
            for key in (MAX, *PLUS, FULL):
                stat += res[key]
                if key != OUT:
                    del res[key]
            res[OUT] = stat
            if res["_MaxLimitBreakCount"] == 4:
                del res[f"_Plus{s}5"]
            for m in [f"_Min{s}" + str(i) for i in range(3, 6)]:
                del res[m]
        return res

    def all_abilities(self, res, exclude_falsy=True):
        for i in (1, 2, 3):
            for j in (1, 2, 3, 4):
                ab = f"_Abilities{i}{j}"
                if ab in res and (
                    abd := self.index["AbilityData"].get(
                        res[ab], full_query=True, exclude_falsy=exclude_falsy
                    )
                ):
                    res[ab] = self.index["AbilityData"].get(
                        res[ab], full_query=True, exclude_falsy=exclude_falsy
                    )
        for i in (1, 2, 3, 4, 5):
            ex = f"_ExAbilityData{i}"
            if ex in res and res[ex]:
                res[ex] = self.index["ExAbilityData"].get(
                    res[ex], exclude_falsy=exclude_falsy
                )
            ex2 = f"_ExAbility2Data{i}"
            if ex2 in res and res[ex2]:
                res[ex2] = self.index["AbilityData"].get(
                    res[ex2], exclude_falsy=exclude_falsy
                )
        return res

    def last_abilities(self, res, exclude_falsy=True, as_mapping=False):
        ab_map = {}
        for i in (1, 2, 3):
            j = 4
            ab = f"_Abilities{i}{j}"
            while not (ab in res and res[ab]) and j > 0:
                j -= 1
                ab = f"_Abilities{i}{j}"
            if j > 0:
                res[ab] = self.index["AbilityData"].get(
                    res[ab], full_query=True, exclude_falsy=exclude_falsy
                )
                ab_map[ab] = res[ab]
        ex = f"_ExAbilityData5"
        if ex in res and res[ex]:
            res[ex] = self.index["ExAbilityData"].get(
                res[ex], exclude_falsy=exclude_falsy
            )
            ab_map[ex] = res[ex]
        ex2 = f"_ExAbility2Data5"
        if ex2 in res and res[ex2]:
            res[ex2] = self.index["AbilityData"].get(
                res[ex2], exclude_falsy=exclude_falsy
            )
            ab_map[ex2] = res[ex2]
        if as_mapping:
            return ab_map
        return res

    def process_result(self, res, exclude_falsy=True, condense=True):
        self.index["ActionParts"].animation_reference = (
            "CharacterMotion",
            int(f'{res["_BaseId"]:06}{res["_VariationId"]:02}'),
        )
        if "_WeaponType" in res:
            res["_WeaponType"] = WEAPON_TYPES.get(
                res["_WeaponType"], res["_WeaponType"]
            )
        if "_ElementalType" in res:
            res["_ElementalType"] = ELEMENTS.get(
                res["_ElementalType"], res["_ElementalType"]
            )
        if "_CharaType" in res:
            res["_CharaType"] = CLASS_TYPES.get(res["_CharaType"], res["_CharaType"])
        if condense:
            res = self.condense_stats(res)

        if "_ModeChangeType" in res and res["_ModeChangeType"]:
            res["_ModeChangeType"] = MODE_CHANGE_TYPES.get(
                res["_ModeChangeType"], res["_ModeChangeType"]
            )
        for m in ("_ModeId1", "_ModeId2", "_ModeId3", "_ModeId4"):
            if m in res and (
                mode := self.index["CharaModeData"].get(
                    res[m], exclude_falsy=exclude_falsy, full_query=True
                )
            ):
                res[m] = mode

        skill_ids = {0}
        for s in ("_Skill1", "_Skill2"):
            if s in res and res[s]:
                skill_ids.add(res[s])
                res[s] = self.index["SkillData"].get(
                    res[s], exclude_falsy=exclude_falsy, full_query=True
                )

        if "_EditSkillId" in res and res["_EditSkillId"] not in skill_ids:
            res["_EditSkillId"] = self.index["SkillData"].get(
                res["_EditSkillId"], exclude_falsy=exclude_falsy, full_query=True
            )

        if condense:
            res = self.last_abilities(res)
        else:
            res = self.all_abilities(res)

        if (
            "_BurstAttack" in res
            and res["_BurstAttack"]
            and (
                ba := self.index["PlayerAction"].get(
                    res["_BurstAttack"], exclude_falsy=exclude_falsy
                )
            )
        ):
            res["_BurstAttack"] = ba

        if (
            "_DashAttack" in res
            and res["_DashAttack"]
            and (
                da := self.index["PlayerAction"].get(
                    res["_DashAttack"], exclude_falsy=exclude_falsy
                )
            )
        ):
            res["_DashAttack"] = da

        if "_EditSkillRelationId" in res and res["_EditSkillRelationId"]:
            edit_skill_rel = self.index["EditSkillCharaOffset"].get(
                res["_EditSkillRelationId"], by="_EditSkillRelationId"
            )
            exclude = ("_Id", "_TargetWeaponType")
            not_id = list(filter(lambda k: k not in exclude, edit_skill_rel[0].keys()))
            reduced_edit_skill_rel = {}
            for esr in edit_skill_rel:
                vals = itemgetter(*not_id)(esr)
                if vals in reduced_edit_skill_rel:
                    for exc in exclude:
                        reduced_edit_skill_rel[vals][exc] += 1 << esr[exc]
                else:
                    for exc in exclude:
                        esr[exc] = 1 << esr[exc]
                    reduced_edit_skill_rel[vals] = esr

            res["_EditSkillRelationId"] = list(reduced_edit_skill_rel.values())
        self.index["ActionParts"].animation_reference = None
        return res

    def get(self, pk, fields=None, exclude_falsy=True, full_query=True, condense=True):
        res = super().get(
            pk,
            by="_SecondName",
            fields=fields,
            mode=DBManager.LIKE,
            exclude_falsy=exclude_falsy,
        )
        if not res:
            res = super().get(
                pk,
                by="_Name",
                fields=fields,
                mode=DBManager.LIKE,
                exclude_falsy=exclude_falsy,
            )
        if not res:
            res = super().get(
                pk,
                by="_Id",
                fields=fields,
                mode=DBManager.LIKE,
                exclude_falsy=exclude_falsy,
            )
        if not full_query:
            return res
        return self.process_result(res, exclude_falsy=exclude_falsy, condense=True)

    @staticmethod
    def outfile_name(res, ext=".json"):
        name = (
            "UNKNOWN"
            if "_Name" not in res
            else res["_Name"]
            if "_SecondName" not in res
            else res["_SecondName"]
        )
        if res["_ElementalType"] == 99:
            return f'{res["_Id"]:02}_{name}{ext}'
        return f'{res["_BaseId"]}_{res["_VariationId"]:02}_{name}{ext}'

    def export_all_to_folder(self, out_dir="./out", ext=".json", exclude_falsy=True):
        out_dir = os.path.join(out_dir, "adventurers")
        super().export_all_to_folder(
            out_dir, ext, exclude_falsy=exclude_falsy, condense=True
        )

    def export_one_to_folder(
        self, pk=10250101, out_dir="./out", ext=".json", exclude_falsy=True
    ):
        out_dir = os.path.join(out_dir, "adventurers")
        super().export_one_to_folder(
            pk, out_dir, ext, exclude_falsy=exclude_falsy, condense=True
        )


if __name__ == "__main__":
    index = DBViewIndex()
    view = CharaData(index)
    view.export_one_to_folder()
