from typing import List, Dict, Any, Callable
import json
import re
import os
from collections import defaultdict
from tqdm import tqdm

from loader.Database import DBViewIndex, DBManager, DBView, DBDict, check_target_path
from loader.Actions import CommandType
from exporter.Mappings import (
    AFFLICTION_TYPES,
    KILLER_STATE,
    TRIBE_TYPES,
    ELEMENTS,
    WEAPON_TYPES,
    AbilityCondition,
    AbilityTargetAction,
    ActionTargetGroup,
    AbilityType,
    AbilityStat,
    PartConditionType,
    PartConditionComparisonType,
    ActionCancelType,
    AuraType,
    ActionSignalType,
    CharacterControl,
)


def get_valid_filename(s):
    return re.sub(r"(?u)[^-\w. ]", "", s)


class ActionCondition(DBView):
    def __init__(self, index):
        super().__init__(index, "ActionCondition", labeled_fields=["_Text", "_TextEx"])
        self.seen_skills = set()

    def process_result(self, res):
        if "_Type" in res:
            res["_Type"] = AFFLICTION_TYPES.get(res["_Type"], res["_Type"])
        self.link(res, "_EnhancedBurstAttack", "PlayerAction")
        self.link(
            res,
            "_AdditionAttack",
            "PlayerActionHitAttribute",
        )
        reset_seen_skills = len(self.seen_skills) == 0
        if res["_Id"] not in self.seen_skills:
            self.seen_skills.add(res["_Id"])
            for s in ("_EnhancedSkill1", "_EnhancedSkill2", "_EnhancedSkillWeapon"):
                if (sid := res.get(s)) not in self.seen_skills:
                    if (skill := self.index["SkillData"].get(sid)) :
                        res[s] = skill
        self.link(res, "_DamageLink", "PlayerActionHitAttribute")
        self.link(res, "_LevelUpId", "ActionCondition")
        if reset_seen_skills:
            self.seen_skills = set()
        return res

    def get(self, key, fields=None):
        res = super().get(key, fields=fields)
        if not res:
            return None
        return self.process_result(res)

    def export_all_to_folder(self, out_dir="./out", ext=".json"):
        # super().export_all_to_folder(out_dir, ext, fn_mode='a', full_actions=False)
        out_dir = os.path.join(out_dir, "_act_cond")
        all_res = self.get_all()
        check_target_path(out_dir)
        sorted_res = defaultdict(lambda: [])
        for res in tqdm(all_res, desc="_act_cond"):
            res = self.process_result(
                res,
            )
            try:
                sorted_res[int(res["_Id"] / 100000000)].append(res)
            except:
                sorted_res[0].append(res)
        for group_name, res_list in sorted_res.items():
            out_name = get_valid_filename(f"{group_name}00000000{ext}")
            output = os.path.join(out_dir, out_name)
            with open(output, "w", newline="", encoding="utf-8") as fp:
                json.dump(res_list, fp, indent=2, ensure_ascii=False, default=str)

    def check_overwrite_groups(self):
        all_res = self.get_all(where="_OverwriteGroupId != 0")
        sorted_actconds = defaultdict(lambda: [])
        for res in all_res:
            sorted_actconds[res["_OverwriteGroupId"]].append({k: v for k, v in res.items() if not k.startswith("_Text") and k != "_Text"})
        from pprint import pprint

        pprint(dict(sorted_actconds))


class ActionGrant(DBView):
    def __init__(self, index):
        super().__init__(index, "ActionGrant")

    def process_result(self, res):
        res["_TargetAction"] = AbilityTargetAction(res["_TargetAction"])
        self.link(res, "_GrantCondition", "ActionCondition")
        return res

    def get(self, pk, by=None, fields=None, order=None):
        res = super().get(pk, by=by, fields=fields, order=order)
        return self.process_result(res)


class AbilityData(DBView):
    STAT_ABILITIES = {
        1: "hp",
        2: "strength",
        3: "defense",
        4: "skill haste",
        5: "dragon haste",
        8: "shapeshift time",
        10: "attack speed",
        12: "fs charge rate",
    }
    MAP_COND_VALUE = (
        AbilityCondition.BUFFED_SPECIFIC_ID,
        AbilityCondition.BUFF_DISAPPEARED,
        AbilityCondition.BUFF_CONSUMED,
    )
    MAP_COND_VALUE2 = (
        AbilityCondition.BUFFED_SPECIFIC_ID_COUNT,
        AbilityCondition.BUFF_COUNT_MORE_THAN,
    )

    @staticmethod
    def a_ids(res, i):
        a_ids = [res[f"_VariousId{i}{a}"] for a in ("a", "b", "c", "") if f"_VariousId{i}{a}" in res and res[f"_VariousId{i}{a}"]]
        return a_ids

    @staticmethod
    def a_str(res, i):
        return res.get(f"_VariousId{i}str", None)

    @staticmethod
    def first_a_id(res, i):
        try:
            key = f"_VariousId{i}a"
            return key, res[key]
        except KeyError:
            key = f"_VariousId{i}"
            return key, res[key]

    @staticmethod
    def generic_description(name):
        def f(ad, res, i):
            a_ids = AbilityData.a_ids(res, i)
            a_str = AbilityData.a_str(res, i)
            if a_ids or a_str:
                res[f"_Description{i}"] = f"{name} {a_ids, a_str}"
            else:
                res[f"_Description{i}"] = name
            return res

        return f

    @staticmethod
    def link_various_ids(ad, res, i, view="ActionCondition"):
        a_ids = []
        for a in ("a", "b", "c", ""):
            key = f"_VariousId{i}{a}"
            if key in res and res[key]:
                a_ids.append(res[key])
                res[key] = ad.index[view].get(res[key])
        return res, a_ids

    @staticmethod
    def link_various_str(ad, res, i, view="PlayerActionHitAttribute"):
        a_str = None
        key = f"_VariousId{i}str"
        if key in res and res[key]:
            a_str = res[key]
            res[key] = ad.index[view].get(res[key], by="_Id")
        return res, a_str

    @staticmethod
    def stat_ability(ad, res, i):
        key, value = AbilityData.first_a_id(res, i)
        res[key] = AbilityStat(value)
        return res

    @staticmethod
    def affliction_ability(ad, res, i):
        key, value = AbilityData.first_a_id(res, i)
        res[key] = AFFLICTION_TYPES.get(value, value)
        return res

    @staticmethod
    def tribe_ability(ad, res, i):
        key, value = AbilityData.first_a_id(res, i)
        res[key] = TRIBE_TYPES.get(value, value)
        return res

    @staticmethod
    def action_condition(ad, res, i):
        res, a_ids = AbilityData.link_various_ids(ad, res, i)
        res, a_str = AbilityData.link_various_str(ad, res, i)
        # res[f"_Description{i}"] = f"action condition {a_ids, a_str}"
        return res

    @staticmethod
    def conditional_action_grant(ad, res, i):
        res, a_ids = AbilityData.link_various_ids(ad, res, i, view="ActionGrant")
        # res[f"_Description{i}"] = f"conditional action grant {a_ids}"
        return res

    @staticmethod
    def elemental_ability(ad, res, i):
        key, value = AbilityData.first_a_id(res, i)
        res[key] = ELEMENTS.get(value, value)
        return res

    @staticmethod
    def action_grant(ad, res, i):
        res, a_ids = AbilityData.link_various_ids(ad, res, i, view="ActionGrant")
        # res[f"_Description{i}"] = f"action grant {a_ids}"
        return res

    @staticmethod
    def ability_reference(ad, res, i):
        res, a_ids = AbilityData.link_various_ids(ad, res, i, view="AbilityData")
        # res[f"_Description{i}"] = f"ability reference {a_ids}"
        return res

    @staticmethod
    def skill_reference(ad, res, i):
        res, a_ids = AbilityData.link_various_ids(ad, res, i, view="SkillData")
        # res[f"_Description{i}"] = f"skill reference {a_ids}"
        return res

    @staticmethod
    def action_reference(ad, res, i):
        res, a_ids = AbilityData.link_various_ids(ad, res, i, view="PlayerAction")
        # res[f"_Description{i}"] = f"action reference {a_ids}"
        return res

    @staticmethod
    def action_condition_timer(ad, res, i):
        res, a_ids = AbilityData.link_various_ids(ad, res, i)
        res[f"_Description{i}"] = "action condition timer"
        return res

    def __init__(self, index):
        super().__init__(index, "AbilityData", labeled_fields=["_Name", "_Details", "_HeadText"])

    def process_result(self, res):
        try:
            ac_enum = AbilityCondition(res["_ConditionType"])
            if ac_enum in AbilityData.MAP_COND_VALUE:
                self.link(
                    res,
                    "_ConditionValue",
                    "ActionCondition",
                )
            if ac_enum in AbilityData.MAP_COND_VALUE2:
                self.link(
                    res,
                    "_ConditionValue2",
                    "ActionCondition",
                )
            res["_ConditionType"] = ac_enum
        except (KeyError, ValueError):
            pass
        try:
            res["_TargetAction"] = AbilityTargetAction(res["_TargetAction"])
        except (KeyError, ValueError):
            pass
        self.link(res, "_RequiredBuff", "ActionCondition")
        for i in (1, 2, 3):
            try:
                res[f"_TargetAction{i}"] = AbilityTargetAction(res[f"_TargetAction{i}"])
            except (KeyError, ValueError):
                pass
            try:
                res = ABILITY_TYPES[res[f"_AbilityType{i}"]](self, res, i)
            except (KeyError, IndexError):
                pass
            try:
                res[f"_AbilityType{i}"] = AbilityType(res[f"_AbilityType{i}"])
            except (KeyError, ValueError):
                pass

        if (ele := res.get("_ElementalType")) :
            res["_ElementalType"] = ELEMENTS.get(ele, ele)
        if (wep := res.get("_WeaponType")) :
            res["_WeaponType"] = WEAPON_TYPES.get(wep, wep)
        return res

    def get(self, key, fields=None, full_query=True):
        res = super().get(key, fields=fields)
        if not full_query:
            return res
        return self.process_result(res)

    def export_all_to_folder(self, out_dir="./out", ext=".json"):
        processed_res = [self.process_result(res) for res in self.get_all()]
        with open(os.path.join(out_dir, f"_abilities{ext}"), "w", newline="", encoding="utf-8") as fp:
            json.dump(processed_res, fp, indent=2, ensure_ascii=False, default=str)


ABILITY_TYPES = {
    1: AbilityData.stat_ability,
    2: AbilityData.affliction_ability,
    3: AbilityData.affliction_ability,
    4: AbilityData.tribe_ability,
    5: AbilityData.tribe_ability,
    # 6: AbilityData.generic_description('damage'),
    # 7: AbilityData.generic_description('critical rate'),
    # 8: AbilityData.generic_description('recovery potency'),
    # 9: AbilityData.generic_description('gauge accelerator'),
    # 10
    # 11: AbilityData.generic_description('striking haste'),
    # 12 13
    14: AbilityData.action_condition,
    # 15
    # 16: AbilityData.generic_description('debuff chance'),
    # 17: AbilityData.generic_description('skill prep'),
    # 18: AbilityData.generic_description('buff time'),
    # 19: AbilityData.generic_description('debuff time'),
    20: AbilityData.affliction_ability,
    # 21: AbilityData.generic_description('player exp'),
    # 22: AbilityData.generic_description('adv exp'),
    # 23: AbilityData.generic_description('rupies'),
    # 24: AbilityData.generic_description('mana'),
    25: AbilityData.conditional_action_grant,
    # 26: AbilityData.generic_description('critical damage'),
    # 27: AbilityData.generic_description('shapeshift prep'),
    28: AbilityData.elemental_ability,
    # 29: AbilityData.generic_description('specific enemy resist'),
    # 30: AbilityData.generic_description('specific enemy bane'),
    # 31 32
    # 33: AbilityData.generic_description('event points'),
    # 34: AbilityData.generic_description('event drops'),
    # 35: AbilityData.generic_description('gauge inhibitor'),
    # 36: AbilityData.generic_description('dragon damage'),
    # 37: AbilityData.generic_description('enemy ability resist'),
    38: AbilityData.action_condition,
    39: AbilityData.action_grant,
    # 40: AbilityData.generic_description('gauge defense & skill damage'),
    # 41: AbilityData.generic_description('event points'),
    # 42: AbilityData.generic_description('level up dragon auto'),
    43: AbilityData.ability_reference,
    44: AbilityData.skill_reference,
    45: AbilityData.action_reference,  # force strikes
    # 46: AbilityData.generic_description('dragon gauge all team'),
    # 47 extend afflic time?
    # 48: AbilityData.generic_description('dragon gauge decrease rate'),
    # 49: AbilityData.generic_description('dragon gauge self'),
    # 50 do nothing
    51: AbilityData.action_condition,
    # 52: AbilityData.generic_description('buff icon critical rate'),
    # 53
    # 54: AbilityData.generic_description('combo damage boost'),
    # 55: AbilityData.generic_description('combo time'),
    # 56: AbilityData.generic_description('dragondrive'),
    57: AbilityData.elemental_ability,
    # 58: AbilityData.generic_description('dragondrive charge'),
    # 59: AbilityData.generic_description('debuff time'),
    # 60: AbilityData.generic_description('stop autofire'),
    # 61: AbilityData.generic_description('mode change'),
    62: AbilityData.action_condition,
    63: AbilityData.action_condition_timer,
    # 64: AbilityData.generic_description('cp gauge gain'),
    65: AbilityData.action_reference,  # dodge
    # 66: AbilityData.generic_description('revive hp'),
    # 67: AbilityData.generic_description('stamina strength'),
    68: AbilityData.action_condition,  # enemy
    # 69: AbilityData.generic_description('cp gauge drain'),
    # 70: AbilityData.generic_description('cp gauge cost'),
    71: AbilityData.action_reference,
    # 72: AbilityData.generic_description('persona element')
}


class BuffCountData(DBView):
    def __init__(self, index):
        super().__init__(index, "BuffCountData")


class AuraData(DBView):
    def __init__(self, index):
        super().__init__(index, "AuraData")

    def process_result(self, res):
        try:
            res["_Type"] = AuraType(res["_Type"])
        except (KeyError, ValueError):
            pass
        return res

    def get(self, pk, **kwargs):
        res = super().get(pk, **kwargs)
        return self.process_result(res)


class PlayerActionHitAttribute(DBView):
    def __init__(self, index):
        super().__init__(index, "PlayerActionHitAttribute")

    def process_result(self, res):
        res_list = [res] if isinstance(res, dict) else res
        for r in res_list:
            try:
                r["_TargetGroup"] = ActionTargetGroup(r["_TargetGroup"])
            except KeyError:
                pass
            self.link(r, "_ActionCondition1", "ActionCondition")
            self.link(
                r,
                "_DamageUpDataByBuffCount",
                "BuffCountData",
            )
            self.link(r, "_AuraId", "AuraData")
            for ks in ("_KillerState1", "_KillerState2", "_KillerState3"):
                if ks in r and r[ks] in KILLER_STATE:
                    r[ks] = KILLER_STATE[r[ks]]
        return res

    def get(self, pk, by=None, fields=None, order=None, mode=DBManager.EXACT, expand_one=True):
        res = super().get(pk, by, fields, order, mode, expand_one=expand_one)
        return self.process_result(res)

    S_PATTERN = re.compile(r"S\d+")

    def export_all_to_folder(self, out_dir="./out", ext=".json"):
        # super().export_all_to_folder(out_dir, ext, fn_mode='a', full_actions=False)
        out_dir = os.path.join(out_dir, "_hit_attr")
        all_res = self.get_all()
        check_target_path(out_dir)
        sorted_res = defaultdict(lambda: [])
        for res in tqdm(all_res, desc="_hit_attr"):
            res = self.process_result(res)
            try:
                k1, _ = res["_Id"].split("_", 1)
                if PlayerActionHitAttribute.S_PATTERN.match(k1):
                    sorted_res["S"].append(res)
                else:
                    sorted_res[k1].append(res)
            except:
                sorted_res[res["_Id"]].append(res)
        for group_name, res_list in sorted_res.items():
            out_name = get_valid_filename(f"{group_name}{ext}")
            output = os.path.join(out_dir, out_name)
            with open(output, "w", newline="", encoding="utf-8") as fp:
                json.dump(res_list, fp, indent=2, ensure_ascii=False, default=str)


class CharacterMotion(DBView):
    def __init__(self, index):
        super().__init__(index, "CharacterMotion")

    def get_by_state_ref(self, state, ref):
        tbl = self.database.check_table(self.name)
        query = f"SELECT {tbl.named_fields} FROM {self.name} WHERE {self.name}.state=? AND {self.name}.ref=?;"
        return self.database.query_many(query=query, param=(state, ref), d_type=DBDict)


class ActionPartsHitLabel(DBView):
    LV_PATTERN = re.compile(r"_LV\d{2}.*")
    LV_CHLV_PATTERN = re.compile(r"_CHLV\d{2}")
    LABEL_SORT = {
        "_hitLabel": 0,
        "_hitAttrLabel": 1,
        "_hitAttrLabelSubList": 2,
        "_abHitAttrLabel": 3,
    }

    def __init__(self, index):
        super().__init__(index, "ActionPartsHitLabel", override_view=True)
        # SELECT * FROM ActionPartsHitLabel LEFT JOIN PlayerActionHitAttribute WHERE PlayerActionHitAttribute._Id GLOB ActionPartsHitLabel._hitLabelGlob

    def open(self):
        self.name = f"View_{self.base_table}"
        self.database.conn.execute(f"DROP VIEW IF EXISTS {self.name}")
        self.database.conn.execute(
            f"CREATE VIEW {self.name} AS SELECT ActionPartsHitLabel._ref AS _ref, ActionPartsHitLabel._source AS _source, PlayerActionHitAttribute.* FROM ActionPartsHitLabel LEFT JOIN PlayerActionHitAttribute WHERE PlayerActionHitAttribute._Id GLOB ActionPartsHitLabel._hitLabelGlob"
        )
        self.database.conn.commit()

    def process_result(self, res):
        result_dict = {source: [] for source in self.LABEL_SORT.keys()}
        for r in res:
            source = r["_source"]
            del r["_ref"]
            del r["_source"]
            result_dict[source].append(r)
        for source in list(result_dict.keys()):
            if not result_dict[source]:
                del result_dict[source]
            else:
                result_dict[source] = self.index["PlayerActionHitAttribute"].process_result(result_dict[source])
        return result_dict

    def get(self, pk, by=None, fields=None, order=None, mode=DBManager.EXACT):
        res = super().get(pk, by=by, fields=fields, order=order, mode=mode, expand_one=False)
        return self.process_result(res)


class ActionParts(DBView):
    def __init__(self, index):
        super().__init__(index, "ActionParts")
        self.animation_reference = None

    def process_result(self, action_parts, hide_ref=True):
        # if isinstance(action_parts, dict):
        #     action_parts = [action_parts]
        for r in action_parts:
            if "commandType" in r:
                r["commandType"] = CommandType(r["commandType"])

            hit_labels = self.index["ActionPartsHitLabel"].get(r["_Id"], by="_ref", order="_Id ASC")
            if hit_labels:
                r["_allHitLabels"] = hit_labels

            del r["_Id"]
            if hide_ref:
                del r["_ref"]

            try:
                r["_actionType"] = ActionCancelType(r["_actionType"])
            except (KeyError, ValueError):
                pass

            if r["commandType"] == CommandType.SEND_SIGNAL:
                r["_signalType"] = ActionSignalType(r.get("_signalType", 0))

            try:
                r["_charaCommand"] = CharacterControl(r["_charaCommand"])
                r["_charaCommandArgs"] = json.loads(r["_charaCommandArgs"])
            except (KeyError, ValueError):
                pass

            self.link(r, "_actionConditionId", "ActionCondition")
            self.link(r, "_buffCountConditionId", "ActionCondition")
            skip_autoFireActionId = False
            try:
                autofire_actions = []
                for autofire_id in set(map(int, json.loads(r["_autoFireActionIdList"]))):
                    if not autofire_id:
                        continue
                    if autofire_id == r.get("_autoFireActionId"):
                        skip_autoFireActionId = True
                    if (autofire_action := self.index["PlayerAction"].get(autofire_id)) :
                        autofire_actions.append(autofire_action)
                if autofire_actions:
                    r["_autoFireActionIdList"] = autofire_actions
            except (KeyError, ValueError, TypeError):
                pass
            if not skip_autoFireActionId:
                self.link(r, "_autoFireActionId", "PlayerAction")

            if "_motionState" in r and r["_motionState"]:
                ms = r["_motionState"]
                animation = []
                if self.animation_reference is not None:
                    animation = self.index[self.animation_reference[0]].get_by_state_ref(ms, self.animation_reference[1])
                if not animation:
                    animation = self.index["CharacterMotion"].get(ms)
                if animation:
                    if len(animation) == 1:
                        r["_animation"] = animation[0]
                    else:
                        r["_animation"] = animation

            if r.get("_conditionType"):
                condtype = PartConditionType(r["_conditionType"])
                r["_conditionType"] = condtype
                if condtype == PartConditionType.OwnerBuffCount:
                    buff, comp, count, padding4 = json.loads(r["_conditionValue"])
                    r["_conditionValue"] = {
                        "_actionCondition": self.index["ActionCondition"].get(buff),
                        "_compare": PartConditionComparisonType(comp),
                        "_count": int(count),
                        "_padding4": padding4,
                    }
                elif condtype in (PartConditionType.ShikigamiLevel, PartConditionType.ActionContainerHitCount):
                    comp, count, padding3, padding4 = json.loads(r["_conditionValue"])
                    r["_conditionValue"] = {
                        "_compare": PartConditionComparisonType(comp),
                        "_count": int(count),
                        "_padding3": padding3,
                        "_padding4": padding4,
                    }

        return action_parts

    def get(self, pk, by=None, fields=None, order=None, mode=DBManager.EXACT, hide_ref=True):
        action_parts = super().get(pk, by=by, fields=fields, order=order, mode=mode, expand_one=False)
        return self.process_result(action_parts, hide_ref=hide_ref)

    @staticmethod
    def remove_falsy_fields(res):
        return DBDict(filter(lambda x: bool(x[1]) or x[0] in ("_seconds", "_seq"), res.items()))


class PlayerAction(DBView):
    BURST_MARKER_DISPLACEMENT = 4
    # REF = set()

    def __init__(self, index):
        super().__init__(index, "PlayerAction")

    def process_result(self, player_action):
        pa_id = player_action["_Id"]
        if action_parts := self.index["ActionParts"].get(pa_id, by="_ref", order="_seconds ASC"):
            player_action["_Parts"] = action_parts
        if (mid := player_action.get("_BurstMarkerId")) and (marker := self.get(mid)):
            player_action["_BurstMarkerId"] = marker
        else:
            try:
                if (
                    player_action.get("_EnhancedBurstAttackOffsetFlag")
                    or action_parts[0]["_motionState"].startswith("charge_13")
                    or action_parts[0]["_motionState"].startswith("charge_12_c")
                ):
                    guess_burst_id = pa_id + PlayerAction.BURST_MARKER_DISPLACEMENT
                    if marker := self.get(guess_burst_id):
                        player_action["_BurstMarkerId"] = marker
            except:
                pass
        if (nextact := player_action.get("_NextAction")) :
            player_action["_NextAction"] = self.get(nextact)
        if (casting := player_action.get("_CastingAction")) :
            player_action["_CastingAction"] = self.get(casting)
        return player_action

    def get(self, pk, fields=None, full_query=True):
        player_action = super().get(pk, fields=fields)
        if not full_query or not player_action:
            return player_action
        # PlayerAction.REF.add(pk)
        return self.process_result(player_action)

    def export_all_to_folder(self, out_dir="./out", ext=".json"):
        # super().export_all_to_folder(out_dir, ext, fn_mode='a', full_actions=False)
        out_dir = os.path.join(out_dir, "_actions")
        all_res = self.get_all()
        check_target_path(out_dir)
        sorted_res = defaultdict(lambda: [])
        for res in tqdm(all_res, desc="_actions"):
            res = self.process_result(res)
            try:
                k1, _ = res["_ActionName"].split("_", 1)
                if k1[0] == "D" and k1 != "DAG":
                    k1 = "DRAGON"
                sorted_res[k1].append(res)
            except:
                sorted_res[res["_ActionName"]].append(res)
            # if res['_Id'] not in PlayerAction.REF:
            #     sorted_res['UNUSED'].append(res)
        for group_name, res_list in sorted_res.items():
            out_name = get_valid_filename(f"{group_name}{ext}")
            output = os.path.join(out_dir, out_name)
            with open(output, "w", newline="", encoding="utf-8") as fp:
                json.dump(res_list, fp, indent=2, ensure_ascii=False, default=str)


class SkillChainData(DBView):
    def __init__(self, index):
        super().__init__(index, "SkillChainData")

    def process_result(self, res):
        for r in res:
            r["_Skill"] = self.index["SkillData"].get(r["_Id"], full_chainSkill=False)
        return res

    def get(self, pk, by=None, fields=None, order=None, mode=DBManager.EXACT, expand_one=False):
        res = super().get(pk, by=by, fields=fields, order=order, mode=mode, expand_one=expand_one)
        return self.process_result(res)


class SkillDetail(DBView):
    def __init__(self, index):
        super().__init__(index, "SkillDetail")


class SkillData(DBView):
    TRANS_PREFIX = "_Trans"

    def __init__(self, index):
        super().__init__(
            index,
            "SkillData",
            labeled_fields=[
                "_Name",
                "_Description1",
                "_Description2",
                "_Description3",
                "_Description4",
                "_TransText",
            ],
        )

    @staticmethod
    def get_all_from(view, prefix, data, **kargs):
        for i in range(1, 5):
            a_id = f"{prefix}{i}"
            if a_id in data and data[a_id]:
                data[a_id] = view.get(data[a_id], **kargs)
        return data

    @staticmethod
    def get_last_from(view, prefix, data, **kargs):
        i = 4
        a_id = f"{prefix}{i}"
        while i > 0 and (not a_id in data or not data[a_id]):
            i -= 1
            a_id = f"{prefix}{i}"
        if i > 0:
            data[a_id] = view.get(data[a_id], **kargs)
        return data

    def process_result(self, skill_data, full_query=True, full_abilities=False, full_transSkill=True, full_chainSkill=True):
        if not skill_data:
            return
        if not full_query:
            return skill_data
        # Actions
        skill_data = self.get_all_from(self.index["PlayerAction"], "_ActionId", skill_data)
        if (
            "_AdvancedSkillLv1" in skill_data
            and skill_data["_AdvancedSkillLv1"]
            and (adv_act := self.index["PlayerAction"].get(skill_data["_AdvancedActionId1"]))
        ):
            skill_data["_AdvancedActionId1"] = adv_act

        # Abilities
        if full_abilities:
            skill_data = self.get_all_from(self.index["AbilityData"], "_Ability", skill_data)
        else:
            skill_data = self.get_last_from(self.index["AbilityData"], "_Ability", skill_data)
        if full_transSkill and "_TransSkill" in skill_data and skill_data["_TransSkill"]:
            next_trans_skill = self.get(
                skill_data["_TransSkill"],
                full_abilities=full_abilities,
                full_transSkill=False,
            )
            trans_skill_group = {
                skill_data["_Id"]: None,
                next_trans_skill["_Id"]: next_trans_skill,
            }
            seen_id = {skill_data["_Id"], next_trans_skill["_Id"]}
            while next_trans_skill["_TransSkill"] not in seen_id:
                next_trans_skill = self.get(
                    next_trans_skill["_TransSkill"],
                    full_abilities=full_abilities,
                    full_transSkill=False,
                )
                trans_skill_group[next_trans_skill["_Id"]] = next_trans_skill
                seen_id.add(next_trans_skill["_Id"])
            skill_data["_TransSkill"] = trans_skill_group

        self.link(skill_data, "_TransBuff", "PlayerAction")
        # ChainGroupId
        if full_chainSkill:
            self.link(skill_data, "_ChainGroupId", "SkillChainData", by="_GroupId")

        skill_detail = self.index["SkillDetail"].get(skill_data["_Id"], by="_SkillId")
        if skill_detail:
            skill_data["_SkillDetail"] = skill_detail

        return skill_data

    def get(self, pk, fields=None, full_query=True, **kwargs):
        skill_data = super().get(pk, fields=fields)
        return self.process_result(skill_data, full_query=full_query, **kwargs)


class MaterialData(DBView):
    def __init__(self, index):
        super().__init__(index, "MaterialData", labeled_fields=["_Name", "_Detail", "_Description"])


class FortPlantData(DBView):
    def __init__(self, index):
        super().__init__(index, "FortPlantData", labeled_fields=["_Name", "_Description", "_EventDescription", "_EventMenuDescription"])

    def process_result(self, res):
        self.link(res, "_DetailId", "FortPlantDetail")
        return res


class FortPlantDetail(DBView):
    def __init__(self, index):
        super().__init__(index, "FortPlantDetail", labeled_fields=["_Name", "_Description"])

    def process_result(self, res):
        self.link(res, "_NextAssetGroup", "FortPlantDetail")
        # for i in (1, 2, 3, 4, 5):
        #     self.link(res, f'_MaterialsId{i}', 'MaterialData', exclude_falsy=exclude_falsy)
        return res


if __name__ == "__main__":
    index = DBViewIndex()
    view = PlayerActionHitAttribute(index)
    # view.check_overwrite_groups()
    # view = SkillData(index)
    # test = view.get(106505012)
    # print(test)
    res = view.get("S152_002_01_LV0[0-9]", mode=DBManager.GLOB)
    from pprint import pprint

    pprint(res)
