import sys
import os
import pathlib
import json
import re
import itertools
from collections import defaultdict
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
from exporter.Mappings import WEAPON_TYPES, ELEMENTS, TRIBE_TYPES, AFFLICTION_TYPES, AbilityCondition, ActionTargetGroup, AbilityTargetAction, AbilityType, AbilityStat, AuraType, PartConditionType, ActionCancelType, PartConditionComparisonType

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
MULTILINE_LIST = ("abilities", "chain")


def fmt_conf(data, k=None, depth=0, f=sys.stdout, lim=2, sortlim=1):
    if k in PRETTY_PRINT_THIS:
        lim += 1
    if depth >= lim:
        if k.startswith("attr") or k in MULTILINE_LIST:
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
                partcond = ("actcond", (actcond.get("_Id"), PART_COMPARISON_TO_VARS[condvalue["_compare"]], count))
            elif ctype == PartConditionType.AuraLevel:
                partcond = ("amp", (condvalue["_aura"].value, condvalue["_target"], PART_COMPARISON_TO_VARS[condvalue["_compare"]], condvalue["_count"]))

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
                    if (not pattern or pattern.match(hitattr["_Id"])) and (
                        attr := convert_hitattr(
                            hitattr,
                            part,
                            action,
                            once_per_action,
                            meta=meta,
                            skill=skill,
                            partcond=partcond,
                        )
                    ):
                        if source == "_hitAttrLabelSubList":
                            part_hitattr_map[source].append(attr)
                        else:
                            part_hitattr_map[source] = attr
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
                last_copy, need_copy = clean_hitattr(hattr.copy(), once_per_action)
                if need_copy:
                    part_hitattrs.append(last_copy)
                    part_hitattrs.append(blt - 1)
                else:
                    part_hitattrs.append(blt)
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
        attr["actcond"] = actcond["_Id"]

    if attr:
        # attr[f"DEBUG_FROM_SEQ"] = part.get("_seq", 0)
        attr["target"] = target.name
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


def hit_sr(action, startup=None, explicit_any=True):
    s, r, followed_by = startup, None, set()
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
                noaid_follow = (part["_seconds"], "any", part.get("_actionType"))
            if action_id:
                followed_by.add((part["_seconds"], action_id, part.get("_actionType")))
            last_r = part["_seconds"]
        if part["commandType"] == CommandType.PLAY_MOTION:
            if (animdata := part.get("_animation")) and isinstance(animdata, dict):
                motion = max(motion, part["_seconds"] + animdata["duration"])
            elif part.get("_motionState") in GENERIC_BUFF:
                motion = max(motion, 1.0)
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


def remap_stuff(conf, action_ids, servant_attrs=None, parent_key=None, fullconf=None):
    # search the dict
    fullconf = fullconf or conf
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
                            try:
                                del fullconf["dservant"]
                            except KeyError:
                                pass
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
            remap_stuff(subvalue, action_ids, servant_attrs=servant_attrs, parent_key=key, fullconf=fullconf)


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
    if not (dodgeconf := hit_attr_adj(action, s, dodgeconf, skip_nohitattr=True, pattern=re.compile(r".*H0\d_LV01$"))):
        return None
    if convert_follow:
        dodgeconf["interrupt"], dodgeconf["cancel"] = convert_following_actions(s, followed_by, ("s",))
    return dodgeconf


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
        self.hitattrshift = False
        self.chara_modes = {}

    def convert_skill(self, k, seq, skill, lv):
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

        # if ab := skill.get(f"_Ability{lv}"):
        #     self.parse_skill_ab(k, seq, skill, action, sconf, ab)

        if ab := skill.get(f"_Ability{lv}"):
            # jank
            if isinstance(ab, dict):
                ab = ab["_Id"]
            sconf["abilities"] = self.index["AbilityConf"].get(ab, source="abilities")

        return sconf, k, action

    def process_skill(self, res, conf, mlvl):
        # exceptions exist
        while self.chara_skills:
            k, seq, skill, prev_id = next(iter(self.chara_skills.values()))
            if seq == 99:
                lv = mlvl[res["_EditSkillLevelNum"]]
            else:
                lv = mlvl.get(seq, 2)
            cskill, k, action = self.convert_skill(k, seq, skill, lv)
            conf[k] = cskill
            self.action_ids[action.get("_Id")] = k
            self.all_chara_skills[skill.get("_Id")] = (k, seq, skill, prev_id)
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

    def process_result(self, res, condense=True, force_50mc=False):
        self.set_animation_reference(res)
        self.reset_meta()

        if force_50mc:
            res = dict(res)
            res["_MaxLimitBreakCount"] = 4
        spiral = res["_MaxLimitBreakCount"] == 5

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
            }
        }
        # hecc
        if res["_Id"] == 10450404:
            conf["c"]["name"] = "Sophie (Persona)"
        if conf["c"]["wt"] == "gun":
            conf["c"]["gun"] = []
        self.name = conf["c"]["name"]

        if self.utp_chara is not None:
            conf["c"]["utp"] = self.utp_chara

        if avoid_on_c := res.get("_AvoidOnCombo"):
            actdata = self.index["PlayerAction"].get(avoid_on_c)
            conf["dodge_on_x"] = convert_dodge(actdata)
            self.action_ids[actdata["_Id"]] = "dodge"
        for dodge in map(res.get, ("_Avoid", "_BackAvoidOnCombo")):
            if dodge:
                actdata = self.index["PlayerAction"].get(dodge)
                if dodgeconf := convert_dodge(actdata):
                    conf["dodge"] = dodgeconf
                self.action_ids[dodge] = "dodge"

        if burst := res.get("_BurstAttack"):
            burst = self.index["PlayerAction"].get(res["_BurstAttack"])
            if burst and (marker := burst.get("_BurstMarkerId")):
                conf.update(convert_fs(burst, marker))
                self.action_ids[burst["_Id"]] = "fs"

        if conf["c"]["spiral"]:
            mlvl = {1: 4, 2: 3}
        else:
            mlvl = {1: 3, 2: 2}

        for s in (1, 2):
            if sdata := res.get(f"_Skill{s}"):
                skill = self.index["SkillData"].get(sdata, full_query=True)
                self.chara_skills[sdata] = (f"s{s}", s, skill, None)

        self.index["AbilityConf"].set_meta(self)
        ablist = []
        for i in (1, 2, 3):
            found = 1
            for j in (3, 2, 1):
                if ab := res.get(f"_Abilities{i}{j}"):
                    if force_50mc and found > 0:
                        found -= 1
                        continue
                    if ability := self.index["AbilityConf"].get(ab, source=f"ability{i}"):
                        ablist.extend(ability)
                    break
        conf["c"]["abilities"] = ablist

        if udrg := res.get("_UniqueDragonId"):
            udform_key = "dservant" if self.utp_chara and self.utp_chara[0] == 2 else "dragonform"
            conf[udform_key] = self.index["DrgConf"].get(udrg, by="_Id", uniqueshift=True, hitattrshift=self.hitattrshift, mlvl=mlvl if res.get("_IsConvertDragonSkillLevel") else None)
            self.action_ids.update(self.index["DrgConf"].action_ids)
            # dum
            self.set_animation_reference(res)

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

        base_mode_burst, base_mode_x = None, None
        for m in range(1, 5):
            if mode := res.get(f"_ModeId{m}"):
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
                if not (mode_name := self.chara_modes.get(m)):
                    if m == 2 and self.utp_chara is not None and self.utp_chara[0] != 1:
                        mode_name = "_ddrive"
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
        try:
            conf["c"]["gun"] = list(set(conf["c"]["gun"]))
        except KeyError:
            pass

        # self.abilities = self.last_abilities(res, as_mapping=True)
        # pprint(self.abilities)
        # for k, seq, skill in self.chara_skills.values():

        if edit := res.get("_EditSkillId"):
            if edit not in self.chara_skills:
                skill = self.index["SkillData"].get(edit, full_query=True)
                self.chara_skills[edit] = (f"s99", 99, skill, None)
                res["_EditSkillId"] = skill
            else:
                res["_EditSkillId"] = self.chara_skills[edit][2]

        self.process_skill(res, conf, mlvl)

        if ss_conf := self.skillshare_data(res):
            conf["c"]["skillshare"] = ss_conf

        try:
            self.action_ids.update(self.base_conf.action_ids)
        except AttributeError:
            pass
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

        self.index["AbilityConf"].set_meta(None)

        return conf

    def get(self, name, exss=False):
        res = super().get(name, full_query=False)
        if isinstance(res, list):
            res = res[0]
        conf = self.process_result(res)
        if exss:
            if ex_res := self.exability_data(res):
                conf["DEBUG_COAB"] = ex_res
        return conf

    @staticmethod
    def outfile_name(conf, ext, variant=None):
        if variant is not None:
            return snakey(conf["c"]["name"]) + "." + variant + ext
        return snakey(conf["c"]["name"]) + ext

    def skillshare_data(self, res):
        ss_conf = {}
        if res["_HoldEditSkillCost"] != 10:
            ss_conf["limit"] = res["_HoldEditSkillCost"]
        if res["_EditSkillRelationId"] > 1:
            modifiers = self.index["EditSkillCharaOffset"].get(res["_EditSkillRelationId"], by="_EditSkillRelationId")[0]
            if modifiers["_SpOffset"] > 1:
                ss_conf["mod_sp"] = modifiers["_SpOffset"]
            if modifiers["_StrengthOffset"] != 0.699999988079071:
                ss_conf["mod_att"] = modifiers["_StrengthOffset"]
            if modifiers["_BuffDebuffOffset"] != 1:
                ss_conf["mod_buff"] = modifiers["_BuffDebuffOffset"]
        if res.get("_EditSkillCost", 0) > 0 and (skill := res.get("_EditSkillId")):
            # skill = self.index["SkillData"].get(res["_EditSkillId"])
            # ss_conf["s"] = self.
            ss_conf["src"] = self.all_chara_skills[skill["_Id"]][0]
            ss_conf["cost"] = res["_EditSkillCost"]
            if res["_MaxLimitBreakCount"] >= 5:
                sp_lv = 4
            else:
                sp_lv = 3
            if res["_EditSkillLevelNum"] == 2:
                sp_lv -= 1
            # ss_conf["type"] = skill["_SkillType"]
            ss_conf["sp"] = skill[f"_SpLv{sp_lv}Edit"]
        return ss_conf

    def exability_data(self, res):
        ex_ab = self.index["ExAbilityConf"].get(res["_ExAbilityData5"], source="coab")
        chain_ab = self.index["AbilityConf"].get(res.get("_ExAbility2Data5"), source="chain")
        entry = {
            "ex": ex_ab,
            "chain": chain_ab,
        }
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
        self.sort_exability_data(exability_data)
        with open(exability_out, "w", newline="") as fp:
            fmt_conf(exability_data, f=fp, lim=3, sortlim=2)
            fp.write("\n")


# ALWAYS_KEEP = {400127, 400406, 400077, 400128, 400092, 400410}
class WpConf(AbilityCrest):
    def __init__(self, index):
        super().__init__(index)
        self.boon_names = {res["_Id"]: res["_Name"] for res in self.index["UnionAbility"].get_all()}

    def process_result(self, res):
        ablist = []
        for i in (1, 2, 3):
            ab = res.get(f"_Abilities{i}3")
            if ability := self.index["AbilityConf"].get(ab, source=f"ability{i}"):
                ablist.extend(ability)

        boon = res.get("_UnionAbilityGroupId", 0)
        if not boon and not ablist:
            return

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
            "abilities": ablist,
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

    def convert_skill(self, k, seq, skill, lv):
        conf, k, action = super().convert_skill(k, seq, skill, lv)
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

    def process_result(self, res, remap=True, hitattrshift=False, mlvl=None, uniqueshift=False):
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

        conf = {}
        if not uniqueshift:
            ablist = []
            self.index["AbilityConf"].set_meta(self)
            for i in (1, 2):
                if (ab := res.get(f"_Abilities{i}{ab_seq}")) and (ability := self.index["AbilityConf"].get(ab, source=f"ability{i}")):
                    ablist.extend(ability)
            conf["d"] = {
                "name": res.get("_SecondName", res.get("_Name")),
                "icon": f'{res["_BaseId"]}_{res["_VariationId"]:02}',
                "att": att,
                "hp": hp,
                "ele": ELEMENTS.get(res["_ElementalType"]).lower(),
            }
            conf["d"]["abilities"] = ablist

        super().process_result(res)
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

        if not uniqueshift:
            self.index["AbilityConf"].set_meta(None)

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

    def get(self, name, by=None, remap=False, hitattrshift=False, mlvl=None, uniqueshift=False):
        res = super().get(name, by=by, full_query=False)
        if isinstance(res, list):
            res = res[0]
        return self.process_result(res, remap=remap, hitattrshift=hitattrshift, mlvl=mlvl, uniqueshift=uniqueshift)


class WepConf(WeaponBody, SkillProcessHelper):
    T2_ELE = ("shadow", "flame")

    def process_result(self, res):
        super().process_result(res)
        self.index["AbilityConf"].set_meta(self)
        skin = res["_WeaponSkinId"]
        # if skin['_FormId'] % 10 == 1 and res['_ElementalType'] in WepConf.T2_ELE:
        #     return None
        tier = res.get("_MaxLimitOverCount", 0) + 1
        try:
            ele_type = res["_ElementalType"].lower()
        except AttributeError:
            ele_type = "any"
        ablist = []
        for i in (1, 2, 3):
            for j in (3, 2, 1):
                ab = res.get(f"_Abilities{i}{j}")
                if ability := self.index["AbilityConf"].get(ab, source=f"ability{i}"):
                    ablist.extend(ability)
                break
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
                "abilities": ablist
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

        self.index["AbilityConf"].set_meta(None)
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


class AbilityConf(AbilityData):
    EXCLUDE_FALSY = False
    TARGET_ACT = {
        AbilityTargetAction.COMBO: "x",
        AbilityTargetAction.BURST_ATTACK: "fs",
        AbilityTargetAction.SKILL_1: "s1",
        AbilityTargetAction.SKILL_2: "s2",
        AbilityTargetAction.SKILL_3: "s3",
        AbilityTargetAction.SKILL_ALL: "s",
        AbilityTargetAction.HUMAN_SKILL_1: "s1",
        AbilityTargetAction.HUMAN_SKILL_1: "s2",
        AbilityTargetAction.DRAGON_SKILL_1: "ds1",
        AbilityTargetAction.SKILL_4: "s4",
        AbilityTargetAction.HUMAN_SKILL_3: "s3",
        AbilityTargetAction.HUMAN_SKILL_4: "s4",
    }

    def __init__(self, index):
        super().__init__(index)
        self.meta = None
        self.source = None

    def set_meta(self, meta):
        self.meta = meta
        self.source = None

    def _varids(self, res, i):
        for a in ("a", "b", "c"):
            try:
                key = f"_VariousId{i}{a}"
                yield res[key]
            except KeyError:
                continue

    def _varid_a(self, res, i):
        try:
            return res[f"_VariousId{i}a"]
        except KeyError:
            return res[f"_VariousId{i}"]

    def _upval(self, res, i, div=100):
        try:
            upval = res[f"_AbilityType{i}UpValue"]
        except KeyError:
            upval = res[f"_AbilityType{i}UpValue0"]
        if div > 1 or div < 0:
            return upval / div
        return upval

    # AbilityCondition
    def ac_NONE(self, res):
        return None

    def ac_HP_MORE(self, res):
        return ["hp", ">=", int(res["_ConditionValue"])]

    def ac_HP_LESS(self, res):
        return ["hp", "<=", int(res["_ConditionValue"])]

    def ac_BUFF_SKILL1(self, res):
        return ["buff", 1]

    def ac_BUFF_SKILL2(self, res):
        return ["buff", 2]

    def ac_DRAGON_MODE(self, res):
        return ["shift", "dform"]

    def ac_BREAKDOWN(self, res):
        return ["break"]

    def ac_GET_BUFF_DEF(self, res):
        return ["event", "doublebuff"]

    def ac_TOTAL_HITCOUNT_MORE(self, res):
        return ["hits", ">=", int(res["_ConditionValue"])]

    def ac_TOTAL_HITCOUNT_LESS(self, res):
        return ["hits", "<", int(res["_ConditionValue"])]

    def ac_KILL_ENEMY(self, res):
        cond = ["slayer", int(res["_ConditionValue"])]
        target = AbilityTargetAction(res.get("_TargetAction"))
        if target != AbilityTargetAction.NONE:
            cond.append(AbilityConf.TARGET_ACT[target])
        return cond

    def ac_TRANSFORM_DRAGON(self, res):
        return ["event", "dragon"]

    def ac_HP_MORE_MOMENT(self, res):
        return ["hp", ">=", int(res["_ConditionValue"]), 1]

    def ac_HP_LESS_MOMENT(self, res):
        return ["hp", "<", int(res["_ConditionValue"]), 1]

    def ac_QUEST_START(self, res):
        return ["start"]

    def ac_OVERDRIVE(self, res):
        return ["overdrive"]

    def ac_ABNORMAL_STATUS(self, res):
        return ["aff", AFFLICTION_TYPES.get(int(res["_ConditionValue"])).lower()]

    def ac_TENSION_MAX(self, res):
        return ["energy", "=", 5]

    def ac_TENSION_MAX_MOMENT(self, res):
        return ["event", "energized"]

    def ac_DEBUFF_SLIP_HP(self, res):
        return ["bleed"]

    def ac_HITCOUNT_MOMENT(self, res):
        cond = ["hits", ">=", int(res["_ConditionValue"]), 1]
        target = AbilityTargetAction(res.get("_TargetAction"))
        if target != AbilityTargetAction.NONE:
            cond.append(AbilityConf.TARGET_ACT[target])
        return cond

    def ac_SP1_OVER(self, res):
        return ["sp", "s1", ">=", int(res["_ConditionValue"])]

    def ac_SP1_LESS(self, res):
        return ["sp", "s1", "<", int(res["_ConditionValue"])]

    def ac_SP1_OVER(self, res):
        return ["sp", "s2", ">=", int(res["_ConditionValue"])]

    def ac_SP1_OVER(self, res):
        return ["sp", "s2", "<", int(res["_ConditionValue"])]

    def ac_CAUSE_ABNORMAL_STATUS(self, res):
        return ["aff", AFFLICTION_TYPES.get(int(res["_ConditionValue"])).lower()]

    def ac_DAMAGED_ABNORMAL_STATUS(self, res):
        return ["selfaff", AFFLICTION_TYPES.get(int(res["_ConditionValue"])).lower()]

    def ac_DRAGONSHIFT_MOMENT(self, res):
        return ["event", "dragon"]

    def ac_TENSION_LV(self, res):
        return ["energy", "=", int(res["_ConditionValue"])]

    def ac_TENSION_LV_MOMENT(self, res):
        return ["event", "energy", ["stack", "=", int(res["_ConditionValue"])]]

    def ac_GET_BUFF_TENSION(self, res):
        return ["event", "energy"]

    def ac_HP_NOREACH(self, res):
        return ["hp", "<", int(res["_ConditionValue"])]

    def ac_HP_NOREACH_MOMENT(self, res):
        return ["hp", "<", int(res["_ConditionValue"]), 1]

    def ac_SKILLCONNECT_SKILL1_MOMENT(self, res):
        return ["event", "s1_charged"]

    def ac_SKILLCONNECT_SKILL2_MOMENT(self, res):
        return ["event", "s2_charged"]

    def ac_CAUSE_DEBUFF_ATK(self, res):
        return ["event", "debuff_att"]

    def ac_CAUSE_DEBUFF_DEF(self, res):
        return ["event", "debuff_def"]

    def ac_CHANGE_BUFF_TYPE_COUNT(self, res):
        return ["bufficon"]

    def ac_CAUSE_CRITICAL(self, res):
        cond = ["event", "crit"]
        target = AbilityTargetAction(res.get("_TargetAction"))
        if target != AbilityTargetAction.NONE:
            cond.append(["base", "in", AbilityConf.TARGET_ACT[target]])
        return cond

    def ac_BUFFED_SPECIFIC_ID(self, res):
        return ["buff", int(res["_ConditionValue"])]

    def ac_DAMAGED(self, res):
        return ["damaged", -1]

    def ac_DEBUFF(self, res):
        return ["debuff", int(res["_ConditionValue"])]

    def ac_RELEASE_DRAGONSHIFT(self, res):
        return ["event", "dragon_end"]

    def ac_UNIQUE_TRANS_MODE(self, res):
        return ["shift", "ddrive"]

    def ac_DAMAGED_MYSELF(self, res):
        return ["damaged", int(res["_ConditionValue"] * -1)]

    def ac_SP1_MORE_MOMENT(self, res):
        return ["sp", "s1", ">=", int(res["_ConditionValue"]), 1]

    def ac_SP1_UNDER_MOMENT(self, res):
        return ["sp", "s1", "<", int(res["_ConditionValue"]), 1]

    def ac_SP2_MORE_MOMENT(self, res):
        return ["sp", "s2", ">=", int(res["_ConditionValue"]), 1]

    def ac_SP2_UNDER_MOMENT(self, res):
        return ["sp", "s2", "<", int(res["_ConditionValue"]), 1]

    def ac_HP_MORE_NOT_EQ_MOMENT(self, res):
        return ["hp", ">", int(res["_ConditionValue"])]

    def ac_HP_LESS_NOT_EQ_MOMENT(self, res):
        return ["hp", "<", int(res["_ConditionValue"])]

    def ac_HP_MORE_NO_SUPPORT_CHARA(self, res):
        return ["hp", ">=", int(res["_ConditionValue"])]

    def ac_HP_NOREACH_NO_SUPPORT_CHARA(self, res):
        return ["hp", "<", int(res["_ConditionValue"])]

    def ac_CP1_CONDITION(self, res):
        return ["cp", ">=", int(res["_ConditionValue"])]

    def ac_REQUIRED_BUFF_AND_SP1_MORE(self, res):
        # return [["buff", res["_RequiredBuff"]], "and", ["sp", "s1", ">=", res[""]]]
        return ["buff", int(res["_RequiredBuff"])]

    def ac_ALWAYS_REACTION_TIME(self, res):
        return ["timer", -1]

    def ac_ON_ABNORMAL_STATUS_RESISTED(self, res):
        return ["antiaff", AFFLICTION_TYPES.get(int(res["_ConditionValue"])).lower()]

    def ac_BUFF_DISAPPEARED(self, res):
        return ["buffend", int(res["_ConditionValue"])]

    def ac_BUFFED_SPECIFIC_ID_COUNT(self, res):
        return ["buff", int(res["_ConditionValue2"]), "=", int(res["_ConditionValue"])]

    def ac_CHARGE_LOOP_REACTION_TIME(self, res):
        return ["fs_hold", "charge"]

    def ac_AVOID(self, res):
        return ["event", "dodge"]

    def ac_CAUSE_DEBUFF_SLIP_HP(self, res):
        return ["bleed", 1]

    def ac_CP1_OVER(self, res):
        return ["cp", ">=", int(res["_ConditionValue"])]

    def ac_BUFF_COUNT_MORE_THAN(self, res):
        return ["buff", int(res["_ConditionValue2"]), ">=", int(res["_ConditionValue"])]

    def ac_BUFF_CONSUMED(self, res):
        return ["buffend", int(res["_ConditionValue"]), 1]

    def ac_HP_BETWEEN(self, res):
        return ["hp", ">=", int(res["_ConditionValue"]), "<=", int(res["_ConditionValue2"])]

    def ac_BURST_ATTACK_FINISHED(self, res):
        return ["event", "fs_end"]

    def ac_DISPEL_SUCCEEDED(self, res):
        cond = ["event", "dispel"]
        target = AbilityTargetAction(res.get("_TargetAction"))
        if target != AbilityTargetAction.NONE:
            cond.append(["base", "in", AbilityConf.TARGET_ACT[target]])
        return cond

    def ac_ON_BUFF_FIELD(self, res):
        return ["zone"]

    def ac_GET_DP(self, res):
        return ["get_dp", int(res["_ConditionValue"])]

    def ac_GET_HEAL(self, res):
        return ["event", "heal"]

    def ac_CHARGE_TIME_MORE_MOMENT(self, res):
        return ["fs_hold", "end"]

    def ac_HITCOUNT_MOMENT_TIMESRATE(self, res):
        return ["mult", "hits", int(res["_ConditionValue"]), int(res["_ConditionValue2"])]

    def ac_HITCOUNT_MOMENT_TIMESRATE(self, res):
        return ["mult", "buff", int(res["_ConditionValue"]), int(res["_ConditionValue2"])]

    def ac_BUFFED_SPECIFIC_ID_COUNT_MORE_ALWAYS_CHECK(self, res):
        return ["buff", int(res["_ConditionValue2"]), ">=", int(res["_ConditionValue"])]

    def ac_GET_BUFF_FROM_SKILL(self, res):
        return ["event", "buffed"]

    def ac_RELEASE_DIVINEDRAGONSHIFT(self, res):
        return ["event", "divineshift_end"]

    def ac_HAS_AURA_TYPE(self, res):
        return ["auratype", int(res["_ConditionValue"]), int(res["_ConditionValue2"])]

    def ac_PARTY_AURA_LEVEL_MORE(self, res):
        return ["aura", int(res["_ConditionValue"]), int(res["_ConditionValue2"])]

    def ac_DRAGONSHIFT(self, res):
        return ["event", "dragon"]

    def ac_DRAGON_MODE_STRICTLY(self, res):
        return ["shift", "dform"]

    def ac_ACTIVATE_SKILL(self, res):
        return ["event", "s"]

    def ac_SELF_AURA_MOMENT(self, res):
        return ["auratype", int(res["_ConditionValue"]), 1, 1]

    def ac_PARTY_AURA_LEVEL_MORE_REACTION_TIME(self, res):
        return ["auratype", int(res["_ConditionValue"]), 1]

    def ac_ON_REMOVE_ABNORMAL_STATUS(self, res):
        return ["event", "relief"]

    # AbilityType
    STAT_TO_MOD = {
        AbilityStat.Hp: "hp",
        AbilityStat.Atk: "att",
        AbilityStat.Def: "defense",
        AbilityStat.Spr: "sp",
        AbilityStat.Dpr: "dh",
        AbilityStat.DragonTime: "dt",
        AbilityStat.AttackSpeed: "spd",
        AbilityStat.BurstSpeed: "fspd",
        AbilityStat.ChargeSpeed: "cspd",
    }

    def _at_upval(self, name, res, i, div=100):
        return [name, self._upval(res, i, div=div)]

    def _at_aff(self, name, res, i, div=100):
        return [name, AFFLICTION_TYPES[self._varid_a(res, i)].lower(), self._upval(res, i, div=div)]

    def at_StatusUp(self, res, i):
        try:
            stat = AbilityStat(self._varid_a(res, i))
        except KeyError:
            stat = AbilityStat(res[f"_VariousId{i}"])
        return ["stat", AbilityConf.STAT_TO_MOD[stat], self._upval(res, i)]

    def at_ResistAbs(self, res, i):
        return self._at_aff("affres", res, i)

    def at_ActAddAbs(self, res, i):
        return self._at_aff("edge", res, i)

    def at_ActKillerTribe(self, res, i):
        return ["killer", TRIBE_TYPES[self._varid_a(res, i)].lower(), self._upval(res, i)]

    def at_ActDamageUp(self, res, i):
        return self._at_upval("dmg", res, i)

    def at_ActCriticalUp(self, res, i):
        return self._at_upval("crit", res, i)

    def at_ActRecoveryUp(self, res, i):
        return self._at_upval("rcv", res, i)

    def at_ActBreakUp(self, res, i):
        return self._at_upval("odaccel", res, i)

    def at_AddRecoverySp(self, res, i):
        return ["stat", "sp", self._upval(res, i)]

    def at_ChangeState(self, res, i):
        buffs = []
        for bid in self._varids(res, i):
            if bid:
                buffs.append(bid)
        if buffs:
            return ["actcond", *buffs]
        else:
            hitattr = convert_hitattr(self.index["PlayerActionHitAttribute"].get(res[f"_VariousId{i}str"]), DUMMY_PART, {}, set())
            if set(hitattr.keys()) == {"actcond", "target"} and hitattr["target"] == "MYSELF":
                return ["actcond", hitattr["actcond"]]
            return ["hitattr", hitattr]

    def at_SpCharge(self, res, i):
        return self._at_upval("prep", res, i)

    def at_BuffExtension(self, res, i):
        return self._at_upval("bufftime", res, i)

    def at_DebuffExtension(self, res, i):
        return self._at_upval("debufftime", res, i)

    def at_AbnormalKiller(self, res, i):
        return self._at_aff("punisher", res, i)

    def at_CriticalDamageUp(self, res, i):
        return self._at_upval("critdmg", res, i)

    def at_DpCharge(self, res, i):
        return self._at_upval("dprep", res, i)

    def at_ResistElement(self, res, i):
        return ["eleres", ELEMENTS[self._varid_a(res, i)].lower(), self._upval(res, i)]

    def at_DragonDamageUp(self, res, i):
        return ["stat", "da", self._upval(res, i)]

    def at_HitAttribute(self, res, i):
        return self.at_ChangeState(res, i)

    def at_HitAttributeShift(self, res, i):
        if self.meta is not None:
            self.meta.hitattrshift = True
        return ["hitattrshift"]

    def at_EnhancedSkill(self, res, i):
        skill_id = self._varid_a(res, i)
        target = AbilityTargetAction(res[f"_TargetAction{i}"])
        seq = int(target.name[-1:])
        if self.meta is not None:
            if not skill_id in self.meta.all_chara_skills:
                skill_data = self.index["SkillData"].get(skill_id)
                self.meta.chara_skills[skill_id] = (f"s{seq}_{self.source}", seq, skill_data, None)
        return ["altskill", self.source]

    def at_EnhancedBurstAttack(self, res, i):
        # for some reason they only use this for albert and otherwise resort to ChangeState
        burst_id = self._varid_a(res, i)
        if self.meta is not None:
            burst = self.index["PlayerAction"].get(burst_id)
            self.meta.alt_actions.append(("fs", burst))
        return None

    def at_AbnoramlExtension(self, res, i):
        return self._at_aff("afftime", res, i)

    def at_DragonTimeSpeedRate(self, res, i):
        value = 100 / (100 + self._upval(res, i))
        return ["stat", "dt", value]

    def at_DpChargeMyParty(self, res, i):
        return self._at_upval("dprep", res, i)

    def at_CriticalUpDependsOnBuffTypeCount(self, res, i):
        return self._at_upval("crit", res, i)

    def at_ChainTimeExtension(self, res, i):
        return self._at_upval("ctime", res, i)

    def at_UniqueTransform(self, res, i):
        if self.meta is not None:
            self.meta.utp_chara = [res[f"_VariousId{i}a"], *(int(v) for v in res[f"_VariousId{i}str"].split("/"))]
        return None

    def at_EnhancedElementDamage(self, res, i):
        return ["eledmg", ELEMENTS.get(self._varid_a(res, i)).lower(), self._upval(res, i)]

    def at_UtpCharge(self, res, i):
        return self._at_upval("utprep", res, i)

    def at_ChangeMode(self, res, i):
        m = self._varid_a(res, i) + 1
        # mode name stuff
        if res["_ConditionType"] == AbilityCondition.BUFF_DISAPPEARED and res["_ConditionValue"] == 1152:
            mode_name = "sigil"
        else:
            mode_name = f"mode{m}"
        if self.meta is not None:
            self.meta.chara_modes[m] = f"_{mode_name}"
        return ["mode", mode_name]

    def at_ModifyBuffDebuffDurationTime(self, res, i):
        return ["actcond_time", self._varid_a(res, i), self._upval(res, i, 1)]

    def at_UniqueAvoid(self, res, i):
        # can this take a cond? unclear
        avoid_id = self._varid_a(res, i)
        if self.meta is not None:
            avoid = self.index["PlayerAction"].get(avoid_id)
            self.meta.alt_actions.append(("dodge", avoid))
        return None

    # processing
    def process_result(self, res, source=None):
        if source is not None:
            self.source = source
        conf = {}
        # cond
        condtype = AbilityCondition(res["_ConditionType"])
        res["_ConditionType"] = condtype
        try:
            if cond := getattr(self, f"ac_{condtype.name}")(res):
                conf["cond"] = cond
        except AttributeError:
            # if the cond is not implemented, skip
            return []
        # cd
        if cd := res.get("_CoolTime"):
            conf["cd"] = cd
        # count
        if count := res.get("_MaxCount"):
            conf["count"] = count
        # ele
        if ele := res.get("_ElementalType"):
            conf["ele"] = ELEMENTS[ele].lower()
        # wt
        if wt := res.get("_WeaponType"):
            conf["wt"] = WEAPON_TYPES[wt].lower()
        # ab
        ablist = []
        conflist = []
        for i in (1, 2, 3):
            abtype = AbilityType(res[f"_AbilityType{i}"])
            if abtype == AbilityType.ReferenceOther:
                for value in self._varids(res, i):
                    if not value or not (subab := self.get(value)):
                        continue
                    conflist.extend(subab)
            else:
                try:
                    if ab := getattr(self, f"at_{abtype.name}")(res, i):
                        target = AbilityTargetAction(res.get(f"_TargetAction{i}", 0))
                        if target != AbilityTargetAction.NONE:
                            ab.append(AbilityConf.TARGET_ACT[target])
                        ablist.append(ab)
                except (AttributeError, ValueError):
                    pass
        if source is not None:
            self.source = None
        if ablist:
            conf["ab"] = ablist
            conflist.append(conf)
        return list(filter(None, conflist))


class ExAbilityConf(AbilityConf):
    def __init__(self, index):
        DBView.__init__(self, index, "ExAbilityData", labeled_fields=["_Name", "_Details"])

    def process_result(self, res, source=None):
        conf = {"category": res["_Category"]}
        if not (conflist := super().process_result(res, source=source)):
            return
        conf.update(conflist[0])
        return conf


class ActCondConf(ActionCondition):
    def __init__(self, index):
        super().__init__(index)
        self.meta = None
        self.all_actcond_conf = {}

    def set_meta(self, meta):
        self.meta = meta

    def process_result(self, res):
        # _Id INTEGER PRIMARY KEY
        actcond_id = res["_Id"]
        conf = {}
        # _Type INTEGER
        try:
            conf["aff"] = AFFLICTION_TYPES.get(res["_Type"], res["_Type"]).lower()
        except KeyError:
            pass

        # _Text TEXT
        # _TextEx TEXT
        # _BlockExaustFlag INTEGER
        # _InternalFlag INTEGER
        # _UniqueIcon INTEGER
        # _BuffIconId INTEGER
        # _ResistBuffReset INTEGER
        # _ResistDebuffReset INTEGER
        # _UnifiedManagement INTEGER
        # _Overwrite INTEGER
        # _OverwriteIdenticalOwner INTEGER
        # _OverwriteGroupId INTEGER
        # _MaxDuplicatedCount INTEGER
        # _UsePowerUpEffect INTEGER
        # _NotUseStartEffect INTEGER
        # _StartEffectCommon TEXT
        # _StartEffectAdd TEXT
        # _LostOnDragon INTEGER
        # _KeepOnDragonShift INTEGER
        # _RestoreOnReborn INTEGER
        # _Rate INTEGER
        # _EfficacyType INTEGER
        # _RemoveConditionId INTEGER
        # _DebuffCategory INTEGER
        # _RemoveDebuffCategory INTEGER
        # _DurationSec REAL
        # _DurationNum INTEGER
        # _MinDurationSec REAL
        # _DurationTimeScale INTEGER
        # _IsAddDurationNum INTEGER
        # _MaxDurationNum INTEGER
        # _CoolDownTimeSec REAL
        # _RemoveAciton INTEGER
        # _DurationNumConsumedHeadText TEXT
        # _SlipDamageIntervalSec REAL
        # _SlipDamageFixed INTEGER
        # _SlipDamageRatio REAL
        # _SlipDamageMax INTEGER
        # _SlipDamagePower REAL
        # _SlipDamageGroup INTEGER
        # _RateIncreaseByTime REAL
        # _RateIncreaseDuration REAL
        # _RegenePower REAL
        # _DebuffGrantRate REAL
        # _EventProbability INTEGER
        # _EventCoefficient REAL
        # _DamageCoefficient REAL
        # _TargetAction INTEGER
        # _TargetElemental INTEGER
        # _ConditionAbs INTEGER
        # _ConditionDebuff INTEGER
        # _RateHP REAL
        # _RateAttack REAL
        # _RateDefense REAL
        # _RateDefenseB REAL
        # _RateCritical REAL
        # _RateSkill REAL
        # _RateBurst REAL
        # _RateRecovery REAL
        # _RateRecoverySp REAL
        # _RateRecoverySpExceptTargetSkill INTEGER
        # _RateRecoveryDp REAL
        # _RateRecoveryUtp REAL
        # _RateAttackSpeed REAL
        # _RateChargeSpeed REAL
        # _RateBurstSpeed REAL
        # _MoveSpeedRate REAL
        # _MoveSpeedRateB REAL
        # _RatePoison REAL
        # _RateBurn REAL
        # _RateFreeze REAL
        # _RateParalysis REAL
        # _RateDarkness REAL
        # _RateSwoon REAL
        # _RateCurse REAL
        # _RateSlowMove REAL
        # _RateSleep REAL
        # _RateFrostbite REAL
        # _RateFlashheat REAL
        # _RateCrashWind REAL
        # _RateDarkAbs REAL
        # _RateDestroyFire REAL
        # _RatePoisonKiller REAL
        # _RateBurnKiller REAL
        # _RateFreezeKiller REAL
        # _RateParalysisKiller REAL
        # _RateDarknessKiller REAL
        # _RateSwoonKiller REAL
        # _RateCurseKiller REAL
        # _RateSlowMoveKiller REAL
        # _RateSleepKiller REAL
        # _RateFrostbiteKiller REAL
        # _RateFlashheatKiller REAL
        # _RateCrashWindKiller REAL
        # _RateDarkAbsKiller REAL
        # _RateDestroyFireKiller REAL
        # _RatePoisonAdd REAL
        # _RateBurnAdd REAL
        # _RateFreezeAdd REAL
        # _RateParalysisAdd REAL
        # _RateDarknessAdd REAL
        # _RateSwoonAdd REAL
        # _RateCurseAdd REAL
        # _RateSlowMoveAdd REAL
        # _RateSleepAdd REAL
        # _RateFrostbiteAdd REAL
        # _RateFlashheatAdd REAL
        # _RateCrashWindAdd REAL
        # _RateDarkAbsAdd REAL
        # _RateDestroyFireAdd REAL
        # _RateFire REAL
        # _RateWater REAL
        # _RateWind REAL
        # _RateLight REAL
        # _RateDark REAL
        # _EnhancedFire REAL
        # _EnhancedWater REAL
        # _EnhancedWind REAL
        # _EnhancedLight REAL
        # _EnhancedDark REAL
        # _EnhancedFire2 REAL
        # _EnhancedWater2 REAL
        # _EnhancedWind2 REAL
        # _EnhancedLight2 REAL
        # _EnhancedDark2 REAL
        # _EnhancedNoElement REAL
        # _EnhancedDisadvantagedElement REAL
        # _RateMagicCreature REAL
        # _RateNatural REAL
        # _RateDemiHuman REAL
        # _RateBeast REAL
        # _RateUndead REAL
        # _RateDeamon REAL
        # _RateHuman REAL
        # _RateDragon REAL
        # _RateDamageCut REAL
        # _RateDamageCut2 REAL
        # _RateDamageCutB REAL
        # _RateWeakInvalid REAL
        # _HealInvalid INTEGER
        # _TensionUpInvalid INTEGER
        # _ValidRegeneHP REAL
        # _ValidRegeneSP REAL
        # _ValidRegeneDP REAL
        # _ValidSlipHp REAL
        # _RequiredRecoverHp INTEGER
        # _RateGetHpRecovery REAL
        # _UniqueRegeneSp01 REAL
        # _AutoRegeneS1 REAL
        # _AutoRegeneSW REAL
        # _RateReraise REAL
        # _RateArmored REAL
        # _RateDamageShield REAL
        # _RateDamageShield2 REAL
        # _RateDamageShield3 REAL
        # _RateSacrificeShield REAL
        # _SacrificeShieldType INTEGER
        # _Malaise01 INTEGER
        # _Malaise02 INTEGER
        # _Malaise03 INTEGER
        # _RateNicked REAL
        # _CurseOfEmptiness INTEGER
        # _CurseOfEmptinessInvalid INTEGER
        # _TransSkill REAL
        # _GrantSkill INTEGER
        # _DisableAction INTEGER
        # _DisableActionFlags INTEGER
        # _DisableMove INTEGER
        # _InvincibleLv INTEGER
        # _AutoAvoid REAL
        # _ComboShift INTEGER
        # _EnhancedBurstAttack INTEGER
        # _EnhancedSkill1 INTEGER
        # _EnhancedSkill2 INTEGER
        # _EnhancedSkillWeapon INTEGER
        # _EnhancedCritical REAL
        # _Tension INTEGER
        # _Inspiration INTEGER
        # _Cartridge INTEGER
        # _ModeStack INTEGER
        # _StackData INTEGER
        # _StackNum INTEGER
        # _Sparking INTEGER
        # _RateHpDrain REAL
        # _HpDrainLimitRate REAL
        # _SelfDamageRate REAL
        # _HpConsumptionRate REAL
        # _HpConsumptionCoef REAL
        # _RemoveTrigger INTEGER
        # _DamageLink TEXT
        # _AdditionAttack TEXT
        # _AdditionAttackHitEffect TEXT
        # _ExtraBuffType INTEGER
        # _EnhancedSky INTEGER
        # _InvalidBuffId INTEGER
        # _ModifyChargeLevel INTEGER
        # _Hiding INTEGER
        # _LevelUpId INTEGER
        # _LevelDownId INTEGER
        # _ExcludeFromBuffExtension INTEGER


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
    parser.add_argument("-ab", help="_Id")
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
            adv_conf = view.get(args.a, exss=True)
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
    elif args.ab:
        view = AbilityConf(index)
        ability = view.get(int(args.ab))
        pprint(ability)
