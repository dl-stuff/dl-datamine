import json
import os
from operator import itemgetter

from loader.Database import DBViewIndex, DBView, DBManager
from loader.Actions import CommandType
from exporter.Shared import (
    AbilityData,
    SkillData,
    PlayerAction,
    ActionCondition,
    snakey,
)
from exporter.Mappings import WEAPON_LABEL, WEAPON_TYPES, ELEMENTS, CLASS_TYPES

MODE_CHANGE_TYPES = {1: "Skill", 2: "Hud", 3: "Dragon", 4: "Buff", 5: "Ability"}


class EditSkillCharaOffset(DBView):
    def __init__(self, index):
        super().__init__(index, "EditSkillCharaOffset")


class ExAbilityData(AbilityData):
    def __init__(self, index):
        DBView.__init__(self, index, "ExAbilityData", labeled_fields=["_Name", "_Details"])


class CharaUniqueCombo(DBView):
    AVOID = {6}

    def __init__(self, index):
        super().__init__(index, "CharaUniqueCombo")

    def get(self, pk, fields=None, full_query=True):
        res = super().get(pk, fields=fields)
        if not full_query:
            return res
        if "_ActionId" in res and res["_ActionId"]:
            base_action_id = res["_ActionId"]
            res["_ActionId"] = list(
                filter(
                    None,
                    (self.index["PlayerAction"].get(base_action_id + i) for i in range(0, res["_MaxComboNum"])),
                )
            )
        if "_ExActionId" in res and res["_ExActionId"]:
            base_action_id = res["_ExActionId"]
            res["_ExActionId"] = [self.index["PlayerAction"].get(base_action_id + i) for i in range(0, res["_MaxComboNum"])]
        if "_BuffHitAttribute" in res and res["_BuffHitAttribute"]:
            res["_BuffHitAttribute"] = self.index["PlayerActionHitAttribute"].get(res["_BuffHitAttribute"])
        return res


class CharaModeData(DBView):
    def __init__(self, index):
        super().__init__(index, "CharaModeData")

    def get(self, pk, fields=None, full_query=True):
        res = super().get(pk, fields=fields)
        if not res:
            return None
        if not full_query:
            return res
        self.link(res, "_ChargeBreakId", "PlayerAction")
        self.link(res, "_ActionId", "PlayerAction")
        self.link(res, "_Skill1Id", "SkillData")
        self.link(res, "_Skill2Id", "SkillData")
        self.link(res, "_UniqueComboId", "CharaUniqueCombo")
        self.link(res, "_BurstAttackId", "PlayerAction")
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

    def all_abilities(self, res):
        for i in (1, 2, 3):
            for j in (1, 2, 3, 4):
                ab = f"_Abilities{i}{j}"
                if ab in res and (abd := self.index["AbilityData"].get(res[ab], full_query=True)):
                    res[ab] = self.index["AbilityData"].get(res[ab], full_query=True)
        for i in (1, 2, 3, 4, 5):
            ex = f"_ExAbilityData{i}"
            if ex in res and res[ex]:
                res[ex] = self.index["ExAbilityData"].get(res[ex])
            ex2 = f"_ExAbility2Data{i}"
            if ex2 in res and res[ex2]:
                res[ex2] = self.index["AbilityData"].get(res[ex2])
        return res

    def last_abilities(self, res, as_mapping=False):
        ab_map = {}
        for i in (1, 2, 3):
            j = 4
            ab = f"_Abilities{i}{j}"
            while not (ab in res and res[ab]) and j > 0:
                j -= 1
                ab = f"_Abilities{i}{j}"
            if j > 0:
                res[ab] = self.index["AbilityData"].get(res[ab], full_query=True)
                ab_map[ab] = res[ab]
        ex = f"_ExAbilityData5"
        if ex in res and res[ex]:
            res[ex] = self.index["ExAbilityData"].get(res[ex])
            ab_map[ex] = res[ex]
        ex2 = f"_ExAbility2Data5"
        if ex2 in res and res[ex2]:
            res[ex2] = self.index["AbilityData"].get(res[ex2])
            ab_map[ex2] = res[ex2]
        if as_mapping:
            return ab_map
        return res

    def set_animation_reference(self, res):
        self.index["ActionParts"].animation_reference = (WEAPON_LABEL[res["_WeaponType"]], f'{res["_BaseId"]:06}{res["_VariationId"]:02}')
        return self.index["ActionParts"].animation_reference

    def process_result(self, res, condense=True):
        self.set_animation_reference(res)
        if "_WeaponType" in res:
            res["_WeaponType"] = WEAPON_TYPES.get(res["_WeaponType"], res["_WeaponType"])
        if "_ElementalType" in res:
            res["_ElementalType"] = ELEMENTS.get(res["_ElementalType"], res["_ElementalType"])
        if "_CharaType" in res:
            res["_CharaType"] = CLASS_TYPES.get(res["_CharaType"], res["_CharaType"])
        if condense:
            res = self.condense_stats(res)

        if "_ModeChangeType" in res and res["_ModeChangeType"]:
            res["_ModeChangeType"] = MODE_CHANGE_TYPES.get(res["_ModeChangeType"], res["_ModeChangeType"])
        for m in ("_ModeId1", "_ModeId2", "_ModeId3", "_ModeId4"):
            if m in res and (mode := self.index["CharaModeData"].get(res[m], full_query=True)):
                res[m] = mode

        skill_ids = {0}
        for s in ("_Skill1", "_Skill2"):
            if s in res and res[s]:
                skill_ids.add(res[s])
                res[s] = self.index["SkillData"].get(res[s], full_query=True)

        if "_EditSkillId" in res and res["_EditSkillId"] not in skill_ids:
            res["_EditSkillId"] = self.index["SkillData"].get(res["_EditSkillId"], full_query=True)

        if condense:
            res = self.last_abilities(res)
        else:
            res = self.all_abilities(res)

        self.link(res, "_BurstAttack", "PlayerAction")
        self.link(res, "_DashAttack", "PlayerAction")
        self.link(res, "_AvoidOnCombo", "PlayerAction")

        self.index["ActionParts"].animation_reference = None
        return res

    def get(self, pk, fields=None, full_query=True, condense=True):
        res = super().get(pk, by="_SecondName", fields=fields, mode=DBManager.LIKE, full_query=False)
        if not res:
            res = super().get(pk, by="_Name", fields=fields, mode=DBManager.LIKE, full_query=False)
        if not res:
            res = super().get(pk, by="_Id", fields=fields, mode=DBManager.LIKE, full_query=False)
        if not full_query:
            return res
        return self.process_result(res, condense=condense)

    @staticmethod
    def outfile_name(res, ext=".json"):
        name = "UNKNOWN" if "_Name" not in res else res["_Name"] if "_SecondName" not in res else res["_SecondName"]
        if res["_ElementalType"] == 99:
            return f'{res["_Id"]:02}_{name}{ext}'
        return snakey(f'{res["_BaseId"]}_{res["_VariationId"]:02}_{name}{ext}')

    def export_all_to_folder(self, out_dir="./out", ext=".json"):
        where = "_ElementalType != 99 OR _Id=19900004"
        out_dir = os.path.join(out_dir, "adventurers")
        super().export_all_to_folder(out_dir, ext, where=where, condense=True)

    def export_one_to_folder(self, pk=10250101, out_dir="./out", ext=".json"):
        out_dir = os.path.join(out_dir, "adventurers")
        super().export_one_to_folder(pk, out_dir, ext, condense=True)


class CharaLimitBreak(DBView):
    def __init__(self, index):
        super().__init__(index, "CharaLimitBreak", override_view=True)


class ManaCircle(DBView):
    FIELD_DEF = {
        "MC": (
            "_ManaCircleName",
            ("_Id", "_Seq"),
            "_Hierarchy",
            "_No",
            "_ManaPieceType",
            "_Step",
            "_IsReleaseStory",
            "_NecessaryManaPoint",
            "_UniqueGrowMaterialCount1",
            "_UniqueGrowMaterialCount2",
            "_GrowMaterialCount",
        ),
        "ManaPieceMaterial": (
            "_ElementId",
            "_MaterialId1",
            "_MaterialQuantity1",
            "_MaterialId2",
            "_MaterialQuantity2",
            "_MaterialId3",
            "_MaterialQuantity3",
            "_DewPoint",
        ),
    }

    def __init__(self, index):
        super().__init__(index, "MC", override_view=True)
        # SELECT DISTINCT _ManaCircleName, _PieceMaterialElementId FROM CharaData
        # SELECT * FROM ManaPieceMaterial WHERE _ElementId=3011

    def open(self):
        self.name = "View_ManaCircle"
        self.database.conn.execute(f"DROP VIEW IF EXISTS {self.name}")
        fieldnames = []
        for tbl, fields in ManaCircle.FIELD_DEF.items():
            for field in fields:
                if isinstance(field, tuple):
                    field, as_field = field
                else:
                    as_field = field
                fieldnames.append(f"{tbl}.{field} AS {as_field}")
        fieldnames = ",".join(fieldnames)
        self.database.conn.execute(f"CREATE VIEW {self.name} AS SELECT {fieldnames} FROM MC LEFT JOIN ManaPieceMaterial ON (MC._ManaPieceType == ManaPieceMaterial._ManaPieceType AND MC._Step == ManaPieceMaterial._Step)")
        self.database.conn.commit()


class CharaLimitBreak(DBView):
    def __init__(self, index):
        super().__init__(index, "CharaLimitBreak")


if __name__ == "__main__":
    index = DBViewIndex()
    # view = ManaCircle(index)
    view = CharaData(index)
    view.export_one_to_folder(pk=10250504)
