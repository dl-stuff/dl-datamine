import ctypes
from enum import Enum
from functools import singledispatchmethod
import sys
import os
import pathlib
import json
import re
import itertools
from collections import defaultdict
from typing import OrderedDict
from tqdm import tqdm
from pprint import pprint
import argparse
from ctypes import c_float


from loader.Database import DBViewIndex, DBView, check_target_path
from loader.Actions import CommandType
from exporter.Shared import ActionCondition, ActionParts, AuraData, PlayerAction, AbilityData, ActionPartsHitLabel, snakey
from exporter.Adventurers import CharaData, CharaUniqueCombo
from exporter.Dragons import DragonData
from exporter.Weapons import WeaponType, WeaponBody
from exporter.Wyrmprints import AbilityCrest, UnionAbility
from exporter.Mappings import (
    WEAPON_TYPES,
    ELEMENTS,
    TRIBE_TYPES,
    AFFLICTION_TYPES,
    AbilityCondition,
    ActionTargetGroup,
    AbilityTargetAction,
    AbilityType,
    AbilityStat,
    AuraType,
    PartConditionType,
    ActionCancelType,
    PartConditionComparisonType,
    ActionSignalType,
)

ONCE_PER_ACT = ("sp", "dp", "utp", "buff", "afflic", "bleed", "extra", "dispel")
DODGE_ACTIONS = {6, 7, 40, 900710, 900711}
DEFAULT_AFF_DURATION = {
    "poison": 15,
    "burn": 12,
    "paralysis": 13,
    "frostbite": 21,
    "flashburn": 21,
    "blind": 8,
    "bog": 8,
    "freeze": (3, 6),
    "stun": (6, 7),
    "sleep": (6, 7),
    "shadowblight": 21,
    "stormlash": 21,
    "scorchrend": 21,
}
DEFAULT_AFF_IV = {
    "poison": 2.9,
    "burn": 3.9,
    "paralysis": 3.9,
    "frostbite": 2.9,
    "flashburn": 2.9,
    "shadowblight": 2.9,
    "stormlash": 2.9,
    "scorchrend": 2.9,
}
AFF_RELIEF = 1
DISPEL = 100
GENERIC_BUFF = (
    "skill_A",
    "skill_B",
    "skill_C",
    "skill_D",
)
BUFFARG_KEY = {
    "_RateAttack": ("att", "buff"),
    "_RateDefense": ("defense", "buff"),
    "_RateHP": ("maxhp", "buff"),
    "_RateCritical": ("crit", "chance"),
    "_EnhancedCritical": ("crit", "damage"),
    "_RateRecoverySp": ("sp", "passive"),
    "_RateAttackSpeed": ("spd", "buff"),
    "_RateChargeSpeed": ("cspd", "buff"),
    "_RateBurst": ("fs", "buff"),
    "_RateSkill": ("s", "buff"),
    "_EnhancedFire2": ("flame", "ele"),
    "_RateRecovery": ("recovery", "buff"),
    # '_RateDamageShield': ('shield', 'buff')
    "_RatePoisonKiller": ("poison_killer", "passive"),
    "_RateBurnKiller": ("burn_killer", "passive"),
    "_RateFreezeKiller": ("freeze_killer", "passive"),
    "_RateDarknessKiller": ("blind_killer", "passive"),
    "_RateSwoonKiller": ("stun_killer", "passive"),
    "_RateSlowMoveKiller": ("bog_killer", "passive"),
    "_RateSleepKiller": ("sleep_killer", "passive"),
    "_RateFrostbiteKiller": ("frostbite_killer", "passive"),
    "_RateFlashheatKiller": ("flashburn_killer", "passive"),
    "_RateCrashWindKiller": ("stormlash_killer", "passive"),
    "_RateDarkAbsKiller": ("shadowblight_killer", "passive"),
    "_RateDestroyFireKiller": ("scorchrend_killer", "passive"),
}
DEBUFFARG_KEY = {
    "_RateDefense": "def",
    "_RateDefenseB": "defb",
    "_RateAttack": "attack",
}
AFFRES_KEY = {
    "_RatePoison": "poison",
    "_RateBurn": "burn",
    "_RateFreeze": "freeze",
    "_RateDarkness": "blind",
    "_RateSwoon": "stun",
    "_RateSlowMove": "bog",
    "_RateSleep": "sleep",
    "_RateFrostbite": "frostbite",
    "_RateFlashheat": "flashburn",
    "_RateCrashWind": "stormlash",
    "_RateDarkAbs": "shadowblight",
    "_RateDestroyFire": "scorchrend",
}
ELERES_KEY = {
    "_RateFire": "flame_resist",
    "_RateWater": "water_resist",
    "_RateWind": "wind_resist",
    "_RateLight": "light_resist",
    "_RateDark": "shadow_resist",
}
TENSION_KEY = {"_Tension": "energy", "_Inspiration": "inspiration"}
# OVERWRITE = ('_Overwrite', '_OverwriteVoice', '_OverwriteGroupId')
ENHANCED_SKILL = {
    "_EnhancedSkill1": 1,
    "_EnhancedSkill2": 2,
    "_EnhancedSkillWeapon": 3,
}
DUMMY_PART = {"_seconds": 0}


def ele_bitmap(n):
    seq = 1
    eles = []
    while n > 0 and seq < 6:
        if n & 1:
            eles.append(ELEMENTS[seq].lower())
        n = n >> 1
        seq += 1
    if len(eles) == 1:
        return eles[0]
    return eles


def str_to_tuples(value):
    # result = {}
    # for pair in value.split("/"):
    #     key, value = map(int, pair.split("_"))
    #     result[key] = value
    # return result
    return [tuple(map(int, pair.split("_"))) for pair in value.split("/")]


def confsort(a):
    k, _ = a
    if k[0] == "x":
        try:
            return "x" + k.split("_")[1]
        except IndexError:
            return k
    return k


def float_ceil(value, percent):
    c_float_value = c_float(c_float(percent).value * value).value
    int_value = int(c_float_value)
    return int_value if int_value == c_float_value else int_value + 1


INDENT = "    "
PRETTY_PRINT_THIS = ("dragonform", "dservant", "repeat")


def fmt_conf(data, k=None, depth=0, f=sys.stdout, lim=2, sortlim=1):
    if k in PRETTY_PRINT_THIS:
        lim += 1
    if depth >= lim:
        if k.startswith("attr"):
            r_str_lst = []
            end = len(data) - 1
            for idx, d in enumerate(data):
                if isinstance(d, int):
                    r_str_lst.append(" " + str(d))
                elif idx > 0:
                    r_str_lst.append("\n" + INDENT * (depth + 1) + json.dumps(d))
                else:
                    r_str_lst.append(json.dumps(d))
            if len(r_str_lst) == 0:
                return "[]"
            return "[\n" + INDENT * (depth + 1) + (",").join(r_str_lst) + "\n" + INDENT * depth + "]"
        return json.dumps(data)
    if not isinstance(data, dict):
        f.write(json.dumps(data))
    else:
        f.write("{\n")
        # f.write(INDENT*depth)
        end = len(data) - 1
        if depth < sortlim:
            items = enumerate(sorted(data.items(), key=confsort))
        else:
            items = enumerate(data.items())
        for idx, kv in items:
            k, v = kv
            f.write(INDENT * (depth + 1))
            f.write('"')
            f.write(str(k))
            f.write('": ')
            res = fmt_conf(v, str(k), depth + 1, f, lim, sortlim)
            if res is not None:
                f.write(res)
            if idx < end:
                f.write(",\n")
            else:
                f.write("\n")
        f.write(INDENT * depth)
        f.write("}")


def fr(num):
    try:
        return round(num, 5)
    except TypeError:
        return 0


def clean_hitattr(attr, once_per_action):
    need_copy = False
    if once_per_action:
        for act in ONCE_PER_ACT:
            try:
                del attr[act]
                if act == "buff" and "coei" in attr:
                    del attr["coei"]
                need_copy = True
            except KeyError:
                continue
    return attr, need_copy


PART_COMPARISON_TO_VARS = {
    PartConditionComparisonType.Equality: "=",
    PartConditionComparisonType.Inequality: "!=",
    PartConditionComparisonType.GreaterThan: ">",
    PartConditionComparisonType.GreaterThanOrEqual: ">=",
    PartConditionComparisonType.LessThan: "<",
    PartConditionComparisonType.LessThanOrEqual: "<=",
}


def convert_all_hitattr(action, pattern=None, meta=None, skill=None):
    actparts = action["_Parts"]
    clear_once_per_action = action.get("_OnHitExecType") == 1
    hitattrs = []
    once_per_action = set()
    partcond_once_per_action = defaultdict(set)
    partcond_once_per_action[None] = once_per_action
    # accurate_col = 0
    # accurate_ab_col = 0

    for part in actparts:
        # servant for persona
        if servant_cmd := part.get("_servantActionCommandId"):
            servant_attr = {"DEBUG_SERVANT": servant_cmd}
            iv = fr(part["_seconds"])
            if iv:
                servant_attr["iv"] = iv
            hitattrs.append(servant_attr)
            continue
        if clear_once_per_action:
            once_per_action.clear()
        # parse part conds
        partcond = None
        if ctype := part.get("_conditionType"):
            condvalue = part["_conditionValue"]
            if ctype == PartConditionType.OwnerBuffCount:
                actcond = condvalue["_actionCondition"]
                if not actcond:
                    continue
                buffname = snakey(actcond.get("_Text") or "buff" + str(actcond.get("_Id")) or "mystery_buff", with_ext=False).lower()
                count = condvalue["_count"]
                compare = "var" + PART_COMPARISON_TO_VARS[condvalue["_compare"]]
                partcond = (compare, (buffname, count))
            elif ctype == PartConditionType.AuraLevel:
                partcond = ("ampcond", (condvalue["_aura"].value, condvalue["_target"], PART_COMPARISON_TO_VARS[condvalue["_compare"]], condvalue["_count"]))

            if partcond is not None:
                once_per_action = partcond_once_per_action[partcond]
                once_per_action.update(partcond_once_per_action[None])
            else:
                once_per_action = partcond_once_per_action[None]
        else:
            once_per_action = partcond_once_per_action[None]
        # get the hitattrs
        part_hitattr_map = {"_hitAttrLabelSubList": []}
        if raw_hitattrs := part.get("_allHitLabels"):
            for source, hitattr_lst in raw_hitattrs.items():
                for hitattr in hitattr_lst:
                    if isinstance(hitattr, str):
                        continue
                    if (not pattern or pattern.match(hitattr["_Id"])) and (attr := convert_hitattr(hitattr, part, action, once_per_action, meta=meta, skill=skill, partcond=partcond)):
                        if source == "_hitAttrLabelSubList":
                            part_hitattr_map[source].append(attr)
                        else:
                            part_hitattr_map[source] = attr
                        if additional := hitattr.get("_AdditionalRandomHitLabel"):
                            if len(additional) == 1:
                                additional = additional[0]
                                additional["_TargetGroup"] = hitattr["_TargetGroup"]
                                if add_attr := convert_hitattr(additional, part, action, once_per_action, meta=meta, skill=skill, partcond=partcond):
                                    if source == "_hitAttrLabelSubList":
                                        part_hitattr_map[source].append(add_attr)
                                    else:
                                        part_hitattr_map[source] = [attr, add_attr]
                        if not pattern:
                            break
        if not part_hitattr_map:
            continue
        part_hitattrs = []
        for key in ActionPartsHitLabel.LABEL_SORT:
            try:
                value = part_hitattr_map[key]
            except KeyError:
                continue
            # # heuristic for gala mascula
            # if key == "_hitAttrLabel" and part.get("_useAccurateCollisionHitInterval"):
            #     if part.get("_seconds") < accurate_col:
            #         continue
            #     accurate_ab_col = part.get("_seconds") + part.get("_collisionHitInterval")
            # if key == "_abHitAttrLabel" and part.get("_abUseAccurateCollisionHitInterval"):
            #     if part.get("_seconds") < accurate_ab_col:
            #         continue
            #     accurate_ab_col = part.get("_seconds") + part.get("_collisionHitInterval")
            if isinstance(value, list):
                part_hitattrs.extend(value)
            else:
                part_hitattrs.append(value)

        is_msl = True
        if part["commandType"] != CommandType.MULTI_BULLET and (blt := part.get("_bulletNum", 0)) > 1 and "_hitAttrLabel" in part_hitattr_map and not "extra" in part_hitattr_map["_hitAttrLabel"]:
            for hattr in (
                part_hitattr_map["_hitAttrLabel"],
                *part_hitattr_map["_hitAttrLabelSubList"],
            ):
                if delayfire := part.get("_delayFireSec"):
                    delayfire = [float(delay) for delay in json.loads(delayfire)]
                    if part.get("_removeStockBulletOnFinish"):
                        sec_key = "iv"
                        try:
                            del hattr["msl"]
                        except KeyError:
                            pass
                    else:
                        sec_key = "msl"
                        hattr[sec_key] = 0.0
                    bullet_attr, _ = clean_hitattr(hattr.copy(), once_per_action)
                    hattr[sec_key] = fr(hattr.get(sec_key, 0.0) + delayfire[0])
                    if not hattr[sec_key]:
                        del hattr[sec_key]
                    for i in range(1, blt):
                        cur_bullet_attr = bullet_attr.copy()
                        cur_bullet_attr[sec_key] = fr(cur_bullet_attr.get(sec_key, 0.0) + delayfire[i])
                        if not cur_bullet_attr[sec_key]:
                            del cur_bullet_attr[sec_key]
                        part_hitattrs.append(cur_bullet_attr)
                else:
                    last_copy, need_copy = clean_hitattr(hattr.copy(), once_per_action)
                    if need_copy:
                        part_hitattrs.append(last_copy)
                        part_hitattrs.append(blt - 1)
                        bullet_attr = last_copy
                    else:
                        part_hitattrs.append(blt)
                        bullet_attr = hattr
                    if delay := part.get("_delayTime", 0):
                        bullet_attr["msl"] = fr(delay)
                        if part.get("_isDelayAffectedBySpeedFactor"):
                            bullet_attr["msl_spd"] = 1
        gen, delay = None, None
        # part.get("_canBeSameTarget")
        if gen := part.get("_generateNum"):
            if blt := part.get("_bulletNum", 0):
                gen = blt
            delay = part.get("_generateDelay", 0)
            ref_attrs = part_hitattrs
        elif (abd := part.get("_abDuration", 0)) >= (abi := part.get("_abHitInterval", 0)) and "_abHitAttrLabel" in part_hitattr_map:
            gen = int(abd / abi)
            # some frame rate bullshit idk
            if gen * abi < abd - 10 / 60:
                gen += 1
            delay = abi
            try:
                part_hitattr_map["_abHitAttrLabel"]["msl"] += abi
            except KeyError:
                part_hitattr_map["_abHitAttrLabel"]["msl"] = abi
            part_hitattr_map["_abHitAttrLabel"]["msl"] = fr(part_hitattr_map["_abHitAttrLabel"]["msl"])
            ref_attrs = [part_hitattr_map["_abHitAttrLabel"]]
        elif (bci := part.get("_collisionHitInterval", 0)) and ((bld := part.get("_bulletDuration", 0)) > bci or (bld := part.get("_duration", 0)) > bci) and ("_hitLabel" in part_hitattr_map or "_hitAttrLabel" in part_hitattr_map):
            gen = int(bld / bci)
            # some frame rate bullshit idk
            if gen * bci < bld - 10 / 60:
                gen += 1
            delay = bci
            ref_attrs = []
            if part_hitattr_map.get("_hitLabel"):
                ref_attrs.append(part_hitattr_map.get("_hitLabel"))
            if part_hitattr_map.get("_hitAttrLabel"):
                ref_attrs.append(part_hitattr_map.get("_hitAttrLabel"))
                ref_attrs.extend(part_hitattr_map.get("_hitAttrLabelSubList"))
        # if adv is not None:
        #     print(adv.name)
        elif part.get("_loopFlag") and "_hitAttrLabel" in part_hitattr_map:
            loopnum = part.get("_loopNum", 0)
            loopsec = part.get("_loopSec")
            delay = part.get("_seconds") + (part.get("_loopFrame", 0) / 60)
            if loopsec := part.get("_loopSec"):
                gen = max(loopnum, int(loopsec // delay))
            else:
                gen = loopnum
            gen += 1
            ref_attrs = [
                part_hitattr_map["_hitAttrLabel"],
                *part_hitattr_map["_hitAttrLabelSubList"],
            ]
            is_msl = False
        gen_attrs = []
        timekey = "msl" if is_msl else "iv"
        if gen is not None and delay is not None:
            for gseq in range(1, gen):
                for attr in ref_attrs:
                    try:
                        gattr, _ = clean_hitattr(attr.copy(), once_per_action)
                    except AttributeError:
                        continue
                    if not gattr:
                        continue
                    if delay:
                        gattr[timekey] = fr(attr.get(timekey, 0) + delay * gseq)
                    gen_attrs.append(gattr)
        if part.get("_generateNumDependOnBuffCount"):
            # possible that this can be used with _generateNum
            buffcond = part["_buffCountConditionId"]
            buffname = snakey(buffcond["_Text"]).lower()
            gen = buffcond["_MaxDuplicatedCount"]
            try:
                bullet_timing = map(float, json.loads(part["_markerDelay"]))
            except KeyError:
                bullet_timing = (0,) * gen

            for idx, delay in enumerate(bullet_timing):
                if idx >= gen:
                    break
                delay = float(delay)
                for attr in part_hitattrs:
                    if idx == 0:
                        if delay:
                            attr[timekey] = fr(attr.get(timekey, 0) + delay)
                        if "cond" in attr:
                            attr["cond"] = ["and", attr["cond"], ["var>=", [buffname, idx + 1]]]
                        attr["cond"] = ["var>=", [buffname, idx + 1]]
                    else:
                        gattr, _ = clean_hitattr(attr.copy(), once_per_action)
                        if not gattr:
                            continue
                        if delay:
                            gattr[timekey] = fr(attr.get(timekey, 0) + delay)
                        if "cond" in gattr:
                            gattr["cond"] = ["and", gattr["cond"], ["var>=", [buffname, idx + 1]]]
                        gattr["cond"] = ["var>=", [buffname, idx + 1]]
                        gen_attrs.append(gattr)
        part_hitattrs.extend(gen_attrs)
        hitattrs.extend(part_hitattrs)
    once_per_action = set()
    return hitattrs


def convert_hitattr(hitattr, part, action, once_per_action, meta=None, skill=None, from_ab=False, partcond=None):
    if hitattr.get("_IgnoreFirstHitCheck"):
        once_per_action = set()
    attr = {}
    target = hitattr.get("_TargetGroup")
    if (target in (ActionTargetGroup.HOSTILE, ActionTargetGroup.HIT_OR_GUARDED_RECORD)) and hitattr.get("_DamageAdjustment"):
        attr["dmg"] = fr(hitattr.get("_DamageAdjustment"))
        killers = []
        for ks in ("_KillerState1", "_KillerState2", "_KillerState3"):
            if hitattr.get(ks):
                killers.append(hitattr.get(ks))
        if len(killers) > 0:
            try:
                attr["killer"] = [fr(hitattr["_KillerStateDamageRate"] - 1), killers]
            except KeyError:
                attr["killer_hitcount"] = [[(hc, fr(mod / 100)) for hc, mod in str_to_tuples(hitattr["_KillerStateDamageRateCurveDependsOnHitCount"])], killers]
        if crisis := hitattr.get("_CrisisLimitRate"):
            attr["crisis"] = fr(crisis - 1)
        if bufc := hitattr.get("_DamageUpRateByBuffCount"):
            attr["bufc"] = fr(bufc)
        if dragon := hitattr.get("_AttrDragon"):
            attr["drg"] = dragon
        if (od := hitattr.get("_ToBreakDmgRate")) and od != 1:
            attr["odmg"] = fr(od)
    if "sp" not in once_per_action:
        if sp := hitattr.get("_AdditionRecoverySp"):
            attr["sp"] = fr(sp)
            once_per_action.add("sp")
        elif sp_p := hitattr.get("_RecoverySpRatio"):
            attr["sp"] = [fr(sp_p), "%"]
            if (sp_i := hitattr.get("_RecoverySpSkillIndex")) or (sp_i := hitattr.get("_RecoverySpSkillIndex2")):
                attr["sp"].append(f"s{sp_i}")
            once_per_action.add("sp")
    if "dp" not in once_per_action and (dp := hitattr.get("_AdditionRecoveryDpLv1")):
        attr["dp"] = dp
        once_per_action.add("dp")
    if "utp" not in once_per_action and ((utp := hitattr.get("_AddUtp")) or (utp := hitattr.get("_AdditionRecoveryUtp"))):
        attr["utp"] = utp
        once_per_action.add("utp")
    if hp := hitattr.get("_SetCurrentHpRate"):
        attr["hp"] = [fr(hp * 100), "="]
    else:
        if hp := hitattr.get("_HpDrainLimitRate"):
            attr["hp"] = fr(hp * 100)
        if hp := hitattr.get("_ConsumeHpRate"):
            attr["hp"] = attr.get("hp", 0) - fr(hp * 100)
    if cp := hitattr.get("_RecoveryCP"):
        attr["cp"] = cp
    if heal := hitattr.get("_RecoveryValue"):
        if target in (ActionTargetGroup.MYPARTY, ActionTargetGroup.ALLY):
            attr["heal"] = [heal, "team"]
        elif target == ActionTargetGroup.ALLY_HP_LOWEST:
            attr["heal"] = [heal, "lowest"]
        else:
            attr["heal"] = heal
    # if (counter := hitattr.get("_DamageCounterCoef")) :
    #     attr["counter"] = counter
    if crit := hitattr.get("_AdditionCritical"):
        attr["crit"] = fr(crit)
    if aura_data := hitattr.get("_AuraId"):
        try:
            attr["amp"] = [str(aura_data["_Id"]), hitattr.get("_AuraMaxLimitLevel", 0), hitattr.get("_AuraTargetType", 0)]
        except KeyError:
            pass

    if part.get("commandType") == CommandType.STOCK_BULLET_FIRE:
        if (stock := part.get("_fireMaxCount", 0)) > 1:
            attr["extra"] = stock
        elif (stock := action.get("_MaxStockBullet", 0)) > 1:
            attr["extra"] = stock
    if bc := attr.get("_DamageUpRateByBuffCount"):
        attr["bufc"] = bc
    if 0 < (attenuation := part.get("_attenuationRate", 0)) < 1:
        attr["fade"] = fr(attenuation)

    # attr_tag = None
    if (actcond := hitattr.get("_ActionCondition1")) and actcond["_Id"] not in once_per_action:
        once_per_action.add(actcond["_Id"])
        # attr_tag = actcond['_Id']
        # if (remove := actcond.get('_RemoveConditionId')):
        #     attr['del'] = remove
        if actcond.get("_DamageLink"):
            return convert_hitattr(
                actcond["_DamageLink"],
                part,
                action,
                once_per_action,
                meta=meta,
                skill=skill,
            )
        convert_actcond(attr, actcond, target, part, meta=meta, skill=skill, from_ab=from_ab)

    if attr:
        # attr[f"DEBUG_FROM_SEQ"] = part.get("_seq", 0)
        attr_with_cond = None
        if partcond:
            # look man i just want partcond to sort first
            attr_with_cond = {"cond": partcond}
        elif ctype := part.get("_conditionType"):
            if ctype == PartConditionType.AllyHpRateLowest and "heal" in attr:
                attr["heal"] = [attr["heal"], "lowest"]
            else:
                attr_with_cond = {"DEBUG_PARTCOND": ctype.name + str(part["_conditionValue"])}
        if attr_with_cond:
            attr_with_cond.update(attr)
            attr = attr_with_cond
        iv = fr(part["_seconds"])
        if iv > 0:
            attr["iv"] = iv
        # if 'BULLET' in part['commandType']
        if delay := part.get("_delayTime", 0):
            attr["msl"] = fr(delay)
            if part.get("_isDelayAffectedBySpeedFactor"):
                attr["msl_spd"] = 1
        # if attr_tag:
        #     attr['tag'] = attr_tag
        if from_ab:
            attr["ab"] = 1
        return attr
    else:
        return None


TARGET_OVERWRITE_KEY = {
    ActionTargetGroup.MYSELF: "MYSELF",
    ActionTargetGroup.MYPARTY: "MYSELF",
    ActionTargetGroup.ALLY: "MYSELF",
}


def convert_actcond(attr, actcond, target, part={}, meta=None, skill=None, from_ab=False):
    if actcond.get("_EfficacyType") == AFF_RELIEF and (rate := actcond.get("_Rate", 0)) and target in {ActionTargetGroup.MYSELF, ActionTargetGroup.MYPARTY, ActionTargetGroup.ALLY}:
        attr["relief"] = [[actcond.get("_Type")], rate]
    elif actcond.get("_EfficacyType") == DISPEL and (rate := actcond.get("_Rate", 0)):
        attr["dispel"] = rate
    else:
        alt_buffs = []
        if meta and skill:
            for ehs, s in ENHANCED_SKILL.items():
                if (esk := actcond.get(ehs)) and not (isinstance(esk, int) or esk.get("_Id") in meta.all_chara_skills):
                    if existing_skill := meta.chara_skills.get(esk.get("_Id")):
                        group = existing_skill[0].split("_")[-1]
                    else:
                        eid = next(meta.eskill_counter)
                        group = "enhanced" if eid == 1 else f"enhanced{eid}"
                    meta.chara_skills[esk.get("_Id")] = (
                        f"s{s}_{group}",
                        s,
                        esk,
                        skill["_Id"],
                    )
                    alt_buffs.append(["sAlt", group, f"s{s}"])
            if isinstance((eba := actcond.get("_EnhancedBurstAttack")), dict):
                if meta and from_ab:
                    base_name = snakey(meta.name.lower()).replace("_", "")
                else:
                    base_name = "enhanced"
                group = base_name
                while group in meta.enhanced_fs and meta.enhanced_fs[group][1] != eba:
                    eid = next(meta.efs_counter)
                    group = f"{base_name}{eid}"
                meta.enhanced_fs[group] = group, eba, eba.get("_BurstMarkerId")
                alt_buffs.append(["fsAlt", group])

        if target == ActionTargetGroup.HOSTILE and (afflic := actcond.get("_Type")):
            affname = afflic.lower()
            attr["afflic"] = [affname, actcond["_Rate"]]
            if dot := actcond.get("_SlipDamagePower"):
                attr["afflic"].append(fr(dot))
            duration = fr(actcond.get("_DurationSec"))
            min_duration = fr(actcond.get("_MinDurationSec"))
            # duration = fr((duration + actcond.get('_MinDurationSec', duration)) / 2)
            if min_duration:
                if DEFAULT_AFF_DURATION[affname] != (min_duration, duration):
                    attr["afflic"].append(duration)
                    attr["afflic"].append(min_duration)
            elif DEFAULT_AFF_DURATION[affname] != duration:
                attr["afflic"].append(duration)
                duration = None
            if iv := actcond.get("_SlipDamageIntervalSec"):
                iv = fr(iv)
                if DEFAULT_AFF_IV[affname] != iv:
                    if duration:
                        attr["afflic"].append(duration)
                    attr["afflic"].append(iv)
        elif "Bleeding" == actcond.get("_Text"):
            attr["bleed"] = [actcond["_Rate"], fr(actcond["_SlipDamagePower"])]
        else:
            buffs = []
            negative_value = None
            is_duration_num = None
            for tsn, btype in TENSION_KEY.items():
                if v := actcond.get(tsn):
                    if target in (
                        ActionTargetGroup.ALLY,
                        ActionTargetGroup.MYPARTY,
                    ):
                        if part.get("_collisionParams_01", 0) > 1:
                            buffs.append([btype, v, "nearby"])
                        else:
                            buffs.append([btype, v, "team"])
                    else:
                        buffs.append([btype, v])
            if not buffs:
                if part.get("_lifetime"):
                    duration = fr(part.get("_lifetime"))
                    btype = "zone"
                elif actcond.get("_DurationNum") and not actcond.get("_DurationSec"):
                    duration = actcond.get("_DurationNum")
                    btype = "next"
                    is_duration_num = True
                else:
                    duration = actcond.get("_DurationSec", -1)
                    duration = fr(duration)
                    if target in (
                        ActionTargetGroup.ALLY,
                        ActionTargetGroup.MYPARTY,
                    ):
                        if part.get("_collisionParams_01", 0) > 1:
                            btype = "nearby"
                        else:
                            btype = "team"
                    else:
                        btype = "self"
                for b in alt_buffs:
                    if btype == "next" and b[0] in ("fsAlt", "sAlt"):
                        b.extend((-1, duration))
                    elif duration > -1:
                        b.append(duration)
                    buffs.append(b)
                if target == ActionTargetGroup.HOSTILE:
                    for k, mod in DEBUFFARG_KEY.items():
                        if value := actcond.get(k):
                            buffs.append(
                                [
                                    "debuff",
                                    fr(value),
                                    duration,
                                    actcond.get("_Rate") / 100,
                                    mod,
                                ]
                            )
                    for k, aff in AFFRES_KEY.items():
                        if value := actcond.get(k):
                            buffs.append(["affres", fr(value), duration, aff])
                    for k, eleres in ELERES_KEY.items():
                        if value := actcond.get(k):
                            buffs.append(["self", -fr(value), duration, eleres, "down"])
                else:
                    if addatk := actcond.get("_AdditionAttack"):
                        buffs.append(["echo", fr(addatk["_DamageAdjustment"]), duration])
                    if drain := actcond.get("_RateHpDrain"):
                        # FIXME: distinction between self vs team?
                        buffs.append(["drain", fr(drain), duration])
                    for k, aff in AFFRES_KEY.items():
                        if value := actcond.get(f"{k}Add"):
                            buffs.append(["affup", fr(value), duration, aff])
                    for k, mod in BUFFARG_KEY.items():
                        if value := actcond.get(k):
                            buffs.append([btype, fr(value), duration, *mod])
                            if negative_value is None:
                                negative_value = value < 0
                    interval = fr(actcond.get("_SlipDamageIntervalSec"))
                    if value := actcond.get("_RegenePower"):
                        buffs.append([btype, fr(value), [duration, interval], "heal", "hp"])
                    for slip_dmg, mult in (("_SlipDamagePower", -1), ("_SlipDamageRatio", -100), ("_SlipDamageFixed", -1)):
                        if value := actcond.get(slip_dmg):
                            value *= mult
                            if (afftype := actcond.get("_Type", "").lower()) in AFFLICTION_TYPES.values():
                                buffs.append(["selfaff", fr(value), [duration, interval], actcond.get("_Rate"), afftype, "regen", "hp"])
                                negative_value = True
                            else:
                                if actcond.get("_ValidRegeneHP"):
                                    buffs.append([btype, fr(value), [duration, interval], "regen", "hp"])
                                if actcond.get("_ValidRegeneSP"):
                                    # unclear what _SlipDamagePower for spwould imply :v
                                    sp_kind = "sp" if "_SlipDamageFixed" else "sp%"
                                    buffs.append([btype, fr(value), [duration, interval], "regen", sp_kind])
                                if negative_value is None:
                                    negative_value = value > 0
                    if negative_value is None:
                        negative_value = False
            if buffs:
                if len(buffs) == 1:
                    buffs = buffs[0]
                # if any(actcond.get(k) for k in AdvConf.OVERWRITE):
                #     buffs.append('-refresh')
                if (bele := actcond.get("_TargetElemental")) and target != ActionTargetGroup.HOSTILE:
                    attr["buffele"] = ele_bitmap(bele)
                if actcond.get("_OverwriteGroupId"):
                    target_name = TARGET_OVERWRITE_KEY.get(target, target.name)
                    buffs.append(f'-overwrite_{target_name}{actcond.get("_OverwriteGroupId")}')
                elif actcond.get("_Overwrite") or actcond.get("_OverwriteIdenticalOwner") or is_duration_num:
                    buffs.append("-refresh")
                attr["buff"] = buffs
                if target == ActionTargetGroup.HOSTILE or negative_value or actcond.get("_CurseOfEmptinessInvalid"):
                    attr["coei"] = 1


def hit_sr(action, startup=None, explicit_any=True):
    s, r = startup, None
    act_cancels = {}
    send_signals = {}
    last_r = None
    noaid_r = None
    noaid_follow = None
    motion = 0

    for part in action["_Parts"]:
        # find startup
        if s is None and part["commandType"] == CommandType.CHARACTER_COMMAND and part.get("_servantActionCommandId"):
            s = fr(part["_seconds"])
        if s is None and (hitlabels := part.get("_allHitLabels")):
            for hl_list in hitlabels.values():
                for hitlabel in hl_list:
                    if hitlabel["_TargetGroup"] != ActionTargetGroup.DUNOBJ:
                        s = fr(part["_seconds"])
        # find recovery
        if part["commandType"] == CommandType.ACTIVE_CANCEL:
            action_id = part.get("_actionId")
            if action_id is None and noaid_r is None:
                noaid_r = part["_seconds"]
                # act_cancels[("any", part.get("_actionType"))] = part["_seconds"]
                noaid_follow = (part["_seconds"], "any", part.get("_actionType"))
            if action_id:
                act_cancel_key = (action_id, part.get("_actionType"))
                if act_cancel_key in act_cancels:
                    act_cancels[act_cancel_key] = min(act_cancels[act_cancel_key], part["_seconds"])
                else:
                    act_cancels[act_cancel_key] = part["_seconds"]
            last_r = part["_seconds"]
        if part["commandType"] == CommandType.SEND_SIGNAL and part.get("_signalType") == ActionSignalType.Input:
            action_id = part.get("_actionId")
            if action_id:
                if action_id in send_signals:
                    send_signals[action_id] = min(send_signals[action_id], part["_seconds"])
                else:
                    send_signals[action_id] = part["_seconds"]
        if part["commandType"] == CommandType.PLAY_MOTION:
            if (animdata := part.get("_animation")) and isinstance(animdata, dict):
                motion = max(motion, part["_seconds"] + animdata["duration"])
            elif part.get("_motionState") in GENERIC_BUFF:
                motion = max(motion, 1.0)
    followed_by = set()
    for key, seconds in act_cancels.items():
        action_id, action_type = key
        seconds = max(seconds, send_signals.get(action_id, 0.0))
        followed_by.add((seconds, action_id, action_type))
    s = s or 0.0
    if explicit_any and (noaid_r is None or noaid_r <= motion):
        possible_r = (motion, noaid_r, last_r)
        if noaid_follow:
            followed_by.add(noaid_follow)
    else:
        possible_r = (noaid_r, motion, last_r)
    ridx = 0
    while ridx < len(possible_r) and (r is None or r < s or r == s == 0):
        r = possible_r[ridx]
        ridx += 1
    if r is not None:
        r = fr(r - s)
    else:
        r = None

    return s, r, followed_by


def hit_attr_adj(action, s, conf, pattern=None, skip_nohitattr=True, meta=None, skill=None, attr_key="attr", next_idx=0):
    if hitattrs := convert_all_hitattr(action, pattern=pattern, meta=meta, skill=skill):
        for attr in hitattrs:
            if not isinstance(attr, int) and "iv" in attr:
                attr["iv"] = fr(attr["iv"] - s)
                if attr["iv"] == 0:
                    del attr["iv"]
        conf[attr_key] = hitattrs
    if casting_action := action.get("_CastingAction"):
        _, s, _ = hit_sr(casting_action)
        conf["startup"] = s

    next_res = None
    if nextaction := action.get("_NextAction"):
        next_res = hit_attr_adj(
            nextaction,
            0.0,
            conf,
            pattern=pattern,
            skip_nohitattr=skip_nohitattr,
            meta=meta,
            skill=skill,
            attr_key=f"DEBUG_attr_N{next_idx+1}",
            next_idx=next_idx + 1,
        )

    if not hitattrs and not next_res and skip_nohitattr:
        return None
    return conf


def remap_stuff(conf, action_ids, parent_key=None, servant_attrs=None):
    # search the dict
    for key, subvalue in conf.copy().items():
        if key in ("interrupt", "cancel"):
            # map interrupt/cancel to conf names
            new_subdict = {}
            for idx, value in subvalue.items():
                try:
                    new_subdict[action_ids[idx]] = value[0]
                except KeyError:
                    if idx in DODGE_ACTIONS or value[1] in (ActionCancelType.Avoid, ActionCancelType.AvoidFront, ActionCancelType.AvoidBack):
                        idx = "dodge"
                    elif value[1] in (ActionCancelType.BurstAttack,):
                        idx = "fs"
                        # fs can never interrupt or cancel fs see Catherine
                        if parent_key.startswith("fs"):
                            continue
                    elif isinstance(idx, int):
                        continue
                    new_subdict[idx] = value[0]
            if "dodgeb" in new_subdict:
                if "dodge" in subvalue:
                    new_subdict["dodge"] = min(new_subdict["dodge"], new_subdict["dodgeb"])
                else:
                    new_subdict["dodge"] = new_subdict["dodgeb"]
                del new_subdict["dodgeb"]
            if new_subdict:
                conf[key] = dict(sorted(new_subdict.items()))
            else:
                del conf[key]
        elif key == "attr":
            if servant_attrs:
                new_attrs = []
                for attr in subvalue:
                    if servant_id := attr.get("DEBUG_SERVANT"):
                        for servant_attr in servant_attrs[servant_id]:
                            if "iv" in attr:
                                servant_attr["iv"] = attr["iv"]
                            elif "iv" in servant_attr:
                                del servant_attr["iv"]
                            servant_attr["msl"] += attr.get("msl", 0.0)
                            servant_attr["msl"] = fr(servant_attr["msl"])
                            new_attrs.append(servant_attr)
                    else:
                        new_attrs.append(attr)
                conf[key] = new_attrs
        elif isinstance(subvalue, dict):
            remap_stuff(subvalue, action_ids, parent_key=key, servant_attrs=servant_attrs)


def convert_following_actions(startup, followed_by, default=None):
    interrupt_by = {}
    cancel_by = {}
    if default:
        for act in default:
            interrupt_by[act] = (0.0, None)
            cancel_by[act] = (0.0, None)
    for t, act, kind in followed_by:
        if fr(t) < startup:
            if not act in interrupt_by or interrupt_by[act][0] > t:
                interrupt_by[act] = (fr(t), kind)
        else:
            if not act in cancel_by or cancel_by[act][0] > t:
                cancel_by[act] = (t, kind)
    for k in interrupt_by:
        cancel_by[k] = (0.0, interrupt_by[k][1])
    for act, value in cancel_by.items():
        t, kind = value
        cancel_by[act] = (fr(max(0.0, t - startup)), kind)
    return interrupt_by, cancel_by


def convert_x(xn, pattern=None, convert_follow=True, is_dragon=False):
    s, r, followed_by = hit_sr(xn)
    xconf = {"startup": s, "recovery": r}
    xconf = hit_attr_adj(xn, s, xconf, skip_nohitattr=False, pattern=pattern)

    if xn.get("_IsLoopAction") and any((xn["_Id"] == fb[1] for fb in followed_by)):
        xconf["loop"] = 1

    if convert_follow:
        xconf["interrupt"], xconf["cancel"] = convert_following_actions(s, followed_by, ("s",))

    return xconf


def convert_dodge(action, convert_follow=True):
    s, r, followed_by = hit_sr(action)
    dodgeconf = {"startup": s, "recovery": r}
    dodgeconf = hit_attr_adj(action, s, dodgeconf, skip_nohitattr=False, pattern=re.compile(r".*H0\d_LV01$"))
    if convert_follow:
        dodgeconf["interrupt"], dodgeconf["cancel"] = convert_following_actions(s, followed_by, ("s",))
    return dodgeconf


def convert_dash(action, convert_follow=True):
    s, r, followed_by = hit_sr(action)
    dashconf = {"startup": s, "recovery": r}
    if connect_c := action.get("_ConnectCombo"):
        dashconf["to_x"] = connect_c
    dashconf = hit_attr_adj(action, s, dashconf, skip_nohitattr=False, pattern=re.compile(r".*H0\d$"))
    if convert_follow:
        dashconf["interrupt"], dashconf["cancel"] = convert_following_actions(s, followed_by, ("s",))
    return dashconf


def convert_fs(burst, marker=None, cancel=None, is_dragon=False):
    startup, recovery, followed_by = hit_sr(burst)
    fsconf = {}
    if is_dragon:
        hitattr_pattern = re.compile(r"S\d{3}.*$")
        key = "dfs"
    else:
        hitattr_pattern = re.compile(r".*_LV02$")
        key = "fs"
    if not isinstance(marker, dict):
        fsconf[key] = hit_attr_adj(
            burst,
            startup,
            {"startup": startup, "recovery": recovery},
            hitattr_pattern,
        )
        if fsconf[key]:
            fsconf[key]["interrupt"], fsconf[key]["cancel"] = convert_following_actions(startup, followed_by, ("s",))
    else:
        mpart = None
        max_CHLV = 1
        CHLV = re.compile(r".*_LV02_CHLV0(\d)$")
        for part in burst["_Parts"]:
            if part.get("_allHitLabels"):
                for hl_list in part["_allHitLabels"].values():
                    for hitlabel in hl_list:
                        if res := CHLV.match(hitlabel["_Id"]):
                            max_CHLV = max(max_CHLV, int(res.group(1)))
        for part in marker["_Parts"]:
            if part["commandType"] == CommandType.GEN_MARKER:
                mpart = part
                break
        charge = 0.5
        if mpart is not None:
            charge = mpart.get("_chargeSec", 0.5)
        if not is_dragon and max_CHLV > 1:
            clv = list(map(float, [charge] + json.loads(mpart.get("_chargeLvSec"))))
            if mpart.get("_useForEachChargeTime"):
                clv = clv[:max_CHLV]
            elif aoci := mpart.get("_activateOnChargeImpact"):
                idx = 0
                for idx, value in enumerate(json.loads(aoci)):
                    if value == 0:
                        break
                clv = clv[: min(idx + 1, max_CHLV)]
            totalc = 0
            base_fs_conf = {"charge": fr(charge), "startup": startup, "recovery": recovery}
            for idx, c in enumerate(clv):
                if idx == 0:
                    clv_pattern = re.compile(r".*_LV02$")
                else:
                    clv_pattern = re.compile(f".*_LV02_CHLV0{idx+1}$")
                clv_attr = hit_attr_adj(burst, startup, base_fs_conf.copy(), clv_pattern)
                totalc += c
                if clv_attr:
                    fsn = f"{key}{idx+1}"
                    fsconf[fsn] = clv_attr
                    fsconf[fsn]["charge"] = fr(totalc)
                    fsconf[fsn]["interrupt"], fsconf[fsn]["cancel"] = convert_following_actions(startup, followed_by, ("s",))
        else:
            fsconf[key] = {"charge": fr(charge), "startup": startup, "recovery": recovery}
            fsconf[key] = hit_attr_adj(burst, startup, fsconf[key], hitattr_pattern, skip_nohitattr=False)
            fsconf[key]["interrupt"], fsconf[key]["cancel"] = convert_following_actions(startup, followed_by, ("s",))
        # charge = mpart.get("_chargeSec", 0.5)
        # fsconf[key] = {"charge": fr(charge), "startup": startup, "recovery": recovery}
        # if not is_dragon and (clv_max := mpart.get("_chargeLvMax")) and (clv := mpart.get("_chargeLvSec")):
        #     clv = list(map(float, [charge] + json.loads(clv)))
        #     totalc = 0
        #     for idx in range(0, clv_max):
        #         c = clv[idx]
        #         if idx == 0:
        #             clv_attr = hit_attr_adj(burst, startup, fsconf[f"fs"].copy(), re.compile(f".*_LV02$"))
        #         else:
        #             clv_attr = hit_attr_adj(
        #                 burst,
        #                 startup,
        #                 fsconf[f"fs"].copy(),
        #                 re.compile(f".*_LV02_CHLV0{idx+1}$"),
        #             )
        #         totalc += c
        #         if clv_attr:
        #             fsn = f"fs{idx+1}"
        #             fsconf[fsn] = clv_attr
        #             fsconf[fsn]["charge"] = fr(totalc)
        #             (
        #                 fsconf[fsn]["interrupt"],
        #                 fsconf[fsn]["cancel"],
        #             ) = convert_following_actions(startup, followed_by, ("s",))
        #     if "fs2" in fsconf and "attr" not in fsconf["fs"]:
        #         del fsconf["fs"]
        #     elif "fs1" in fsconf:
        #         fsconf["fs"] = fsconf["fs1"]
        #         del fsconf["fs1"]
        # else:
        #     fsconf[key] = hit_attr_adj(
        #         burst,
        #         startup,
        #         fsconf[key],
        #         hitattr_pattern,
        #         skip_nohitattr=False,
        #     )
        #     if fsconf[key]:
        #         fsconf[key]["interrupt"], fsconf[key]["cancel"] = convert_following_actions(startup, followed_by, ("s",))
    if not is_dragon and cancel is not None:
        fsconf["fsf"] = {
            "charge": fr(0.1 + cancel["_Parts"][0]["_duration"]),
            "startup": 0.0,
            "recovery": 0.0,
        }
        fsconf["fsf"]["interrupt"], fsconf["fsf"]["cancel"] = convert_following_actions(startup, followed_by, ("s",))

    return fsconf


class BaseConf(WeaponType):
    LABEL_MAP = {
        "AXE": "axe",
        "BOW": "bow",
        "CAN": "staff",
        "DAG": "dagger",
        "KAT": "blade",
        "LAN": "lance",
        "ROD": "wand",
        "SWD": "sword",
        "GUN": "gun",
    }
    GUN_MODES = (40, 41, 42)

    def __init__(self, index):
        self.action_ids = {}
        return super().__init__(index)

    def process_result(self, res, full_query=True):
        conf = {"lv2": {}}
        if res["_Label"] != "GUN":
            fs_id = res["_BurstPhase1"]
            res = super().process_result(res, full_query=True)
            # fs_delay = {}
            fsconf = convert_fs(res["_BurstPhase1"], res["_ChargeMarker"], res["_ChargeCancel"])
            # startup = fsconf["fs"]["startup"]
            # for x, delay in fs_delay.items():
            #     fsconf['fs'][x] = {'startup': fr(startup+delay)}
            if fsconf:
                self.action_ids[res["_BurstPhase1"]["_Id"]] = "fs"
            conf.update(fsconf)
            for n in range(1, 6):
                try:
                    xn = res[f"_DefaultSkill0{n}"]
                except KeyError:
                    break
                conf[f"x{n}"] = convert_x(xn)
                # for part in xn['_Parts']:
                #     if part['commandType'] == 'ACTIVE_CANCEL' and part.get('_actionId') == fs_id and part.get('_seconds'):
                #         fs_delay[f'x{n}'] = part.get('_seconds')
                self.action_ids[xn["_Id"]] = f"x{n}"
                if hitattrs := convert_all_hitattr(xn, re.compile(r".*H0\d_LV02$")):
                    for attr in hitattrs:
                        attr["iv"] = fr(attr["iv"] - conf[f"x{n}"]["startup"])
                        if attr["iv"] == 0:
                            del attr["iv"]
                    conf["lv2"][f"x{n}"] = {"attr": hitattrs}
        else:
            # gun stuff
            self.action_ids[res["_BurstPhase1"]] = "fs"
            for mode in BaseConf.GUN_MODES:
                mode = self.index["CharaModeData"].get(mode, full_query=True)
                mode_name = f'gun{mode["_GunMode"]}'
                if burst := mode.get("_BurstAttackId"):
                    marker = burst.get("_BurstMarkerId")
                    for fs, fsc in convert_fs(burst, marker).items():
                        conf[f"{fs}_{mode_name}"] = fsc
                        self.action_ids[burst["_Id"]] = "fs"
                if (xalt := mode.get("_UniqueComboId")) and isinstance(xalt, dict):
                    for prefix in ("", "Ex"):
                        if xalt.get(f"_{prefix}ActionId"):
                            for n, xn in enumerate(xalt[f"_{prefix}ActionId"]):
                                n += 1
                                xn_key = f"x{n}_{mode_name}{prefix.lower()}"
                                if xaltconf := convert_x(xn):
                                    conf[xn_key] = xaltconf
                                self.action_ids[xn["_Id"]] = f"x{n}"
                                if hitattrs := convert_all_hitattr(xn, re.compile(r".*H0\d_LV02$")):
                                    for attr in hitattrs:
                                        attr["iv"] = fr(attr["iv"] - conf[xn_key]["startup"])
                                        if attr["iv"] == 0:
                                            del attr["iv"]
                                    conf["lv2"][xn_key] = {"attr": hitattrs}

        remap_stuff(conf, self.action_ids)

        return conf

    @staticmethod
    def outfile_name(res, ext):
        return BaseConf.LABEL_MAP[res["_Label"]] + ext

    def export_all_to_folder(self, out_dir="./out", ext=".json"):
        out_dir = os.path.join(out_dir, "base")
        all_res = self.get_all()
        check_target_path(out_dir)
        for res in tqdm(all_res, desc=os.path.basename(out_dir)):
            out_name = self.outfile_name(res, ext)
            res = self.process_result(res)
            output = os.path.join(out_dir, out_name)
            with open(output, "w", newline="", encoding="utf-8") as fp:
                # json.dump(res, fp, indent=2, ensure_ascii=False)
                fmt_conf(res, f=fp)
                fp.write("\n")


class SkillProcessHelper:
    def reset_meta(self):
        self.chara_skills = {}
        self.eskill_counter = itertools.count(start=1)
        self.efs_counter = itertools.count(start=1)
        self.all_chara_skills = {}
        self.enhanced_fs = {}
        self.ab_alt_attrs = defaultdict(lambda: [])
        self.action_ids = {}
        # for advs only
        self.alt_actions = []
        self.utp_chara = None
        self.dragon_hitattrshift = False
        self.sigil_mode = None

    def convert_skill(self, k, seq, skill, lv, no_loop=False):
        action = 0
        if lv >= skill.get("_AdvancedSkillLv1", float("inf")):
            skey_pattern = "_AdvancedActionId{}"
            action = skill.get(skey_pattern.format(1))
        if isinstance(action, int):
            skey_pattern = "_ActionId{}"
            action = skill.get("_ActionId1")

        startup, recovery, followed_by = hit_sr(action, startup=0)

        if not recovery:
            AdvConf.MISSING_ENDLAG.append(skill.get("_Name"))

        sconf = {
            "sp": skill.get(f"_SpLv{lv}", skill.get("_Sp", 0)),
            "startup": startup,
            "recovery": recovery,
        }

        hitlabel_pattern = re.compile(f".*LV0{lv}$")
        sconf = hit_attr_adj(
            action,
            sconf["startup"],
            sconf,
            skip_nohitattr=False,
            pattern=hitlabel_pattern,
            meta=self,
            skill=skill,
        )
        hitattrs = sconf.get("attr")
        if (not hitattrs or all(["dmg" not in attr for attr in hitattrs if isinstance(attr, dict)])) and skill.get(f"_IsAffectedByTensionLv{lv}"):
            sconf["energizable"] = bool(skill[f"_IsAffectedByTensionLv{lv}"])

        interrupt, cancel = convert_following_actions(0, followed_by)
        if interrupt:
            sconf["interrupt"] = interrupt
        if cancel:
            sconf["cancel"] = cancel

        for idx in range(2, 5):
            if rng_actions := skill.get(skey_pattern.format(idx)):
                hit_attr_adj(
                    rng_actions,
                    sconf["startup"],
                    sconf,
                    skip_nohitattr=False,
                    pattern=hitlabel_pattern,
                    meta=self,
                    skill=skill,
                    attr_key=f"DEBUG_attr_R{idx}",
                )

        if isinstance((transkills := skill.get("_TransSkill")), dict):
            for idx, ts in enumerate(transkills.items()):
                tsid, tsk = ts
                if tsid not in self.all_chara_skills:
                    self.chara_skills[tsid] = (
                        f"{k}_phase{idx+1}",
                        seq,
                        tsk,
                        skill.get("_Id"),
                    )
            k = f"{k}_phase1"
        try:
            for tbuff in skill["_TransBuff"]["_Parts"]:
                if not tbuff.get("_allHitLabels"):
                    continue
                for hl_list in tbuff["_allHitLabels"].values():
                    for hitlabel in hl_list:
                        if (actcond := hitlabel.get("_ActionCondition1")) and actcond.get("_CurseOfEmptinessInvalid"):
                            sconf["phase_coei"] = True
        except KeyError:
            pass

        if isinstance((chainskills := skill.get("_ChainGroupId")), list):
            for idx, cs in enumerate(chainskills):
                cskill = cs["_Skill"]
                activate = cs.get("_ActivateCondition", 0)
                if cskill["_Id"] not in self.all_chara_skills:
                    self.chara_skills[cskill["_Id"]] = (
                        f"s{seq}_chain{activate}",
                        seq,
                        cskill,
                        skill.get("_Id"),
                    )

        if isinstance((ocskill := skill.get("_OverChargeSkillId")), dict):
            n = 1
            prev_sid = skill.get("_Id")
            prev_entry = None
            while prev_sid in self.chara_skills:
                prev_entry = self.chara_skills[prev_sid]
                if not "_overcharge" in prev_entry[0]:
                    break
                n += 1
                prev_sid = prev_entry[3]
            base = k.split("_", 1)[0]
            self.chara_skills[ocskill["_Id"]] = (
                f"{base}_overcharge{n}",
                seq,
                ocskill,
                skill.get("_Id"),
            )

        if ab := skill.get(f"_Ability{lv}"):
            self.parse_skill_ab(k, seq, skill, action, sconf, ab)

        return sconf, k, action

    def parse_skill_ab(self, k, seq, skill, action, sconf, ab):
        if isinstance(ab, int):
            ab = self.index["AbilityData"].get(ab)
        for a in (1, 2, 3):
            ab_type = ab.get(f"_AbilityType{a}")
            if ab_type == AbilityType.ReferenceOther:
                for k in ("a", "b", "c"):
                    if sub_ab := ab.get(f"_VariousId{a}{k}"):
                        self.parse_skill_ab(k, seq, skill, action, sconf, sub_ab)
            if ab_type == AbilityType.EnhancedSkill:  # alt skill
                s = int(ab[f"_TargetAction{a}"].name[-1])
                eid = next(self.eskill_counter)
                if existing_skill := self.chara_skills.get(ab[f"_VariousId{a}a"]["_Id"]):
                    group = existing_skill[0].split("_")[-1]
                else:
                    eid = next(self.eskill_counter)
                    group = "enhanced" if eid == 1 else f"enhanced{eid}"
                self.chara_skills[ab[f"_VariousId{a}a"]["_Id"]] = (
                    f"s{s}_{group}",
                    s,
                    ab[f"_VariousId{a}a"],
                    ab[f"_VariousId{a}a"]["_Id"],
                )
            elif ab_type == AbilityType.ChangeState:
                condtype = ab.get("_ConditionType")
                hitattr = ab.get(f"_VariousId{a}str")
                if not hitattr:
                    actcond = ab.get(f"_VariousId{a}a")
                    if (condtype == AbilityCondition.SP1_LESS and actcond.get("_AutoRegeneS1")) or (condtype == AbilityCondition.SP2_LESS and actcond.get("_UniqueRegeneSp01")):
                        sconf["sp_regen"] = float_ceil(
                            sconf["sp"],
                            -actcond.get("_SlipDamageRatio") / actcond.get("_SlipDamageIntervalSec"),
                        )
                        continue
                    hitattr = {"_ActionCondition1": ab.get(f"_VariousId{a}a")}
                if not (attr := convert_hitattr(hitattr, DUMMY_PART, action, set(), meta=self, skill=skill)):
                    continue
                if cooltime := ab.get("_CoolTime"):
                    attr["cd"] = cooltime
                if condtype in HP_GEQ:
                    attr["cond"] = ["hp>", fr(ab["_ConditionValue"])]
                elif condtype in HP_LEQ:
                    attr["cond"] = ["hp<=", fr(ab["_ConditionValue"])]
                confkey = "attr" if ab.get("_OnSkill") == seq else f"DEBUG_attr_{condtype.name}"
                try:
                    sconf[confkey].insert(0, attr)
                except KeyError:
                    sconf[confkey] = [attr]
                # for ehs, s in ENHANCED_SKILL.items():
                #     if (esk := actcond.get(ehs)) :
                #         if existing_skill := self.chara_skills.get(esk.get("_Id")):
                #             group = existing_skill[0].split("_")[-1]
                #         else:
                #             eid = next(self.eskill_counter)
                #             group = "enhanced" if eid == 1 else f"enhanced{eid}"
                #         self.chara_skills[esk["_Id"]] = (
                #             f"s{s}_{group}",
                #             s,
                #             esk,
                #             esk["_Id"],
                #         )

    def search_abs(self, ab):
        if not ab:
            return
        for i in (1, 2, 3):
            ab_type = ab.get(f"_AbilityType{i}")
            if ab_type == AbilityType.ReferenceOther:
                for sfx in ("a", "b", "c"):
                    self.search_abs(ab.get(f"_VariousId{i}{sfx}"))
            elif ab_type == AbilityType.ChangeState:
                hitattr = ab.get(f"_VariousId{i}str")
                if not hitattr:
                    actcond = ab.get(f"_VariousId{i}a")
                    if actcond:
                        hitattr = {"_ActionCondition1": actcond}
                if hitattr:
                    if sid := ab.get("_OnSkill"):
                        self.ab_alt_attrs[sid].append((ab, hitattr))
                    elif actcond := hitattr.get("_ActionCondition1"):
                        if isinstance((eba := actcond.get("_EnhancedBurstAttack")), dict):
                            base_name = snakey(self.name.lower()).replace("_", "")
                            group = base_name
                            while group in self.enhanced_fs and self.enhanced_fs[group][1] != eba:
                                eid = next(self.efs_counter)
                                group = f"{base_name}{eid}"
                            self.enhanced_fs[group] = group, eba, eba.get("_BurstMarkerId")
            elif ab_type == AbilityType.EnhancedSkill:
                s = int(ab[f"_TargetAction{i}"].name[-1])
                alt_skill = ab[f"_VariousId{i}a"]
                eid = next(self.eskill_counter)
                if existing_skill := self.chara_skills.get(alt_skill["_Id"]):
                    group = existing_skill[0].split("_")[-1]
                else:
                    eid = next(self.eskill_counter)
                    group = "enhanced" if eid == 1 else f"enhanced{eid}"
                self.chara_skills[alt_skill["_Id"]] = (
                    f"s{s}_{group}",
                    s,
                    alt_skill,
                    alt_skill["_Id"],
                )
            elif ab_type == AbilityType.EnhancedBurstAttack:
                self.alt_actions.append(("fs", ab[f"_VariousId{i}a"]))
            elif ab_type == AbilityType.UniqueAvoid:
                self.alt_actions.append(("dodge", ab[f"_VariousId{i}a"]))
            elif ab_type == AbilityType.UniqueTransform:
                self.utp_chara = (ab.get(f"_VariousId{i}a", 0), ab.get(f"_VariousId{i}str"))
            elif ab_type == AbilityType.HitAttributeShift:
                self.dragon_hitattrshift = True
            elif ab_type == AbilityType.ChangeMode and ab.get(f"_ConditionType") == AbilityCondition.BUFF_DISAPPEARED and ab["_ConditionValue"]["_Id"] == 1152:
                # 1152 is sigil debuff
                self.sigil_mode = ab.get(f"_VariousId{i}a") + 1

    def process_skill(self, res, conf, mlvl, all_levels=False):
        # exceptions exist
        while self.chara_skills:
            k, seq, skill, prev_id = next(iter(self.chara_skills.values()))
            self.all_chara_skills[skill.get("_Id")] = (k, seq, skill, prev_id)
            if seq == 99:
                lv = mlvl[res["_EditSkillLevelNum"]]
            else:
                lv = mlvl.get(seq, 2)
            cskill, k, action = self.convert_skill(k, seq, skill, lv)
            for ab, hitattr in self.ab_alt_attrs.get(seq, []):
                attr = {}
                condtype = ab.get("_ConditionType")
                if not (
                    attr := convert_hitattr(
                        hitattr,
                        DUMMY_PART,
                        action,
                        set(),
                        meta=self,
                        skill=skill,
                        from_ab=True,
                    )
                ):
                    continue
                if cooltime := ab.get("_CoolTime"):
                    attr["cd"] = cooltime
                if condtype in HP_GEQ:
                    attr["cond"] = ["hp>", fr(ab["_ConditionValue"])]
                elif condtype in HP_LEQ:
                    attr["cond"] = ["hp<=", fr(ab["_ConditionValue"])]
                try:
                    cskill["attr"].insert(0, attr)
                except KeyError:
                    cskill["attr"] = [attr]
            conf[k] = cskill
            self.action_ids[action.get("_Id")] = k
            del self.chara_skills[skill.get("_Id")]

        for efs, eba, emk in self.enhanced_fs.values():
            for fs, fsc in convert_fs(eba, emk).items():
                conf[f"{fs}_{efs}"] = fsc
                self.action_ids[eba["_Id"]] = f"{fs}_{efs}"


class AdvConf(CharaData, SkillProcessHelper):
    MISSING_ENDLAG = []
    DO_NOT_FIND_LOOP = (
        10350302,  # summer norwin
        10650101,  # gala sarisse
    )
    SPECIAL_EDIT_SKILL = {103505044: 2, 105501025: 1, 109501023: 1, 104501034: 1}
    EX_CATEGORY_NAMES = {
        1: "Lance",
        2: "Blade",
        3: "Axe",
        4: "Bow",
        5: "Sword",
        6: "Wand",
        7: "Dagger",
        8: "Staff",
        # 9: "Gala_Prince",
        10: "Wand2",
        12: "Axe2",
        # 13: "Tobias",
        16: "Peony",
        # 17: "Grace",
        # 18: "Chrom",
        # 19: "Sharena",
        20: "Dagger2",
        22: "Gun",
        # 23: "Kimono_Elisanne",
        # 24: "Panther",
        # 25: "Joker",
        26: "Mona",
    }
    SERVANT_TO_DACT = (
        (1, "dx1"),
        (2, "dx2"),
        (3, "dx3"),
        (4, "dx4"),
        (5, "dx5"),
        (6, "ds1"),
        (7, "ds2"),
    )

    def process_result(self, res, condense=True, all_levels=False, force_50mc=False):
        self.set_animation_reference(res)
        self.reset_meta()

        ab_lst = []
        if force_50mc:
            res = dict(res)
            res["_MaxLimitBreakCount"] = 4
        spiral = res["_MaxLimitBreakCount"] == 5
        for i in (1, 2, 3):
            found = 1
            for j in (3, 2, 1):
                if ab := res.get(f"_Abilities{i}{j}"):
                    if force_50mc and found > 0:
                        found -= 1
                        continue
                    ab_lst.append(self.index["AbilityData"].get(ab, full_query=True))
                    break
        converted, skipped = convert_all_ability(ab_lst)
        res = self.condense_stats(res)
        conf = {
            "c": {
                "name": res.get("_SecondName", res.get("_Name")),
                "icon": f'{res["_BaseId"]:06}_{res["_VariationId"]:02}_r{res["_Rarity"]:02}',
                "att": res["_MaxAtk"],
                "hp": res["_MaxHp"],
                "ele": ELEMENTS[res["_ElementalType"]].lower(),
                "wt": WEAPON_TYPES[res["_WeaponType"]].lower(),
                "spiral": spiral,
                "a": converted,
                # 'skipped': skipped
            }
        }
        # hecc
        if res["_Id"] == 10450404:
            conf["c"]["name"] = "Sophie (Persona)"
        if conf["c"]["wt"] == "gun":
            conf["c"]["gun"] = []
        self.name = conf["c"]["name"]

        for ab in ab_lst:
            self.search_abs(ab)

        if self.utp_chara is not None:
            conf["c"]["utp"] = [self.utp_chara[0]] + [int(v) for v in self.utp_chara[1].split("/")]

        if avoid_on_c := res.get("_AvoidOnCombo"):
            actdata = self.index["PlayerAction"].get(avoid_on_c)
            conf["dodge_on_x"] = convert_dodge(actdata)
            self.action_ids[actdata["_Id"]] = "dodge"

        if burst := res.get("_BurstAttack"):
            burst = self.index["PlayerAction"].get(res["_BurstAttack"])
            if burst and (marker := burst.get("_BurstMarkerId")):
                conf.update(convert_fs(burst, marker))
                self.action_ids[burst["_Id"]] = "fs"

        for act, actdata in self.alt_actions:
            if not actdata:
                continue
            actconf = None
            if act == "fs" and (marker := actdata.get("_BurstMarkerId")):
                actconf = convert_fs(actdata, marker)["fs"]
                if act in conf:
                    act = f"{act}_abalt"
            elif act == "dodge":
                actconf = convert_dodge(actdata)
                # hax for lv1 of the ability
                self.action_ids[actdata["_Id"] - 1] = "dodge"
            if actconf:
                conf[act] = actconf
                self.action_ids[actdata["_Id"]] = act

        if conf["c"]["spiral"]:
            mlvl = {1: 4, 2: 3}
        else:
            mlvl = {1: 3, 2: 2}

        for s in (1, 2):
            if sdata := res.get(f"_Skill{s}"):
                skill = self.index["SkillData"].get(sdata, full_query=True)
                self.chara_skills[sdata] = (f"s{s}", s, skill, None)

        if (edit := res.get("_EditSkillId")) and edit not in self.chara_skills:
            skill = self.index["SkillData"].get(res[f"_EditSkillId"], full_query=True)
            self.chara_skills[res["_EditSkillId"]] = (f"s99", 99, skill, None)

        if udrg := res.get("_UniqueDragonId"):
            udform_key = "dservant" if self.utp_chara and self.utp_chara[0] == 2 else "dragonform"
            conf[udform_key] = self.index["DrgConf"].get(udrg, by="_Id", hitattrshift=self.dragon_hitattrshift, mlvl=mlvl if res.get("_IsConvertDragonSkillLevel") else None)
            del conf[udform_key]["d"]
            self.action_ids.update(self.index["DrgConf"].action_ids)
            # dum
            self.set_animation_reference(res)

        base_mode_burst, base_mode_x = None, None
        for m in range(1, 5):
            if mode := res.get(f"_ModeId{m}"):
                mode_name = None
                if not isinstance(mode, dict):
                    mode = self.index["CharaModeData"].get(mode, full_query=True)
                    if not mode:
                        continue
                if gunkind := mode.get("_GunMode"):
                    conf["c"]["gun"].append(gunkind)
                    if mode["_Id"] in BaseConf.GUN_MODES:
                        continue
                    # if not any([mode.get(f'_Skill{s}Id') for s in (1, 2)]):
                    #     continue
                if m == 2 and self.utp_chara is not None and self.utp_chara[0] != 1:
                    mode_name = "_ddrive"
                elif self.sigil_mode is not None and m == self.sigil_mode:
                    mode_name = "_sigil"
                else:
                    try:
                        mode_name = "_" + snakey(mode["_ActionId"]["_Parts"][0]["_actionConditionId"]["_Text"].split(" ")[0].lower())
                    except:
                        if m == 1:
                            mode_name = ""
                        else:
                            mode_name = f"_mode{m}"
                for s in (1, 2):
                    if skill := mode.get(f"_Skill{s}Id"):
                        self.chara_skills[skill.get("_Id")] = (
                            f"s{s}{mode_name}",
                            s,
                            skill,
                            None,
                        )
                if (burst := mode.get("_BurstAttackId")) and base_mode_burst != burst["_Id"]:
                    marker = burst.get("_BurstMarkerId")
                    if not marker:
                        marker = self.index["PlayerAction"].get(burst["_Id"] + 4)
                    fs = None
                    for fs, fsc in convert_fs(burst, marker).items():
                        conf[f"{fs}{mode_name}"] = fsc
                    if fs:
                        self.action_ids[burst["_Id"]] = "fs"
                    if not mode_name:
                        base_mode_burst = burst["_Id"]
                if ((xalt := mode.get("_UniqueComboId")) and isinstance(xalt, dict)) and base_mode_x != xalt["_Id"]:
                    xalt_pattern = re.compile(r".*H0\d_LV02$") if conf["c"]["spiral"] else None
                    for prefix in ("", "Ex"):
                        if xalt.get(f"_{prefix}ActionId"):
                            for n, xn in enumerate(xalt[f"_{prefix}ActionId"]):
                                n += 1
                                if not mode_name and prefix:
                                    xn_key = f"x{n}_{prefix.lower()}"
                                else:
                                    xn_key = f"x{n}{mode_name}{prefix.lower()}"
                                if xaltconf := convert_x(xn, pattern=xalt_pattern):
                                    conf[xn_key] = xaltconf
                                    self.action_ids[xn["_Id"]] = xn_key
                                elif xalt_pattern is not None and (xaltconf := convert_x(xn)):
                                    conf[xn_key] = xaltconf
                                    self.action_ids[xn["_Id"]] = xn_key
                    if not mode_name:
                        base_mode_x = xalt["_Id"]
                        if xalt["_MaxComboNum"] < 5:
                            conf["default"] = {"x_max": xalt["_MaxComboNum"]}
                if dashondodge := mode.get("_DashOnAvoid"):
                    if dashconf := convert_dash(dashondodge):
                        conf["dash"] = dashconf
                        self.action_ids[dashondodge["_Id"]] = "dash"
        try:
            conf["c"]["gun"] = list(set(conf["c"]["gun"]))
        except KeyError:
            pass

        # self.abilities = self.last_abilities(res, as_mapping=True)
        # pprint(self.abilities)
        # for k, seq, skill in self.chara_skills.values():

        self.process_skill(res, conf, mlvl, all_levels=all_levels)
        self.edit_skill_idx = 0
        if edit := res.get("_EditSkillId"):
            try:
                self.edit_skill_idx = self.SPECIAL_EDIT_SKILL[edit]
            except KeyError:
                self.edit_skill_idx = self.all_chara_skills[edit][1]

        try:
            self.action_ids.update(self.base_conf.action_ids)
        except AttributeError:
            pass

        for dodge in map(res.get, ("_Avoid", "_BackAvoidOnCombo")):
            if dodge:
                self.action_ids[dodge] = "dodge"

        servant_attrs = None
        if self.utp_chara and self.utp_chara[0] == 2:
            # build fake servant attrs
            servant_attrs = {}
            for servant_id, dact in self.SERVANT_TO_DACT:
                if not (dact_conf := conf["dservant"].get(dact)) or not (dact_attrs := dact_conf.get("attr")):
                    continue
                servant_attrs[servant_id] = []
                for attr in dact_attrs:
                    try:
                        del attr["sp"]
                    except KeyError:
                        pass
                    attr = dict(attr)
                    if servant_id == 6:
                        # man i fucking hate cykagames
                        attr["gluca"] = 1
                    attr["msl"] = dact_conf.get("startup") + attr.get("iv", 0.0) + attr.get("msl", 0.0)
                    servant_attrs[servant_id].append(attr)
        remap_stuff(conf, self.action_ids, servant_attrs=servant_attrs)

        return conf

    def get(self, name, all_levels=False):
        res = super().get(name, full_query=False)
        if isinstance(res, list):
            res = res[0]
        return self.process_result(res, all_levels=all_levels)

    @staticmethod
    def outfile_name(conf, ext, variant=None):
        if variant is not None:
            return snakey(conf["c"]["name"]) + "." + variant + ext
        return snakey(conf["c"]["name"]) + ext

    def skillshare_data(self, res):
        res_data = {}
        if res["_HoldEditSkillCost"] != 10:
            res_data["limit"] = res["_HoldEditSkillCost"]
        if res["_EditSkillRelationId"] > 1:
            modifiers = self.index["EditSkillCharaOffset"].get(res["_EditSkillRelationId"], by="_EditSkillRelationId")[0]
            if modifiers["_SpOffset"] > 1:
                res_data["mod_sp"] = modifiers["_SpOffset"]
            if modifiers["_StrengthOffset"] != 0.699999988079071:
                res_data["mod_att"] = modifiers["_StrengthOffset"]
            if modifiers["_BuffDebuffOffset"] != 1:
                res_data["mod_buff"] = modifiers["_BuffDebuffOffset"]
        if res.get("_EditSkillId", 0) > 0 and res.get("_EditSkillCost", 0) > 0:
            skill = self.index["SkillData"].get(res["_EditSkillId"])
            res_data["s"] = self.edit_skill_idx
            if res["_MaxLimitBreakCount"] >= 5:
                sp_lv = 4
            else:
                sp_lv = 3
            if res["_EditSkillLevelNum"] == 2:
                sp_lv -= 1
            # res_data['name'] = snakey(skill['_Name'])
            res_data["cost"] = res["_EditSkillCost"]
            res_data["type"] = skill["_SkillType"]
            # sp_s_list = [
            #     skill['_SpEdit'],
            #     skill['_SpLv2Edit'],
            #     skill['_SpLv3Edit'],
            #     skill['_SpLv4Edit'],
            # ]
            res_data["sp"] = skill[f"_SpLv{sp_lv}Edit"]
        return res_data

    def exability_data(self, res):
        ex_res = self.index["ExAbilityData"].get(res["_ExAbilityData5"])
        ex_ab, ex_skipped = convert_exability(ex_res)
        chain_res = self.index["AbilityData"].get(res.get("_ExAbility2Data5"), full_query=True)
        chain_ab, chain_skipped = convert_ability(chain_res, chains=True)
        if len(chain_ab) > 1:
            print(res)
        entry = {
            "category": ex_res.get("_Category"),
            "ex": ex_ab,
            "chain": chain_ab,
            # "skipped": ex_skipped + chain_skipped,
        }
        if not chain_res.get("_ElementalType") and chain_ab:
            entry["ALL_ELE_CHAIN"] = True
        return entry

    def sort_exability_data(self, exability_data):
        ex_by_ele = defaultdict(set)
        ex_by_category = {}
        catagorized_names = defaultdict(set)
        all_ele_chains = {}
        for ele, exabs in exability_data.items():
            for name, entry in exabs.items():
                cat = entry["category"]
                ex_by_ele[ele].add(cat)
                if cat not in ex_by_category or (entry["ex"] and ex_by_category[cat]["ex"][0][1] < entry["ex"][0][1]):
                    ex_by_category[cat] = {
                        "category": cat,
                        "ex": entry["ex"],
                        "chain": [],
                    }
                catagorized_names[cat].add(name)
                if entry.get("ALL_ELE_CHAIN"):
                    del entry["ALL_ELE_CHAIN"]
                    all_ele_chains[name] = entry
        extra_data = {}
        extra_data["generic"] = {}
        extra_data["any"] = {}
        for cat, entry in ex_by_category.items():
            try:
                catname = AdvConf.EX_CATEGORY_NAMES[cat]
            except KeyError:
                if cat not in catagorized_names:
                    continue
                catname = sorted(catagorized_names[cat])[0]
                if len(catagorized_names[cat]) > 1:
                    print(f"More than 1 name for EX category {cat}: {catagorized_names[cat]}, picked {catname}")
            entry["category"] = catname
            if all((cat in eleset for eleset in ex_by_ele.values())):
                extra_data["generic"][catname] = entry
                for name in catagorized_names[cat]:
                    for exabs in exability_data.values():
                        try:
                            if not exabs[name]["chain"]:
                                del exabs[name]
                            else:
                                exabs[name]["category"] = catname
                        except KeyError:
                            pass
            else:
                if entry["ex"] and not entry["ex"][0][0].startswith("ele_"):
                    extra_data["any"][catname] = entry
                for name in catagorized_names[cat]:
                    for exabs in exability_data.values():
                        try:
                            exabs[name]["category"] = catname
                        except KeyError:
                            pass
        extra_data["any"].update(all_ele_chains)
        exability_data.update(extra_data)

    def export_all_to_folder(self, out_dir="./out", ext=".json"):
        # do this here in order to have the action ids from generic weapon
        self.base_conf = BaseConf(self.index)
        self.base_conf.export_all_to_folder(out_dir=out_dir)

        all_res = self.get_all(where="_ElementalType != 99 AND _IsPlayable = 1")
        # ref_dir = os.path.join(out_dir, '..', 'adv')
        skillshare_out = os.path.join(out_dir, f"skillshare{ext}")
        exability_out = os.path.join(out_dir, f"exability{ext}")
        advout_dir = os.path.join(out_dir, "adv")
        check_target_path(advout_dir)
        skillshare_data = {}
        exability_data = {ele.lower(): {} for ele in ELEMENTS.values()}

        for res in tqdm(all_res, desc=os.path.basename(advout_dir)):
            try:
                if res.get("_UniqueGrowMaterialId1") and res.get("_UniqueGrowMaterialId2"):
                    outconf = self.process_result(res, force_50mc=True)
                    out_name = self.outfile_name(outconf, ext, variant="50MC")
                    output = os.path.join(advout_dir, out_name)
                    with open(output, "w", newline="", encoding="utf-8") as fp:
                        fmt_conf(outconf, f=fp)
                        fp.write("\n")
                outconf = self.process_result(res)
                out_name = self.outfile_name(outconf, ext)
                if ss_res := self.skillshare_data(res):
                    skillshare_data[snakey(outconf["c"]["name"])] = ss_res
                if ex_res := self.exability_data(res):
                    exability_data[snakey(outconf["c"]["ele"])][snakey(outconf["c"]["name"])] = ex_res
                output = os.path.join(advout_dir, out_name)
                with open(output, "w", newline="", encoding="utf-8") as fp:
                    fmt_conf(outconf, f=fp)
                    fp.write("\n")
            except Exception as e:
                print(res["_Id"], res.get("_SecondName", res.get("_Name")), flush=True)
                raise e
        if AdvConf.MISSING_ENDLAG:
            print("Missing endlag for:", AdvConf.MISSING_ENDLAG)
        with open(skillshare_out, "w", newline="") as fp:
            fmt_conf(skillshare_data, f=fp)
            fp.write("\n")
        self.sort_exability_data(exability_data)
        with open(exability_out, "w", newline="") as fp:
            fmt_conf(exability_data, f=fp, lim=3, sortlim=2)
            fp.write("\n")


HP_GEQ = (
    AbilityCondition.HP_MORE,
    AbilityCondition.HP_MORE_MOMENT,
    AbilityCondition.HP_MORE_NOT_EQ_MOMENT,
    AbilityCondition.HP_MORE_NO_SUPPORT_CHARA,
)
HP_LEQ = (
    AbilityCondition.HP_LESS,
    AbilityCondition.HP_NOREACH,
    AbilityCondition.HP_LESS_MOMENT,
    AbilityCondition.HP_LESS_NOT_EQ_MOMENT,
    AbilityCondition.HP_NOREACH_NO_SUPPORT_CHARA,
)


def ab_cond(ab, chains=False):
    cond = ab.get("_ConditionType")
    condval = ab.get("_ConditionValue")
    condval2 = ab.get("_ConditionValue2")
    ele = ab.get("_ElementalType")
    wep = ab.get("_WeaponType")
    cparts = []
    if ele and not chains:
        cparts.append(ele.lower())
    if wep:
        cparts.append(wep.lower())
    try:
        condval = int(condval)
    except TypeError:
        condval = 0
    try:
        condval2 = int(condval2)
    except TypeError:
        condval2 = 0
    if cond in HP_GEQ:
        cparts.append(f"hp{condval}")
    elif cond in HP_LEQ:
        cparts.append(f"hp≤{condval}")
    elif cond == AbilityCondition.TOTAL_HITCOUNT_MORE:
        cparts.append(f"hit{condval}")
    elif cond == AbilityCondition.ON_BUFF_FIELD:
        cparts.append("zone")
    elif cond == AbilityCondition.UNIQUE_TRANS_MODE:
        cparts.append("ddrive")
    elif cond == AbilityCondition.HAS_AURA_TYPE:
        if condval2 == 1:
            target = "self"
        else:
            target = "team"
        cparts.append(f"amp_{condval}_{target}")
    elif cond == AbilityCondition.SELF_AURA_LEVEL_MORE:
        cparts.append(f"amp_{condval}_self_{condval2}")
    elif cond == AbilityCondition.PARTY_AURA_LEVEL_MORE:
        cparts.append(f"amp_{condval}_team_{condval2}")
    if cparts:
        return "_".join(cparts)


AB_STATS = {
    AbilityStat.Hp: "hp",
    AbilityStat.Atk: "a",
    AbilityStat.Spr: "sp",
    AbilityStat.Dpr: "dh",
    AbilityStat.DragonTime: "dt",
    AbilityStat.AttackSpeed: "spd",
    AbilityStat.BurstSpeed: "fspd",
    AbilityStat.ChargeSpeed: "cspd",
}


def ab_stats(**kwargs):
    if (stat := AB_STATS.get(kwargs.get("var_a"))) and (upval := kwargs.get("upval")):
        if kwargs.get("ex") and stat in "a":
            return [stat, upval / 100, "ex"]
        res = [stat, upval / 100]
        if condstr := ab_cond(kwargs.get("ab"), kwargs.get("chains")):
            res.append(condstr)
        return res


def ab_aff_edge(**kwargs):
    if a_id := kwargs.get("var_a"):
        res = [f"edge_{a_id}", kwargs.get("upval")]
        if condstr := ab_cond(kwargs.get("ab"), kwargs.get("chains")):
            res.append(condstr)
        return res


def ab_damage(**kwargs):
    if upval := kwargs.get("upval"):
        res = None
        target = kwargs.get("target")
        astr = None
        condstr = None
        if target == AbilityTargetAction.SKILL_ALL:
            astr = "s"
        elif target == AbilityTargetAction.BURST_ATTACK:
            astr = "fs"
        elif target == AbilityTargetAction.COMBO:
            astr = "x"
        if astr:
            if kwargs.get("ex"):
                return [astr, upval / 100, "ex"]
            res = [astr, upval / 100]
        else:
            cond = kwargs.get("ab").get("_ConditionType")
            if cond == AbilityCondition.DEBUFF_SLIP_HP:
                res = ["bleed", upval / 100]
            elif cond == AbilityCondition.OVERDRIVE:
                res = ["od", upval / 100]
            elif cond == AbilityCondition.BREAKDOWN:
                res = ["bk", upval / 100]
            elif cond == AbilityCondition.DEBUFF:
                condval = kwargs.get("ab").get("_ConditionValue")
                if condval == 3:
                    res = ["k_debuff_def", upval / 100]
                elif condval == 21:
                    res = ["k_debuff", upval / 100]
                elif condval == 2:
                    res = ["k_debuff_attack", upval / 100]
        condstr = ab_cond(kwargs.get("ab"), kwargs.get("chains"))
        if res:
            if condstr:
                res.append(condstr)
            return res


VALUE_CONDS = {
    AbilityCondition.TOTAL_HITCOUNT_MORE: "hitcount",
    AbilityCondition.HP_MORE_MOMENT: "hpmore",
    AbilityCondition.HP_MORE: "hpmore",
    AbilityCondition.HP_LESS: "hpless",
}
OTHER_CONDS = {
    AbilityCondition.SKILLCONNECT_SKILL1_MOMENT: "primed",
    AbilityCondition.ON_BUFF_FIELD: "poised",
    AbilityCondition.GET_BUFF_TENSION: "energy",
}
ACTCOND_TO_AB = {
    "_RateAttack": "att",
    "_RateCritical": "crit_chance",
    "_EnhancedCritical": "crit_damage",
    "_RateDefense": "defense",
    "_RegenePower": "heal",
    "_RateAttackSpeed": "spd_buff",
    "_RateBurst": "fs_buff",
}


def check_duration_and_cooltime(ab, actcond, extra_args, default_duration=15, default_cooltime=10):
    if (duration := actcond.get("_DurationSec")) != default_duration:
        extra_args.append(fr(duration or -1))
    if (cooltime := ab.get("_CoolTime")) and cooltime != default_cooltime:
        if not extra_args:
            extra_args.append(fr(duration or -1))
        extra_args.append(fr(cooltime))


def ab_actcond(**kwargs):
    ab = kwargs["ab"]
    actcond = kwargs.get("var_a")
    if not actcond:
        if var_str := kwargs.get("var_str"):
            actcond = var_str.get("_ActionCondition1")
    cond = ab.get("_ConditionType")
    astr = None
    extra_args = []
    if cond == AbilityCondition.GET_BUFF_DEF:
        astr = "bc"
        check_duration_and_cooltime(ab, actcond, extra_args, default_cooltime=None)
    elif cond == AbilityCondition.HP_LESS_MOMENT:
        if ab.get("_OccurenceNum"):
            astr = "lo"
        elif ab.get("_MaxCount") == 5:
            astr = "uo"
        elif ab.get("_MaxCount") == 3:
            astr = "ro"
        else:
            condval = ab.get("_ConditionValue")
            if condval == int(condval):
                condval = int(condval)
            astr = f"hpless_{condval}"
            check_duration_and_cooltime(ab, actcond, extra_args)
    elif cond == AbilityCondition.HITCOUNT_MOMENT:
        if ab.get("_TargetAction") == AbilityTargetAction.BURST_ATTACK:
            return [
                "fsprep",
                ab.get("_OccurenceNum"),
                fr(kwargs.get("var_str").get("_RecoverySpRatio")),
            ]
        if val := actcond.get("_Tension"):
            return ["ecombo", int(ab.get("_ConditionValue"))]
    elif cond == AbilityCondition.QUEST_START:
        if val := actcond.get("_Tension"):
            return ["eprep", int(val)]
        elif val := actcond.get("_RateAttack"):
            return ["bprep_att", fr(val), fr(actcond.get("_DurationSec"))]
    elif cond == AbilityCondition.TRANSFORM_DRAGON:
        astr = "dshift"
        modtype = None
        shift_values = []
        for actcond in (kwargs.get("var_a"), kwargs.get("var_b"), kwargs.get("var_c")):
            if not actcond:
                continue
            if actcond.get("_DurationSec"):
                return None
            if val := actcond.get("_RateSkill"):
                c_modtype = "s"
            elif val := actcond.get("_RateDefense"):
                c_modtype = "defense"
            elif val := actcond.get("_RateAttack"):
                c_modtype = "att"
            if modtype is not None and c_modtype != modtype:
                # not generic dshift
                return None
            modtype = c_modtype
            shift_values.append(fr(val))
        if modtype is None:
            return None
        return [f"{astr}_{modtype}", *shift_values]
    elif cond == AbilityCondition.KILL_ENEMY:
        if ab.get("_TargetAction") == AbilityTargetAction.BURST_ATTACK:
            astr = "sts"
        else:
            astr = "sls"
    elif cond in (
        AbilityCondition.CAUSE_ABNORMAL_STATUS,
        AbilityCondition.DAMAGED_ABNORMAL_STATUS,
    ):
        affname = AFFLICTION_TYPES[ab.get("_ConditionValue")]
        if cond == AbilityCondition.CAUSE_ABNORMAL_STATUS:
            affstr = "aff"
        else:
            affstr = "res"
        if var_str.get("_TargetGroup") in (
            ActionTargetGroup.ALLY,
            ActionTargetGroup.MYPARTY,
        ):
            astr = f"{affstr}team_{affname}"
        else:
            astr = f"{affstr}self_{affname}"
        check_duration_and_cooltime(ab, actcond, extra_args)
    elif cond == AbilityCondition.TENSION_MAX_MOMENT:
        astr = "energized"
        check_duration_and_cooltime(ab, actcond, extra_args, default_cooltime=None)
    elif cond == AbilityCondition.GET_HEAL:
        astr = "healed"
        check_duration_and_cooltime(ab, actcond, extra_args)
    elif cond == AbilityCondition.DAMAGED:
        astr = "damaged"
        if count := actcond.get("_DurationNum"):
            extra_args.append(count)
        else:
            check_duration_and_cooltime(ab, actcond, extra_args, default_cooltime=5)
    elif cond in (AbilityCondition.AVOID, AbilityCondition.JUST_AVOID):
        astr = "dodge"
        if cond == AbilityCondition.JUST_AVOID:
            check_duration_and_cooltime(ab, actcond, extra_args, default_duration=-1, default_cooltime=-1)
            extra_args.append("iframe")
        else:
            check_duration_and_cooltime(ab, actcond, extra_args, default_cooltime=15)
    elif cond in VALUE_CONDS:
        condval = ab.get("_ConditionValue")
        if condval == int(condval):
            condval = int(condval)
        astr = f"{VALUE_CONDS[cond]}_{condval}"
    elif cond in OTHER_CONDS:
        astr = OTHER_CONDS[cond]
    if astr:
        full_astr, value = None, None
        if val := actcond.get("_Tension"):
            if astr == "energy":
                full_astr = "eextra"
                value = ab.get("_Probability") / 100
            else:
                full_astr = f"{astr}_energy"
                value = int(val)
                if astr == "bc" and len(extra_args) == 1:
                    extra_args = tuple()
        elif val := actcond.get("_Inspiration"):
            full_astr = f"{astr}_inspiration"
            value = int(val)
        elif (regen := actcond.get("_SlipDamageRatio")) and actcond.get("_ValidRegeneHP"):
            full_astr = f"{astr}_regen"
            value = fr(regen * -100)
        else:
            for key, suffix in ACTCOND_TO_AB.items():
                if val := actcond.get(key):
                    full_astr = f"{astr}_{suffix}"
                    value = fr(val)
                    break
        if full_astr and value:
            return [full_astr, value, *extra_args]


def ab_prep(**kwargs):
    ab = kwargs["ab"]
    upval = kwargs.get("upval", 0)
    astr = "prep"
    if ab.get("_OnSkill") == 99:
        astr = "scharge_all"
        upval /= 100
    if condstr := ab_cond(ab, kwargs.get("chains")):
        return [astr, upval, condstr]
    return [astr, upval]


def ab_generic(name, div=100):
    def ab_whatever(**kwargs):
        if upval := kwargs.get("upval"):
            res = [name, fr(upval / div)]
            if condstr := ab_cond(kwargs.get("ab"), kwargs.get("chains")):
                res.append(condstr)
            return res

    return ab_whatever


def ab_bufftime(**kwargs):
    if upval := kwargs.get("upval"):
        res = ["bt", fr(upval / 100)]
        if kwargs.get("ex"):
            res.append("ex")
        elif condstr := ab_cond(kwargs.get("ab"), kwargs.get("chains")):
            res.append(condstr)
        return res


def ab_aff_k(**kwargs):
    if a_id := kwargs.get("var_a"):
        res = [f"k_{a_id}", kwargs.get("upval") / 100]
        if condstr := ab_cond(kwargs.get("ab"), kwargs.get("chains")):
            res.append(condstr)
        return res


def ab_typenum_k(**kwargs):
    if a_vals := kwargs.get("var_str"):
        return ["affnumkiller", [float(i) / 100 for i in a_vals.split("/")]]


def ab_tribe_k(**kwargs):
    if a_id := kwargs.get("var_a"):
        res = [f"k_{TRIBE_TYPES.get(a_id, a_id)}", kwargs.get("upval") / 100]
        if condstr := ab_cond(kwargs.get("ab"), kwargs.get("chains")):
            res.append(condstr)
        return res


def ab_aff_res(**kwargs):
    if a_id := kwargs.get("var_a"):
        ab = kwargs.get("ab")
        aff = a_id
        if aff == "all" and (count := ab.get("_OccurenceNum")):
            res = ["affshield", count]
        else:
            res = [f"affres_{aff}", kwargs.get("upval")]
        if condstr := ab_cond(ab, kwargs.get("chains")):
            res.append(condstr)
        return res


def ab_psalm(**kwargs):
    ab = kwargs.get("ab")
    return [
        "psalm",
        ab["_BaseCrestGroupId"],
        ab["_TriggerBaseCrestGroupCount"],
        int(kwargs.get("upval")),
    ]


def ab_eledmg(**kwargs):
    return [f"ele_{kwargs.get('var_a').lower()}", kwargs.get("upval") / 100]


def ab_dpcharge(**kwargs):
    ab = kwargs.get("ab")
    if ab.get("_ConditionType") == AbilityCondition.HITCOUNT_MOMENT:
        return [f"dpcombo", int(ab.get("_ConditionValue"))]


def ab_cc(**kwargs):
    if upval := kwargs.get("upval"):
        upval = fr(upval / 100)
        ab = kwargs.get("ab")
        cond = ab.get("_ConditionType")
        condval = ab.get("_ConditionValue")
        condval2 = ab.get("_ConditionValue2")
        if cond == AbilityCondition.HITCOUNT_MOMENT_TIMESRATE:
            return ["critcombo", upval, condval, condval2]
        res = ["cc", upval]
        if condstr := ab_cond(ab, kwargs.get("chains")):
            res.append(condstr)
        return res


def ab_afftime(**kwargs):
    if a_id := kwargs.get("var_a"):
        res = [f"afftime_{a_id}", kwargs.get("upval") / 100]
        if condstr := ab_cond(kwargs.get("ab"), kwargs.get("chains")):
            res.append(condstr)
        return res


def ab_crisis(**kwargs):
    target = kwargs.get("target")
    if target == AbilityTargetAction.SKILL_ALL:
        mod = "s"
    elif target == AbilityTargetAction.BURST_ATTACK:
        mod = "fs"
    elif target == AbilityTargetAction.COMBO:
        mod = "x"
    return [f"crisis_{mod}", fr(kwargs.get("upval") / 100 - 1)]


ABILITY_CONVERT = {
    AbilityType.StatusUp: ab_stats,
    AbilityType.ActAddAbs: ab_aff_edge,
    AbilityType.ActDamageUp: ab_damage,
    AbilityType.ActCriticalUp: ab_cc,
    AbilityType.ActBreakUp: ab_generic("odaccel"),
    AbilityType.AddRecoverySp: ab_generic("spf"),
    AbilityType.AddRecoveryDp: ab_actcond,
    AbilityType.SpCharge: ab_prep,
    AbilityType.BuffExtension: ab_bufftime,
    AbilityType.DebuffExtension: ab_generic("dbt"),
    AbilityType.AbnormalKiller: ab_aff_k,
    AbilityType.CriticalDamageUp: ab_generic("cd"),
    AbilityType.DpCharge: ab_generic("dp", 1),
    AbilityType.DragonDamageUp: ab_generic("da"),
    AbilityType.DebuffTimeExtensionForSpecificDebuffs: ab_generic("dbt"),
    AbilityType.ActKillerTribe: ab_tribe_k,
    AbilityType.ChangeState: ab_actcond,
    AbilityType.ChainTimeExtension: ab_generic("ctime", 1),
    AbilityType.ResistAbs: ab_aff_res,
    AbilityType.CrestGroupScoreUp: ab_psalm,
    AbilityType.ActRecoveryUp: ab_generic("rcv"),
    AbilityType.EnhancedElementDamage: ab_eledmg,
    AbilityType.DpChargeMyParty: ab_dpcharge,
    AbilityType.AbnoramlExtension: ab_afftime,
    AbilityType.CrisisRate: ab_crisis,
    AbilityType.AbnormalTypeNumKiller: ab_typenum_k,
}
SPECIAL_AB = {
    448: ["spu", 0.08],
    1402: ["au", 0.08],
    2366: ["ccu", 0.1],
    2369: ["cdu", 0.21],
    1776: ["corrosion", 3],
    400000858: ["poised_shadowblight-killer_passive", 0.08],
}


def convert_ability(ab, skip_abtype=tuple(), chains=False):
    if special_ab := SPECIAL_AB.get(ab.get("_Id")):
        return [special_ab], []
    converted = []
    skipped = []
    for i in (1, 2, 3):
        if not f"_AbilityType{i}" in ab:
            continue
        atype = ab[f"_AbilityType{i}"]
        if atype in skip_abtype:
            continue
        if convert_a := ABILITY_CONVERT.get(atype):
            try:
                res = convert_a(
                    ab=ab,
                    target=ab.get(f"_TargetAction{i}"),
                    upval=ab.get(f"_AbilityType{i}UpValue"),
                    var_a=ab.get(f"_VariousId{i}a"),
                    var_b=ab.get(f"_VariousId{i}b"),
                    var_c=ab.get(f"_VariousId{i}c"),
                    var_str=ab.get(f"_VariousId{i}str"),
                    chains=chains,
                )
            except Exception as e:
                res = None
            if res:
                converted.append(res)
        elif atype == AbilityType.ReferenceOther:
            for a in ("a", "b", "c"):
                if subab := ab.get(f"_VariousId{i}{a}"):
                    sub_c, sub_s = convert_ability(subab, skip_abtype=skip_abtype)
                    converted.extend(sub_c)
                    skipped.extend(sub_s)
    if not converted:
        skipped.append((ab.get("_Id"), ab.get("_Name")))
    return converted, skipped


def convert_exability(ab):
    converted = []
    skipped = []
    for i in (1, 2, 3):
        if not f"_AbilityType{i}" in ab:
            continue
        atype = ab[f"_AbilityType{i}"]
        if convert_a := ABILITY_CONVERT.get(atype):
            try:
                res = convert_a(
                    ab=ab,
                    target=ab.get(f"_TargetAction{i}"),
                    upval=ab.get(f"_AbilityType{i}UpValue0"),
                    var_a=ab.get(f"_VariousId{i}"),
                    ex=True,
                )
            except:
                res = None
            if res:
                converted.append(res)
        elif atype == AbilityType.ReferenceOther:
            for a in ("a", "b", "c"):
                if subab := ab.get(f"_VariousId{i}{a}"):
                    sub_c, sub_s = convert_exability(subab)
                    converted.extend(sub_c)
                    skipped.extend(sub_s)
    if not converted:
        skipped.append((ab.get("_Id"), ab.get("_Name")))
    return converted, skipped


def convert_all_ability(ab_lst, skip_abtype=tuple()):
    all_c, all_s = [], []
    for ab in ab_lst:
        converted, skipped = convert_ability(ab, skip_abtype=skip_abtype)
        all_c.extend(converted)
        all_s.extend(skipped)
    return all_c, all_s


# ALWAYS_KEEP = {400127, 400406, 400077, 400128, 400092, 400410}
class WpConf(AbilityCrest):
    HDT_PRINT = {
        "name": "High Dragon Print",
        "icon": "400072_02",
        "hp": 83,
        "att": 20,
        "rarity": 1,
        "union": 0,
        "a": [["res_hdt", 0.25]],
    }
    SKIP_AB = (AbilityType.ResistAbs,)
    # 7(burn) and 13(poison) have self inflictions, do not skip
    SKIP_BOON = (0, 8, 9, 10, 13, 14, 15, 16)

    def __init__(self, index):
        super().__init__(index)
        self.boon_names = {res["_Id"]: res["_Name"] for res in self.index["UnionAbility"].get_all()}

    def process_result(self, res):
        ab_lst = []
        for i in (1, 2, 3):
            k = f"_Abilities{i}3"
            if ab := res.get(k):
                ab_lst.append(self.index["AbilityData"].get(ab, full_query=True))
        converted, skipped = convert_all_ability(ab_lst, skip_abtype=WpConf.SKIP_AB)

        boon = res.get("_UnionAbilityGroupId", 0)
        if boon in WpConf.SKIP_BOON:
            if not converted:
                return
            # if converted[0][0].startswith("sts") or converted[0][0].startswith("sls"):
            #     return

        if res.get("_IsHideChangeImage"):
            icon = f'{res["_BaseId"]}_01'
        else:
            icon = f'{res["_BaseId"]}_02'
        conf = {
            "name": res["_Name"].strip(),
            "icon": icon,
            "att": res["_MaxAtk"],
            "hp": res["_MaxHp"],
            "rarity": res["_CrestSlotType"],
            "union": boon,
            "a": converted,
            # 'skipped': skipped
        }
        return conf

    def export_all_to_folder(self, out_dir="./out", ext=".json"):
        all_res = self.get_all()
        check_target_path(out_dir)
        outdata = {}
        skipped = []
        collisions = defaultdict(list)
        for res in tqdm(all_res, desc="wp"):
            conf = self.process_result(
                res,
            )
            if conf:
                qual_name = snakey(res["_Name"])
                if qual_name in outdata:
                    collisions[qual_name].append(outdata[qual_name])
                    collisions[qual_name].append(conf)
                else:
                    outdata[qual_name] = conf
            else:
                skipped.append((res["_BaseId"], res["_Name"]))
                # skipped.append(res["_Name"])
        outdata["High_Dragon_Print"] = WpConf.HDT_PRINT
        for qual_name, duplicates in collisions.items():
            if len({dupe["union"] for dupe in duplicates}) == len(duplicates):
                for dupe in duplicates:
                    dupe["name"] = f"{dupe['name']} ({self.boon_names[dupe['union']]})"
                    outdata[snakey(dupe["name"].replace("'s Boon", ""))] = dupe
                del outdata[qual_name]
            else:
                print(f"Check dupe {qual_name}")
        output = os.path.join(out_dir, "wyrmprints.json")
        with open(output, "w", newline="", encoding="utf-8") as fp:
            # json.dump(res, fp, indent=2, ensure_ascii=False)
            fmt_conf(outdata, f=fp)
            fp.write("\n")
        # print('Skipped:', skipped)

    def get(self, name):
        res = super().get(name, full_query=False)
        if isinstance(res, list):
            res = res[0]
        return self.process_result(res)


class DrgConf(DragonData, SkillProcessHelper):
    EXTRA_DRAGONS = (
        20050102,
        20050202,
        20050302,
        20050402,
        20050502,
        20050507,
    )
    COMMON_ACTIONS = {"dodge": {}, "dodgeb": {}, "dshift": {}}
    COMMON_ACTIONS_DEFAULTS = {
        # recovery only
        "dodge": 0.66667,
        "dodgeb": 0.66667,
        "dshift": 0.69444,
    }

    def convert_skill(self, k, seq, skill, lv, no_loop=False):
        conf, k, action = super().convert_skill(k, seq, skill, lv, no_loop=no_loop)
        conf["sp_db"] = skill.get("_SpLv2Dragon", 45)
        conf["uses"] = skill.get("_MaxUseNum", 1)
        if self.hitattrshift:
            del conf["attr"]
            hit_attr_adj(action, conf["startup"], conf, pattern=re.compile(f".*\d_LV0{lv}.*"))
            hit_attr_adj(action, conf["startup"], conf, pattern=re.compile(f".*\d(_HAS)?_LV0{lv}.*"), attr_key="attr_HAS")
        else:
            try:
                attr = conf["attr"]
                del conf["attr"]
                conf["attr"] = attr
            except KeyError:
                pass
        return conf, k, action

    def process_result(self, res, remap=True, hitattrshift=False, mlvl=None):
        super().process_result(res)
        self.reset_meta()
        self.hitattrshift = hitattrshift

        max_lb = res.get("_MaxLimitBreakCount", 4)
        att = res["_MaxAtk"]
        hp = res["_MaxHp"]
        if max_lb == 5:
            ab_seq = 6
            att = res.get("_AddMaxAtk1", 0)
            hp = res.get("_AddMaxHp1", 0)
        else:
            ab_seq = 5

        ab_lst = []
        for i in (1, 2):
            if ab := res.get(f"_Abilities{i}{ab_seq}"):
                ab_lst.append(ab)
        converted, skipped = convert_all_ability(ab_lst)

        conf = {
            "d": {
                "name": res.get("_SecondName", res.get("_Name")),
                "icon": f'{res["_BaseId"]}_{res["_VariationId"]:02}',
                "att": att,
                "hp": hp,
                "ele": ELEMENTS.get(res["_ElementalType"]).lower(),
                "a": converted,
            }
        }
        # if skipped:
        #     conf['d']['skipped'] = skipped

        for act, key in (
            ("dodgeb", "_AvoidActionBack"),
            ("dodge", "_AvoidActionFront"),
            ("dshift", "_Transform"),
        ):
            try:
                s, r, _ = hit_sr(res[key], startup=0.0, explicit_any=False)
            except KeyError:
                continue
                # try:
                #     DrgConf.COMMON_ACTIONS[act][tuple(actconf['attr'][0].items())].add(conf['d']['name'])
                # except KeyError:
                #     DrgConf.COMMON_ACTIONS[act][tuple(actconf['attr'][0].items())] = {conf['d']['name']}
            actconf = {}
            if DrgConf.COMMON_ACTIONS_DEFAULTS[act] != r:
                actconf = {"recovery": r}
            if act == "dshift":
                hitattrs = convert_all_hitattr(res[key])
                if hitattrs and (len(hitattrs) > 1 or hitattrs[0]["dmg"] != 2.0 or set(hitattrs[0].keys()) != {"dmg"}):
                    actconf["attr"] = hitattrs
                if hitattrshift:
                    if hitattrs := convert_all_hitattr(res[key], pattern=re.compile(r".*_HAS")):
                        actconf["attr_HAS"] = hitattrs
            if actconf:
                conf[act] = actconf

            self.action_ids[res[key]["_Id"]] = act

        if burst := res.get("_BurstAttack"):
            conf.update(convert_fs(burst, burst.get("_BurstMarkerId"), is_dragon=True))
            self.action_ids[burst["_Id"]] = "dfs"

        if "dodgeb" in conf:
            if "dodge" not in conf or conf["dodge"]["recovery"] > conf["dodgeb"]["recovery"]:
                conf["dodge"] = conf["dodgeb"]
                conf["dodge"]["backdash"] = True
            del conf["dodgeb"]

        dcombo = res["_DefaultSkill"]
        dcmax = res["_ComboMax"]
        for n, xn in enumerate(dcombo):
            n += 1
            xn_key = f"dx{n}"
            if dxconf := convert_x(xn, convert_follow=True, is_dragon=True):
                conf[xn_key] = dxconf
                self.action_ids[xn["_Id"]] = xn_key
            if hitattrshift:
                hit_attr_adj(xn, conf[xn_key]["startup"], conf[xn_key], pattern=re.compile(r".*_HAS"), skip_nohitattr=True, attr_key="attr_HAS")

        for act, seq, key in (
            ("ds1", 1, "_Skill1"),
            ("ds2", 2, "_Skill2"),
        ):
            if not (dskill := res.get(key)):
                continue
            self.chara_skills[dskill["_Id"]] = (act, seq, dskill, None)
        dsfinal = res.get("_SkillFinalAttack")
        dsfinal_act = None
        if dsfinal:
            dsfinal_act = self.chara_skills.get(dsfinal["_Id"], (None,))[0]
            if dsfinal and not dsfinal_act:
                self.chara_skills[dsfinal["_Id"]] = ("ds99", 99, dsfinal, None)

        self.process_skill(res, conf, mlvl or {1: 2, 2: 2})
        if dsfinal_act:
            conf[dsfinal_act]["final"] = True

        if remap:
            remap_stuff(conf, self.action_ids)

        return conf

    def export_all_to_folder(self, out_dir="./out", ext=".json"):
        where_str = "_Rarity = 5 AND _IsPlayable = 1 AND (_SellDewPoint = 8500 OR _Id in (" + ",".join(map(str, DrgConf.EXTRA_DRAGONS)) + ")) AND _Id = _EmblemId"
        # where_str = '_IsPlayable = 1'
        all_res = self.get_all(where=where_str)
        out_dir = os.path.join(out_dir, "drg")
        check_target_path(out_dir)
        outdata = {ele.lower(): {} for ele in ELEMENTS.values()}
        # skipped = []
        for res in tqdm(all_res, desc=os.path.basename(out_dir)):
            conf = self.process_result(res)
            # outfile = snakey(conf['d']['ele']) + '.json'
            if conf:
                outdata[conf["d"]["ele"]][snakey(conf["d"]["name"])] = conf
        for ele, data in outdata.items():
            output = os.path.join(out_dir, f"{ele}.json")
            with open(output, "w", newline="", encoding="utf-8") as fp:
                fmt_conf(data, f=fp, lim=3)
                fp.write("\n")
        # pprint(DrgConf.COMMON_ACTIONS)

    def get(self, name, by=None, remap=False, hitattrshift=False, mlvl=None):
        res = super().get(name, by=by, full_query=False)
        if isinstance(res, list):
            res = res[0]
        return self.process_result(res, remap=remap, hitattrshift=hitattrshift, mlvl=mlvl)


class WepConf(WeaponBody, SkillProcessHelper):
    T2_ELE = ("shadow", "flame")

    def process_result(self, res):
        super().process_result(res)
        skin = res["_WeaponSkinId"]
        # if skin['_FormId'] % 10 == 1 and res['_ElementalType'] in WepConf.T2_ELE:
        #     return None
        tier = res.get("_MaxLimitOverCount", 0) + 1
        try:
            ele_type = res["_ElementalType"].lower()
        except AttributeError:
            ele_type = "any"
        ab_lst = []
        for i in (1, 2, 3):
            for j in (3, 2, 1):
                if ab := res.get(f"_Abilities{i}{j}"):
                    ab_lst.append(ab)
                    break
        converted, skipped = convert_all_ability(ab_lst)
        conf = {
            "w": {
                "name": res["_Name"],
                "icon": f'{skin["_BaseId"]}_{skin["_VariationId"]:02}_{skin["_FormId"]}',
                "att": res.get(f"_MaxAtk{tier}", 0),
                "hp": res.get(f"_MaxHp{tier}", 0),
                "ele": ele_type,
                "wt": res["_WeaponType"].lower(),
                "series": res["_WeaponSeriesId"]["_GroupSeriesName"].replace(" Weapons", ""),
                # 'crest': {
                #     5: res.get('_CrestSlotType1MaxCount', 0),
                #     4: res.get('_CrestSlotType2MaxCount', 0)
                # },
                "tier": tier,
                "a": converted
                # 'skipped': skipped
            }
        }

        self.reset_meta()
        dupe_skill = {}
        for act, seq, key in (("s3", 3, f"_ChangeSkillId3"),):
            if not (skill := res.get(key)):
                continue
            if skill["_Id"] in self.chara_skills:
                dupe_skill[act] = self.chara_skills[skill["_Id"]][0]
            else:
                self.chara_skills[skill["_Id"]] = (act, seq, skill, None)
        self.process_skill(res, conf, {})

        remap_stuff(conf, self.action_ids)

        return conf

    def export_all_to_folder(self, out_dir="./out", ext=".json"):
        all_res = self.get_all(where="_IsPlayable = 1")
        out_dir = os.path.join(out_dir, "wep")
        check_target_path(out_dir)
        outdata = {wt.lower(): {ele.lower(): {} for ele in ("any", *ELEMENTS.values())} for wt in WEAPON_TYPES.values()}
        # skipped = []
        for res in tqdm(all_res, desc=os.path.basename(out_dir)):
            conf = self.process_result(res)
            # outfile = snakey(conf['d']['ele']) + '.json'
            if conf:
                outdata[conf["w"]["wt"]][conf["w"]["ele"]][snakey(conf["w"]["series"]).lower()] = conf
        for wt, data in outdata.items():
            output = os.path.join(out_dir, f"{wt}.json")
            with open(output, "w", newline="", encoding="utf-8") as fp:
                fmt_conf(data, f=fp, lim=4)
                fp.write("\n")
        #     else:
        #         skipped.append(res["_Name"])
        # print('Skipped:', ','.join(skipped))


class AuraConf(AuraData):
    def process_result(self, res):
        aura_values = []
        for i in range(1, 7):
            aura_values.append(
                [
                    fr(res.get(f"_Rate{i:02}")),
                    res.get(f"_Duration{i:02}"),
                ]
            )
        return {
            "publish": res.get("_PublishLevel"),
            "extend": res.get("_DurationExtension"),
            "type": res["_Type"],
            "values": aura_values,
        }

    def export_all_to_folder(self, out_dir="./out", ext=".json"):
        all_res = self.get_all()
        check_target_path(out_dir)
        outdata = {}
        for res in tqdm(all_res, desc="wp"):
            outdata[str(res["_Id"])] = self.process_result(res)
        output = os.path.join(out_dir, "amp.json")
        with open(output, "w", newline="", encoding="utf-8") as fp:
            fmt_conf(outdata, f=fp)
            fp.write("\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-a", help="_Name/_SecondName")
    parser.add_argument("-d", help="_Name")
    parser.add_argument("-wp", help="_Name")
    parser.add_argument("-s", help="_SkillId")
    parser.add_argument("-slv", help="Skill level")
    parser.add_argument("-f", help="_BurstAttackId")
    parser.add_argument("-x", help="_UniqueComboId")
    parser.add_argument("-fm", help="_BurstAttackMarker")
    # parser.add_argument('-x', '_UniqueComboId')
    parser.add_argument("-w", help="_Name")
    parser.add_argument("-act", help="_ActionId")
    parser.add_argument("-amp", help="all")
    args = parser.parse_args()

    index = DBViewIndex()
    # out_dir = os.path.join(pathlib.Path(__file__).parent.absolute(), '..', '..', 'dl', 'conf', 'gen')
    out_dir = os.path.join(pathlib.Path(__file__).parent.absolute(), "..", "out", "gen")

    if args.s and args.slv:
        view = AdvConf(index)
        if args.a:
            view.get(args.a)
        view.reset_meta()
        sconf, k, action = view.convert_skill(
            "s1",
            0,
            view.index["SkillData"].get(int(args.s)),
            int(args.slv),
        )
        sconf = {k: sconf}
        fmt_conf(sconf, f=sys.stdout)
        print("\n")
        pprint(view.chara_skills.keys())
        pprint(view.enhanced_fs)
    elif args.a:
        view = AdvConf(index)
        if args.a == "all":
            view.export_all_to_folder(out_dir=out_dir)
        else:
            adv_conf = view.get(args.a, all_levels=False)
            fmt_conf(adv_conf, f=sys.stdout)
    elif args.d:
        view = DrgConf(index)
        if args.d == "all":
            view.export_all_to_folder(out_dir=out_dir)
        else:
            d = view.get(args.d, remap=True)
            fmt_conf(d, f=sys.stdout)
    elif args.wp:
        view = WpConf(index)
        if args.wp == "all":
            view.export_all_to_folder(out_dir=out_dir)
        else:
            wp = view.get(args.wp)
            fmt_conf({snakey(wp["name"]): wp}, f=sys.stdout)
    elif args.f:
        view = PlayerAction(index)
        burst = view.get(int(args.f))
        if mid := burst.get("_BurstMarkerId"):
            marker = mid
        elif args.fm:
            marker = view.get(int(args.fm))
        else:
            marker = view.get(int(args.f) + 4)
        fmt_conf(convert_fs(burst, marker), f=sys.stdout)
    elif args.x:
        view = CharaUniqueCombo(index)
        xalt = view.get(int(args.x))
        if not isinstance(xalt, dict):
            exit()
        conf = {}
        for prefix in ("", "Ex"):
            if xalt.get(f"_{prefix}ActionId"):
                for n, xn in enumerate(xalt[f"_{prefix}ActionId"]):
                    n += 1
                    if xaltconf := convert_x(xn):
                        conf[f"x{n}_{prefix.lower()}"] = xaltconf
        fmt_conf(conf, f=sys.stdout)
    elif args.w:
        if args.w == "all":
            view = WepConf(index)
            view.export_all_to_folder(out_dir=out_dir)
    elif args.act:
        view = PlayerAction(index)
        action = view.get(int(args.act))
        pprint(convert_x(action))
    elif args.amp:
        view = AuraConf(index)
        view.export_all_to_folder(out_dir=out_dir)
