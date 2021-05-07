import os
import json
import re
from collections import defaultdict
from tqdm import tqdm

from loader.Database import (
    DBViewIndex,
    DBManager,
    DBView,
    DBDict,
    ShortEnum,
    check_target_path,
)
from exporter.Shared import ActionCondition, snakey
from exporter.Mappings import AFFLICTION_TYPES, TRIBE_TYPES, ELEMENTS

AISCRIPT_INIT_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), "AiscriptInit.py")


class EnemyAbilityType(ShortEnum):
    NONE = 0
    DISSEVER = 1
    MIRAGE = 2
    NICKED = 3
    FURY = 4
    DP_DOWN = 5
    ATTACK_RANGE_TOLERANCE = 6
    BLAZING = 7
    SKILL_GUARD = 8
    IGNORE_PLAYER_ATK = 9
    VERONICA_MIRAGE = 10
    RIPTIDE = 11
    ELECTRIFY = 12
    FURY_2 = 13
    GRUDGE = 14
    PETRIFACTION = 15
    MALAISE = 16
    DRAIN = 17
    ATK_GUARD = 18
    RAMPAGE = 19
    GIANT = 20
    IGNORE_ATK_ON_ACTION = 21
    VIRUS = 22
    ARENA = 23
    GOLDEN_BARRIER = 24
    SHOWING = 25
    MIST = 26
    UNISON = 27
    CHILD_PLAY = 28
    BLOCKING = 29
    OPENNESS = 30
    DISPEL_GUARD = 31
    HEAL_BLOCK = 32
    DRAGON_BUSTER = 33
    HOPELESSNESS = 34
    SUBSPACE = 35
    GODS_ROCK = 36
    BERSERK_01 = 37
    BERSERK_02 = 38
    BERSERK_03 = 39
    BERSERK_04 = 40
    BERSERK_05 = 41
    YIN_YANG = 42
    BLACK_FLAME = 43
    BOOK_OF_GENESIS = 44
    BOOK_OF_DOOM = 45
    SCAPEGOAT = 46


# CREATE TABLE EnemyAbility (_Id INTEGER PRIMARY KEY,_AbilityType INTEGER,_Name TEXT,_IconId TEXT,_EffectName TEXT,_BerserkBreakLimit REAL,_BerserkODAtkRate INTEGER,_BerserkODDefRate INTEGER,_BerserkBreakAtkRate INTEGER,_BerserkBreakDefRate INTEGER,_BerserkODDmgRateOnBurstAtk INTEGER,_HpCost INTEGER,_DownScale REAL,_GeneratorLabel TEXT,_Reserve01 TEXT,_KillerDefDevide REAL,_DebuffId INTEGER,_BaseDpDamage INTEGER,_AttackRangeToleranceType INTEGER,_AttackRangeToleranceRate REAL,_HitAttr01 TEXT,_DmgInterval REAL,_DmgZoneR REAL,_ReducedDmgRate REAL,_MirageDownODRate REAL,_SpeedRate01 REAL,_HitAttr02 TEXT,_DmgZoneR02 REAL,_HoleR01 REAL,_Duration01 REAL,_HitAttr0301 TEXT,_DmgZoneR0301 REAL,_ReducedDmgRate0201 REAL,_HitAttr0302 TEXT,_DmgZoneR0302 REAL,_ReducedDmgRate0202 REAL,_HitAttr0303 TEXT,_DmgZoneR0303 REAL,_ReducedDmgRate0203 REAL,_HitAttr0304 TEXT,_ReducedDmgRate0204 REAL,_OdDefRate INTEGER,_HitAttr04 TEXT,_FixedDmgStack02 INTEGER,_FixedDmgStack03 INTEGER,_FixedDmgStack04 INTEGER,_FixedDmgStack05 INTEGER,_HitAttr05 TEXT,_DmgInterval02 REAL,_Duration02 REAL,_UseVirus INTEGER,_HitEffect02 TEXT,_HitSe02 TEXT,_ReducedDmgRate03 REAL,_LevelDmgRate REAL,_LevelUpInterval REAL,_MaxLevel INTEGER,_BodyScale REAL,_Duration04 REAL,_HitEffect01 TEXT,_HitSe01 TEXT,_FixedAbnormalRate INTEGER,_FixedAbnormalRate02 INTEGER,_FixedAbnormalRate03 INTEGER,_Duration03 REAL,_Duration0302 REAL,_Duration0303 REAL,_DmgZoneR0401 REAL,_DmgZoneR0402 REAL,_ReduceDuration INTEGER,_DmgZoneR05 REAL,_AttackDmgRate REAL,_ReceiveDmgRate REAL,_BuffId INTEGER,_RetryTime REAL,_HitAttr06 TEXT,_BarrierEff TEXT,_BarrierBrokenEff TEXT,_BarrierHitTimes INTEGER,_BarrierDuration REAL,_ShowingTiming INTEGER,_PartnerId INTEGER,_PartnerDeadPos REAL,_PartnerActionOnWeakDestroy INTEGER,_ParterActionOnTimerAction INTEGER,_ReducedDmgRate04 REAL,_BuffId02 INTEGER,_BuffInterval REAL,_TargetParamId INTEGER,_StopAbilityActionId INTEGER,_UndeadEffect TEXT,_ReducedDP INTEGER,_ReducedUTP INTEGER,_WarpGateId INTEGER,_ZoneR01 REAL,_ActionId01 INTEGER,_BuffId03 INTEGER,_YinYangType INTEGER,_AtkDmgRate02 INTEGER,_RecDmgRate02 INTEGER,_AbnormalRate0100 INTEGER,_AbnormalRate0101 INTEGER,_AbnormalRate0102 INTEGER,_AbnormaType0201 INTEGER,_AbnormalRate0201 INTEGER,_AbnormaType0202 INTEGER,_AbnormalRate0202 INTEGER,_AbnormaType0203 INTEGER,_AbnormalRate0203 INTEGER,_BuffId04 INTEGER,_ActionId03 INTEGER,_ActionId02 INTEGER,_Count0101 INTEGER,_Count0102 INTEGER,_Count02 INTEGER,_Duration05 REAL)


class EnemyAbility(DBView):
    def __init__(self, index):
        super().__init__(index, "EnemyAbility", labeled_fields=["_Name"])

    def process_result(self, res):
        try:
            res["_AbilityType"] = EnemyAbilityType(res["_AbilityType"])
        except (KeyError, ValueError):
            pass
        for k in res:
            if k.startswith("_HitAttr"):
                self.link(res, k, "EnemyActionHitAttribute")
            elif k.startswith("_BuffId"):
                self.link(res, k, "ActionCondition")
            elif "ActionId" in k:
                self.link(res, k, "EnemyAction")
        return res


class EnemyList(DBView):
    def __init__(self, index):
        super().__init__(index, "EnemyList", labeled_fields=["_Name"])

    def process_result(self, res):
        if "_TribeType" in res and res["_TribeType"]:
            res["_TribeType"] = TRIBE_TYPES.get(res["_TribeType"], res["_TribeType"])
        return res


class EnemyData(DBView):
    def __init__(self, index):
        super().__init__(index, "EnemyData")

    def process_result(self, res):
        if "_BookId" in res and res["_BookId"]:
            if (data := self.index["EnemyList"].get(res["_BookId"])) :
                res["_BookId"] = data
        if "_ElementalType" in res and res["_ElementalType"]:
            res["_ElementalType"] = ELEMENTS.get(res["_ElementalType"], res["_ElementalType"])
        return res


class EnemyActionHitAttribute(DBView):
    def __init__(self, index):
        super().__init__(index, "EnemyActionHitAttribute")

    def process_result(self, res):
        res_list = [res] if isinstance(res, dict) else res
        for r in res_list:
            if "_ActionCondition" in r and r["_ActionCondition"]:
                act_cond = self.index["ActionCondition"].get(r["_ActionCondition"])
                if act_cond:
                    r["_ActionCondition"] = act_cond
        return res


class EnemyHitDifficulty(DBView):
    def __init__(self, index):
        super().__init__(index, "EnemyHitDifficulty")

    def process_result(self, res):
        for k in res:
            if k == "_Id":
                continue
            res[k] = self.index["EnemyActionHitAttribute"].get(res[k])
        return res


class EnemyAction(DBView):
    def __init__(self, index):
        super().__init__(
            index,
            "EnemyAction",
            labeled_fields=[
                "_NameFire",
                "_NameWater",
                "_NameWind",
                "_NameLight",
                "_NameDark",
            ],
        )

    def process_result(self, res):
        if "_ActionGroupName" in res and res["_ActionGroupName"] and (hitdiff := self.index["EnemyHitDifficulty"].get(res["_ActionGroupName"])):
            res["_ActionGroupName"] = hitdiff
        return res


class EnemyActionSet(DBView):
    def __init__(self, index):
        super().__init__(index, "EnemyActionSet")

    def process_result(self, res):
        for k in res:
            if k == "_Id":
                continue
            res[k] = self.index["EnemyAction"].get(res[k])
        return res


class EnemyParam(DBView):
    DP_PATTERN = {1: "On Death", 2: "Every 10% HP"}
    RESIST_ID_ADJUST = {
        7: 9,
        8: None,
        9: 7,
        10: 8,
        11: 10,
        12: 11,
        13: 12,
        14: 13,
        15: 14,
    }
    DO_FULL_ACTIONS = ("AGITO_ABS", "DIABOLOS")

    def __init__(self, index):
        super().__init__(index, "EnemyParam")

    PARAM_GROUP = re.compile(r"([^\d]+)_\d{2}_\d{2}_E_?\d{2}")

    @staticmethod
    def general_param_group(res):
        try:
            param_group = res["_ParamGroupName"]
            if (match := EnemyParam.PARAM_GROUP.match(param_group)) :
                return match.group(1)
            else:
                return param_group.split("_", 1)[0]
        except KeyError:
            return "UNKNOWN"

    def process_result(self, res, full_actions=False):
        if "_DataId" in res and res["_DataId"]:
            if (data := self.index["EnemyData"].get(res["_DataId"])) :
                res["_DataId"] = data
        if full_actions or EnemyParam.general_param_group(res) in EnemyParam.DO_FULL_ACTIONS:
            seen_actsets = set()
            for actset_key in ("_ActionSet", "_ActionSetBoost", "_ActionSetFire", "_ActionSetWater", "_ActionSetWind", "_ActionSetLight", "_ActionSetDark"):
                if not (actset_id := res.get(actset_key)) or actset_id in seen_actsets:
                    continue
                seen_actsets.add(actset_id)
                self.link(res, actset_key, "EnemyActionSet")

        for ab in ("_Ability01", "_Ability02", "_Ability03", "_Ability04", "_BerserkAbility"):
            self.link(res, ab, "EnemyAbility")
        resists = {}
        for k, v in AFFLICTION_TYPES.items():
            k = EnemyParam.RESIST_ID_ADJUST.get(k, k)
            if k is None:
                continue
            resist_key = f"_RegistAbnormalRate{k:02}"
            if resist_key in res:
                resists[v] = res[resist_key]
                del res[resist_key]
            else:
                resists[v] = 0
        res["_AfflictionResist"] = resists
        if "_DropDpPattern" in res:
            res["_DropDpPattern"] = self.DP_PATTERN.get(res["_DropDpPattern"], res["_DropDpPattern"])
        return res

    @staticmethod
    def outfile_name(res, ext):
        return snakey(f'{res["_Id"]:02}_{res.get("_ParamGroupName", "UNKNOWN")}{ext}')

    @staticmethod
    def outfile_name_with_subdir(res, ext=".json", aiscript_dir="./out/_aiscript", enemies_dir="./out/enemies"):
        subdir = EnemyParam.general_param_group(res)
        try:
            name = res["_DataId"]["_BookId"]["_Name"]
        except KeyError:
            name = "UNNAMED"
        check_target_path(os.path.join(enemies_dir, subdir))
        try:
            _, ai_file = res["_Ai"].split("/")
            ai_path = os.path.join(aiscript_dir, ai_file)
            if os.path.exists(ai_path + ".py"):
                filename = snakey(f"{ai_file}_{name}")
                link_target = os.path.join(enemies_dir, subdir, f"{filename}.py")
                try:
                    os.link(ai_path + ".py", link_target)
                except FileExistsError:
                    os.remove(link_target)
                    os.link(ai_path + ".py", link_target)
                return subdir, snakey(f"{filename}{ext}")
        except KeyError:
            pass
        return subdir, snakey(f'{res["_Id"]:02}_{name}{ext}')

    def export_all_to_folder(self, out_dir="./out", ext=".json"):
        aiscript_dir = os.path.join(out_dir, "_aiscript")
        out_dir = os.path.join(out_dir, "enemies")
        aiscript_init_link = os.path.join(out_dir, "__init__.py")
        try:
            os.link(AISCRIPT_INIT_PATH, aiscript_init_link)
        except FileExistsError:
            os.remove(aiscript_init_link)
            os.link(AISCRIPT_INIT_PATH, aiscript_init_link)
        all_res = self.get_all()
        check_target_path(out_dir)
        misc_data = defaultdict(list)
        for res in tqdm(all_res, desc="enemies"):
            res = self.process_result(res)
            subdir, out_file = self.outfile_name_with_subdir(res, ext=ext, aiscript_dir=aiscript_dir, enemies_dir=out_dir)
            if subdir is None:
                misc_data[out_file].append(res)
                continue
            out_path = os.path.join(out_dir, subdir, out_file)
            with open(out_path, "w", newline="", encoding="utf-8") as fp:
                json.dump(res, fp, indent=2, ensure_ascii=False, default=str)
        for group_name, res_list in misc_data.items():
            out_name = snakey(f"{group_name}{ext}")
            output = os.path.join(out_dir, out_name)
            with open(output, "w", newline="", encoding="utf-8") as fp:
                json.dump(res_list, fp, indent=2, ensure_ascii=False, default=str)


if __name__ == "__main__":
    index = DBViewIndex()
    view = EnemyParam(index)
    view.export_all_to_folder()
