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
from exporter.Shared import ActionCondition, ActionParts, PlayerAction, AbilityData, ActionPartsHitLabel, snakey
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
)

ONCE_PER_ACT = ("sp", "dp", "utp", "buff", "afflic", "bleed", "extra", "dispel")
DODGE_ACTIONS = {6, 40}
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
    "_RegenePower": ("heal", "buff"),
    "_SlipDamageRatio": ("regen", "buff"),
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
TENSION_KEY = {"_Tension": "energy", "_Inspiration": "inspiration"}
# OVERWRITE = ('_Overwrite', '_OverwriteVoice', '_OverwriteGroupId')
ENHANCED_SKILL = {
    "_EnhancedSkill1": 1,
    "_EnhancedSkill2": 2,
    "_EnhancedSkillWeapon": 3,
}
AURA_TYPE_BUFFARGS = {
    AuraType.HP: ("maxhp", "buff"),
    AuraType.ATTACK: ("att", "buff"),
    AuraType.DEFENSE: ("def", "buff"),
}
DUMMY_PART = {"_seconds": 0}


def ele_bitmap(n):
    seq = 1
    while not n & 1 and n > 0:
        n = n >> 1
        seq += 1
    return ELEMENTS[seq]


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


def fmt_conf(data, k=None, depth=0, f=sys.stdout, lim=2, sortlim=1):
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
            f.write(k)
            f.write('": ')
            res = fmt_conf(v, k, depth + 1, f, lim, sortlim)
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


def convert_all_hitattr(action, pattern=None, meta=None, skill=None):
    actparts = action["_Parts"]
    clear_once_per_action = action.get("_OnHitExecType") == 1
    hitattrs = []
    once_per_action = set()
    for part in actparts:
        if clear_once_per_action:
            once_per_action.clear()
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
            if isinstance(value, list):
                part_hitattrs.extend(value)
            else:
                part_hitattrs.append(value)
        is_msl = True
        if (blt := part.get("_bulletNum", 0)) > 1 and "_hitAttrLabel" in part_hitattr_map and not "extra" in part_hitattr_map["_hitAttrLabel"]:
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
        if gen := part.get("_generateNum"):
            delay = part.get("_generateDelay")
            ref_attrs = part_hitattrs
        elif (abd := part.get("_abDuration", 0)) >= (abi := part.get("_abHitInterval", 0)) and "_abHitAttrLabel" in part_hitattr_map:
            # weird rounding shenanigans can occur due to float bullshit
            gen = int(abd / abi)
            delay = abi
            try:
                part_hitattr_map["_abHitAttrLabel"]["msl"] += fr(abi)
            except KeyError:
                part_hitattr_map["_abHitAttrLabel"]["msl"] = fr(abi)
            ref_attrs = [part_hitattr_map["_abHitAttrLabel"]]
        elif (
            (bci := part.get("_collisionHitInterval", 0))
            and ((bld := part.get("_bulletDuration", 0)) > bci or (bld := part.get("_duration", 0)) > bci)
            and ("_hitLabel" in part_hitattr_map or "_hitAttrLabel" in part_hitattr_map)
        ):
            gen = int(bld / bci)
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
        if gen and delay:
            for gseq in range(1, gen):
                for attr in ref_attrs:
                    gattr, _ = clean_hitattr(attr.copy(), once_per_action)
                    if not gattr:
                        continue
                    gattr[timekey] = fr(attr.get(timekey, 0) + delay * gseq)
                    gen_attrs.append(gattr)
        if part.get("_generateNumDependOnBuffCount"):
            # possible that this can be used with _generateNum
            buffcond = part["_buffCountConditionId"]
            buffname = snakey(buffcond["_Text"]).lower()
            gen = buffcond["_MaxDuplicatedCount"]
            for idx, delay in enumerate(map(float, json.loads(part["_bulletDelayTime"]))):
                if idx >= gen:
                    break
                delay = float(delay)
                for attr in part_hitattrs:
                    if idx == 0:
                        attr[timekey] = fr(attr.get(timekey, 0) + delay)
                        attr["cond"] = ["var>=", [buffname, idx + 1]]
                    else:
                        gattr, _ = clean_hitattr(attr.copy(), once_per_action)
                        if not gattr:
                            continue
                        gattr[timekey] = fr(attr.get(timekey, 0) + delay)
                        gattr["cond"] = ["var>=", [buffname, idx + 1]]
                        gen_attrs.append(gattr)
        part_hitattrs.extend(gen_attrs)
        hitattrs.extend(part_hitattrs)
    once_per_action = set()
    return hitattrs


def convert_hitattr(hitattr, part, action, once_per_action, meta=None, skill=None, from_ab=False):
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
            attr["killer"] = [fr(hitattr["_KillerStateDamageRate"] - 1), killers]
        if crisis := hitattr.get("_CrisisLimitRate"):
            attr["crisis"] = fr(crisis - 1)
        if bufc := hitattr.get("_DamageUpRateByBuffCount"):
            attr["bufc"] = fr(bufc)
        if dragon := hitattr.get("_AttrDragon"):
            attr["drg"] = dragon
        if (od := hitattr.get("_ToBreakDmgRate")) and od != 1:
            attr["odmg"] = fr(od)
        # wow i fucking hate cykagames
        if part.get("DEBUG_GLUCA_FLAG"):
            attr["gluca"] = 1
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
    if (aura_max := hitattr.get("_AuraMaxLimitLevel")) and (aura_data := hitattr.get("_AuraId")):
        try:
            publish_lv = aura_data.get("_PublishLevel")
            # fr(aura_data.get("_DurationExtension"))
            # aura_args = [[aura_data["_Id"], *AURA_TYPE_BUFFARGS[aura_data["_Type"]]]]
            aura_args = [
                [
                    aura_data["_Type"].value,
                    # aura_data["_Id"],
                    publish_lv,
                    aura_max,
                    fr(aura_data.get("_DurationExtension", 0)),
                    *AURA_TYPE_BUFFARGS[aura_data["_Type"]],
                ]
            ]
            aura_values = []
            for i in range(1, 7):
                aura_values.append(
                    [
                        fr(aura_data.get(f"_Rate{i:02}")),
                        aura_data.get(f"_Duration{i:02}"),
                    ]
                )
            aura_args.append(aura_values)
            attr["amp"] = aura_args
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
        if ctype := part.get("_conditionType"):
            attr[f"DEBUG_CHECK_PARTCOND"] = str(ctype)
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
        return attr
    else:
        return None


def convert_actcond(attr, actcond, target, part={}, meta=None, skill=None, from_ab=False):
    if actcond.get("_EfficacyType") == DISPEL and (rate := actcond.get("_Rate", 0)):
        attr["dispel"] = rate
    else:
        alt_buffs = []
        if meta and skill:
            for ehs, s in ENHANCED_SKILL.items():
                if esk := actcond.get(ehs):
                    if isinstance(esk, int) or esk.get("_Id") in meta.all_chara_skills:
                        meta.chara_skill_loop.add(skill["_Id"])
                    else:
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
                        if part.get("_collisionParams_01", 0) > 0:
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
                        if part.get("_collisionParams_01", 0) > 0:
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
                else:
                    if addatk := actcond.get("_AdditionAttack"):
                        buffs.append(["echo", fr(addatk["_DamageAdjustment"]), duration])
                    if drain := actcond.get("_RateHpDrain"):
                        # FIXME: distinction between self vs team?
                        buffs.append(["drain", fr(drain), duration])
                    for k, mod in BUFFARG_KEY.items():
                        if value := actcond.get(k):
                            if (bele := actcond.get("_TargetElemental")) and btype != "self":
                                buffs.append(
                                    [
                                        "ele",
                                        fr(value),
                                        duration,
                                        *mod,
                                        ele_bitmap(bele).lower(),
                                    ]
                                )
                                if negative_value is None:
                                    negative_value = value < 0
                            elif k == "_SlipDamageRatio":
                                value *= 100
                                if (afftype := actcond.get("_Type", "").lower()) in AFFLICTION_TYPES.values():
                                    buffs.append(
                                        [
                                            "selfaff",
                                            -fr(value),
                                            duration,
                                            actcond.get("_Rate"),
                                            afftype,
                                            *mod,
                                        ]
                                    )
                                    if negative_value is None:
                                        negative_value = value > 0
                                else:
                                    buffs.append([btype, -fr(value), duration, *mod])
                            else:
                                buffs.append([btype, fr(value), duration, *mod])
                                if negative_value is None:
                                    negative_value = value < 0
                    if negative_value is None:
                        negative_value = False
            if buffs:
                if len(buffs) == 1:
                    buffs = buffs[0]
                # if any(actcond.get(k) for k in AdvConf.OVERWRITE):
                #     buffs.append('-refresh')
                if actcond.get("_OverwriteGroupId"):
                    buffs.append(f'-overwrite_{actcond.get("_OverwriteGroupId")}')
                elif actcond.get("_Overwrite") or actcond.get("_OverwriteIdenticalOwner") or is_duration_num:
                    buffs.append("-refresh")
                attr["buff"] = buffs
                if target == ActionTargetGroup.HOSTILE or negative_value or actcond.get("_CurseOfEmptinessInvalid"):
                    attr["coei"] = 1


def hit_sr(parts, seq=None, xlen=None, is_dragon=False, signal_end=None):
    s, r = None, None
    motion = None
    # use_motion = False
    timestop = 0
    timecurve = None
    followed_by = set()
    signals = {}
    signal_end = signal_end or set()
    motion_end = None
    for idx, part in enumerate(parts):
        if part["commandType"] == CommandType.SEND_SIGNAL:
            actid = part.get("_actionId", 0)
            if not (is_dragon and actid % 100 in (20, 21)) and not actid in DODGE_ACTIONS:
                signals[actid] = -10
                if part.get("_motionEnd"):
                    signal_end.add(actid)
        elif part.get("_allHitLabels") and s is None:
            s = fr(part["_seconds"])
        elif part["commandType"] == CommandType.ACTIVE_CANCEL:
            recovery = part["_seconds"]
            actid = part.get("_actionId")
            if seq and actid in signals:
                signals[actid] = recovery
            if part.get("_motionEnd") or actid in signal_end:
                motion_end = recovery
            if actid:
                followed_by.add((recovery, actid))
            # else:
            #     recovery = max(timestop, recovery)
        elif part["commandType"] == CommandType.HIT_STOP:
            # timestop = part.get('_seconds', 0) + part.get('_duration', 0)
            ts_second = part.get("_seconds", 0)
            ts_delay = part.get("_duration", 0)
            timestop = ts_second + ts_delay
            # if is_dragon:
            #     found_hit = False
            #     for npart in parts[idx+1:]:
            #         if npart['_seconds'] > ts_second:
            #             # found_hit = found_hit or ('HIT' in npart['commandType'] or 'BULLET' in npart['commandType'])
            #             if 'HIT' in npart['commandType'] or 'BULLET' in npart['commandType']:
            #                 npart['_seconds'] += ts_delay
        elif is_dragon and part["commandType"] == CommandType.MOVE_TIME_CURVE and not part.get("_isNormalizeCurve"):
            timecurve = part.get("_duration")
        # if part['commandType'] == 'PLAY_MOTION' and part.get('_animation'):
        #     motion = fr(part['_animation']['stopTime'] - part['_blendDuration'])
        #     if part['_animation']['name'][0] == 'D':
        #         use_motion = True
    # if timestop > 0:
    # if not signal_to_next:
    #     for part in sorted(parts, key=lambda p: -p['_seq']):
    #         if part['commandType'] == 'ACTIVE_CANCEL' and part['_seconds'] > 0:
    #             r = part['_seconds']
    #             break
    # print(signals, motion_end, timecurve)
    if timecurve is not None:
        for part in sorted(parts, key=lambda p: -p["_seq"]):
            if part["commandType"] == CommandType.ACTIVE_CANCEL and part["_seconds"] > 0:
                r = part["_seconds"]
                break
        if r is None:
            r = motion_end
        if r is not None:
            r = max(timestop, r)
    else:
        try:
            r = max(signals.values())
        except:
            pass
    if s is None:
        return 0, 0, {}
    if r is None or r < s:
        if motion_end:
            r = motion_end
        else:
            for part in reversed(parts):
                if part["commandType"] == CommandType.ACTIVE_CANCEL:
                    r = part["_seconds"]
                    break
        if r is not None:
            r = max(timestop, r)
    r = fr(r)
    return s, r, followed_by


def hit_attr_adj(action, s, conf, pattern=None, skip_nohitattr=True):
    if hitattrs := convert_all_hitattr(action, pattern=pattern):
        try:
            conf["recovery"] = fr(conf["recovery"] - s)
        except TypeError:
            conf["recovery"] = None
        for attr in hitattrs:
            if not isinstance(attr, int) and "iv" in attr:
                attr["iv"] = fr(attr["iv"] - s)
                if attr["iv"] == 0:
                    del attr["iv"]
        conf["attr"] = hitattrs
    if not hitattrs and skip_nohitattr:
        return None
    return conf


def convert_following_actions(startup, followed_by, default=None):
    interrupt_by = {}
    cancel_by = {}
    if default:
        for act in default:
            interrupt_by[act] = 0.0
            cancel_by[act] = 0.0
    for t, act in followed_by:
        if act in DODGE_ACTIONS:
            act_name = "dodge"
        elif act % 10 == 5:
            act_name = "fs"
        else:
            continue
        if t < startup:
            interrupt_by[act_name] = fr(t)
        else:
            cancel_by[act_name] = t
    cancel_by.update(interrupt_by)
    for act, t in cancel_by.items():
        cancel_by[act] = fr(max(0.0, t - startup))
    return interrupt_by, cancel_by


def convert_x(aid, xn, xlen=5, pattern=None, convert_follow=True, is_dragon=False):
    DEBUG_CHECK_NEXTACT = False
    currentaction = xn
    while nextaction := currentaction.get("_NextAction"):
        xn["_Parts"].extend(nextaction["_Parts"])
        currentaction = nextaction
        DEBUG_CHECK_NEXTACT = True

    s, r, followed_by = hit_sr(xn["_Parts"], seq=aid, xlen=xlen, is_dragon=is_dragon)
    xconf = {"startup": s, "recovery": r}
    if DEBUG_CHECK_NEXTACT:
        xconf["DEBUG_CHECK_NEXTACT"] = True
    xconf = hit_attr_adj(xn, s, xconf, skip_nohitattr=False, pattern=pattern)

    if convert_follow:
        xconf["interrupt"], xconf["cancel"] = convert_following_actions(s, followed_by, ("s",))

    return xconf


def convert_fs(burst, marker=None, cancel=None):
    startup, recovery, followed_by = hit_sr(burst["_Parts"])
    fsconf = {}
    if not isinstance(marker, dict):
        fsconf["fs"] = hit_attr_adj(
            burst,
            startup,
            {"startup": startup, "recovery": recovery},
            re.compile(r".*_LV02$"),
        )
    else:
        for mpart in marker["_Parts"]:
            if mpart["commandType"] == CommandType.GEN_MARKER:
                break
        charge = mpart.get("_chargeSec", 0.5)
        fsconf["fs"] = {"charge": fr(charge), "startup": startup, "recovery": recovery}
        if clv := mpart.get("_chargeLvSec"):
            clv = list(map(float, [charge] + json.loads(clv)))
            totalc = 0
            for idx, c in enumerate(clv):
                if idx == 0:
                    clv_attr = hit_attr_adj(burst, startup, fsconf[f"fs"].copy(), re.compile(f".*_LV02$"))
                else:
                    clv_attr = hit_attr_adj(
                        burst,
                        startup,
                        fsconf[f"fs"].copy(),
                        re.compile(f".*_LV02_CHLV0{idx+1}$"),
                    )
                totalc += c
                if clv_attr:
                    fsn = f"fs{idx+1}"
                    fsconf[fsn] = clv_attr
                    fsconf[fsn]["charge"] = fr(totalc)
                    (
                        fsconf[fsn]["interrupt"],
                        fsconf[fsn]["cancel"],
                    ) = convert_following_actions(startup, followed_by, ("s",))
            if "fs2" in fsconf and "attr" not in fsconf["fs"]:
                del fsconf["fs"]
            elif "fs1" in fsconf:
                fsconf["fs"] = fsconf["fs1"]
                del fsconf["fs1"]
        else:
            fsconf["fs"] = hit_attr_adj(
                burst,
                startup,
                fsconf["fs"],
                re.compile(r".*_LV02$"),
                skip_nohitattr=False,
            )
            if fsconf["fs"]:
                (
                    fsconf["fs"]["interrupt"],
                    fsconf["fs"]["cancel"],
                ) = convert_following_actions(startup, followed_by, ("s",))
    if cancel is not None:
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

    def process_result(self, res, full_query=True):
        conf = {"lv2": {}}
        if res["_Label"] != "GUN":
            fs_id = res["_BurstPhase1"]
            res = super().process_result(res, full_query=True)
            # fs_delay = {}
            fsconf = convert_fs(res["_BurstPhase1"], res["_ChargeMarker"], res["_ChargeCancel"])
            startup = fsconf["fs"]["startup"]
            # for x, delay in fs_delay.items():
            #     fsconf['fs'][x] = {'startup': fr(startup+delay)}
            conf.update(fsconf)
            for n in range(1, 6):
                try:
                    xn = res[f"_DefaultSkill0{n}"]
                except KeyError:
                    break
                conf[f"x{n}"] = convert_x(xn["_Id"], xn)
                # for part in xn['_Parts']:
                #     if part['commandType'] == 'ACTIVE_CANCEL' and part.get('_actionId') == fs_id and part.get('_seconds'):
                #         fs_delay[f'x{n}'] = part.get('_seconds')
                if hitattrs := convert_all_hitattr(xn, re.compile(r".*H0\d_LV02$")):
                    for attr in hitattrs:
                        attr["iv"] = fr(attr["iv"] - conf[f"x{n}"]["startup"])
                        if attr["iv"] == 0:
                            del attr["iv"]
                    conf["lv2"][f"x{n}"] = {"attr": hitattrs}
        else:
            # gun stuff
            for mode in BaseConf.GUN_MODES:
                mode = self.index["CharaModeData"].get(mode, full_query=True)
                mode_name = f'gun{mode["_GunMode"]}'
                if burst := mode.get("_BurstAttackId"):
                    marker = burst.get("_BurstMarkerId")
                    for fs, fsc in convert_fs(burst, marker).items():
                        conf[f"{fs}_{mode_name}"] = fsc
                if (xalt := mode.get("_UniqueComboId")) and isinstance(xalt, dict):
                    for prefix in ("", "Ex"):
                        if xalt.get(f"_{prefix}ActionId"):
                            for n, xn in enumerate(xalt[f"_{prefix}ActionId"]):
                                n += 1
                                xn_key = f"x{n}_{mode_name}{prefix.lower()}"
                                if xaltconf := convert_x(xn["_Id"], xn, xlen=xalt["_MaxComboNum"]):
                                    conf[xn_key] = xaltconf
                                if hitattrs := convert_all_hitattr(xn, re.compile(r".*H0\d_LV02$")):
                                    for attr in hitattrs:
                                        attr["iv"] = fr(attr["iv"] - conf[xn_key]["startup"])
                                        if attr["iv"] == 0:
                                            del attr["iv"]
                                    conf["lv2"][xn_key] = {"attr": hitattrs}

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


def convert_skill_common(skill, lv):
    action = 0
    if lv >= skill.get("_AdvancedSkillLv1", float("inf")):
        action = skill.get("_AdvancedActionId1", 0)
    if isinstance(action, int):
        action = skill.get("_ActionId1")

    startup, recovery = 0.1, None
    actcancel = None
    mstate = None
    timestop = 0
    followed_by = set()
    for part in action["_Parts"]:
        if part["commandType"] == CommandType.ACTIVE_CANCEL and actcancel is None:
            if "_actionId" in part:
                followed_by.add((part["_seconds"], part["_actionId"]))
            else:
                actcancel = part["_seconds"]
        if part["commandType"] == CommandType.PLAY_MOTION and mstate is None:
            if animation := part.get("_animation"):
                if isinstance(animation, list):
                    mstate = sum(a["duration"] for a in animation)
                else:
                    mstate = animation["duration"]
            if part.get("_motionState") in GENERIC_BUFF:
                mstate = 1.0
        if part["commandType"] == CommandType.HIT_STOP:
            timestop = part["_seconds"] + part["_duration"]
        if actcancel and mstate:
            break
    if actcancel:
        actcancel = max(timestop, actcancel)
    recovery = actcancel or mstate or recovery

    if recovery is None:
        AdvConf.MISSING_ENDLAG.append(skill.get("_Name"))

    sconf = {
        "sp": skill.get(f"_SpLv{lv}", skill.get("_Sp", 0)),
        "startup": startup,
        "recovery": None if not recovery else fr(recovery),
    }

    interrupt, cancel = convert_following_actions(0, followed_by)
    if interrupt:
        sconf["interrupt"] = interrupt
    if cancel:
        sconf["cancel"] = cancel

    currentaction = action
    while nextaction := currentaction.get("_NextAction"):
        action["_Parts"].extend(nextaction["_Parts"])
        currentaction = nextaction
        sconf["DEBUG_CHECK_NEXTACT"] = True

    return sconf, action


class SkillProcessHelper:
    def reset_meta(self):
        self.chara_skills = {}
        self.chara_skill_loop = set()
        self.eskill_counter = itertools.count(start=1)
        self.efs_counter = itertools.count(start=1)
        self.all_chara_skills = {}
        self.enhanced_fs = {}
        self.ab_alt_attrs = defaultdict(lambda: [])

    def convert_skill(self, k, seq, skill, lv, no_loop=False):
        sconf, action = convert_skill_common(skill, lv)

        if hitattrs := convert_all_hitattr(
            action,
            re.compile(f".*LV0{lv}$"),
            meta=None if no_loop else self,
            skill=skill,
        ):
            sconf["attr"] = hitattrs
        if (not hitattrs or all(["dmg" not in attr for attr in hitattrs if isinstance(attr, dict)])) and skill.get(f"_IsAffectedByTensionLv{lv}"):
            sconf["energizable"] = bool(skill[f"_IsAffectedByTensionLv{lv}"])

        if isinstance((transkills := skill.get("_TransSkill")), dict):
            k = f"s{seq}_phase1"
            for idx, ts in enumerate(transkills.items()):
                tsid, tsk = ts
                if tsid not in self.all_chara_skills:
                    self.chara_skills[tsid] = (
                        f"s{seq}_phase{idx+1}",
                        seq,
                        tsk,
                        skill.get("_Id"),
                    )

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
                s = int(ab["_TargetAction1"].name[-1])
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
                confkey = "attr" if ab.get("_OnSkill") == seq else f"attr_{condtype}"
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
            del self.chara_skills[skill.get("_Id")]

        for efs, eba, emk in self.enhanced_fs.values():
            n = ""
            for fs, fsc in convert_fs(eba, emk).items():
                conf[f"{fs}_{efs}"] = fsc

        # if res.get('_Id') not in AdvConf.DO_NOT_FIND_LOOP:
        #     if self.chara_skill_loop:
        #         for loop_id in self.chara_skill_loop:
        #             k, seq, _, prev_id = self.all_chara_skills.get(loop_id)
        #             loop_sequence = [(k, seq)]
        #             while prev_id != loop_id and prev_id is not None:
        #                 k, seq, _, pid = self.all_chara_skills.get(prev_id)
        #                 loop_sequence.append((k, seq))
        #                 prev_id = pid
        #             for p, ks in enumerate(reversed(loop_sequence)):
        #                 k, seq = ks
        #                 conf[f's{seq}_phase{p+1}'] = conf[k]
        #                 del conf[k]


def find_ab_alt_attrs(ab_alt_attrs, ab):
    if not ab:
        return
    for i in (1, 2, 3):
        ab_type = ab.get(f"_AbilityType{i}")
        if ab_type == AbilityType.ChangeState:
            hitattr = ab.get(f"_VariousId{i}str")
            if not hitattr:
                hitattr = {"_ActionCondition1": ab.get(f"_VariousId{i}a")}
            if sid := ab.get("_OnSkill"):
                ab_alt_attrs[sid].append((ab, hitattr))

        elif ab_type == AbilityType.ReferenceOther:
            for sfx in ("a", "b", "c"):
                find_ab_alt_attrs(ab_alt_attrs, ab.get(f"_VariousId{i}{sfx}"))


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

    def process_result(self, res, condense=True, all_levels=False):
        self.index["ActionParts"].animation_reference = f'{res["_BaseId"]:06}{res["_VariationId"]:02}'
        self.reset_meta()

        ab_lst = []
        for i in (1, 2, 3):
            for j in (3, 2, 1):
                if ab := res.get(f"_Abilities{i}{j}"):
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
                "spiral": res["_MaxLimitBreakCount"] == 5,
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
            find_ab_alt_attrs(self.ab_alt_attrs, ab)

        if burst := res.get("_BurstAttack"):
            burst = self.index["PlayerAction"].get(res["_BurstAttack"])
            if burst and (marker := burst.get("_BurstMarkerId")):
                conf.update(convert_fs(burst, marker))

        for s in (1, 2):
            skill = self.index["SkillData"].get(res[f"_Skill{s}"], full_query=True)
            self.chara_skills[res[f"_Skill{s}"]] = (f"s{s}", s, skill, None)
        if (edit := res.get("_EditSkillId")) and edit not in self.chara_skills:
            skill = self.index["SkillData"].get(res[f"_EditSkillId"], full_query=True)
            self.chara_skills[res["_EditSkillId"]] = (f"s99", 99, skill, None)

        if udrg := res.get("_UniqueDragonId"):
            if not res.get("_ModeChangeType") and res.get("_IsConvertDragonSkillLevel"):
                dragon = self.index["DragonData"].get(udrg, by="_Id")
                for part in dragon["_Skill1"]["_ActionId1"]["_Parts"]:
                    part["DEBUG_GLUCA_FLAG"] = True
                res["_ModeId2"] = {
                    "_UniqueComboId": {
                        "_ActionId": dragon["_DefaultSkill"],
                        "_MaxComboNum": dragon["_ComboMax"],
                    },
                    "_Skill1Id": dragon["_Skill1"],
                    "_Skill2Id": dragon["_Skill2"],
                }
                if ddodge := dragon.get("dodge"):
                    conf["dodge"] = {"startup": ddodge["recovery"]}
                else:
                    conf["dodge"] = {"startup": DrgConf.COMMON_ACTIONS_DEFAULTS["dodge"]}
            else:
                conf["dragonform"] = self.index["DrgConf"].get(udrg, by="_Id")
                del conf["dragonform"]["d"]
            # dum
            self.index["ActionParts"].animation_reference = f'{res["_BaseId"]:06}{res["_VariationId"]:02}'

        for m in range(1, 5):
            if mode := res.get(f"_ModeId{m}"):
                mode_name = None
                if not isinstance(mode, dict):
                    mode = self.index["CharaModeData"].get(mode, full_query=True)
                    if not mode:
                        continue
                else:
                    mode_name = "_ddrive"
                if gunkind := mode.get("_GunMode"):
                    conf["c"]["gun"].append(gunkind)
                    if mode["_Id"] in BaseConf.GUN_MODES:
                        continue
                    # if not any([mode.get(f'_Skill{s}Id') for s in (1, 2)]):
                    #     continue
                if not mode_name:
                    try:
                        mode_name = snakey(mode["_ActionId"]["_Parts"][0]["_actionConditionId"]["_Text"].split(" ")[0].lower())
                    except:
                        if res.get("_ModeChangeType") == 3 and m == 2:
                            mode_name = "_ddrive"
                            if udrg := res.get("_UniqueDragonId"):
                                dragon = self.index["DragonData"].get(udrg, by="_Id")
                                for s in (1, 2):
                                    a_skey = f"_Skill{s}Id"
                                    d_skey = f"_Skill{s}"
                                    if not d_skey in dragon:
                                        continue
                                    if s == 1:
                                        for part in dragon[d_skey]["_ActionId1"]["_Parts"]:
                                            part["DEBUG_GLUCA_FLAG"] = True
                                    if a_skey in mode:
                                        mode[a_skey]["_ActionId1"]["_Parts"].extend(dragon[d_skey]["_ActionId1"]["_Parts"])
                                    else:
                                        mode[a_skey] = dragon[d_skey]
                        elif m == 1:
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
                if burst := mode.get("_BurstAttackId"):
                    marker = burst.get("_BurstMarkerId")
                    if not marker:
                        marker = self.index["PlayerAction"].get(burst["_Id"] + 4)
                    for fs, fsc in convert_fs(burst, marker).items():
                        conf[f"{fs}{mode_name}"] = fsc
                if (xalt := mode.get("_UniqueComboId")) and isinstance(xalt, dict):
                    xalt_pattern = re.compile(r".*H0\d_LV02$") if conf["c"]["spiral"] else None
                    for prefix in ("", "Ex"):
                        if xalt.get(f"_{prefix}ActionId"):
                            for n, xn in enumerate(xalt[f"_{prefix}ActionId"]):
                                n += 1
                                if xaltconf := convert_x(
                                    xn["_Id"],
                                    xn,
                                    xlen=xalt["_MaxComboNum"],
                                    pattern=xalt_pattern,
                                ):
                                    conf[f"x{n}{mode_name}{prefix.lower()}"] = xaltconf
                                elif xalt_pattern is not None and (xaltconf := convert_x(xn["_Id"], xn, xlen=xalt["_MaxComboNum"])):
                                    conf[f"x{n}{mode_name}{prefix.lower()}"] = xaltconf
        try:
            conf["c"]["gun"] = list(set(conf["c"]["gun"]))
        except KeyError:
            pass

        # self.abilities = self.last_abilities(res, as_mapping=True)
        # pprint(self.abilities)
        # for k, seq, skill in self.chara_skills.values():

        if conf["c"]["spiral"]:
            mlvl = {1: 4, 2: 3}
        else:
            mlvl = {1: 3, 2: 2}
        self.process_skill(res, conf, mlvl, all_levels=all_levels)
        self.edit_skill_idx = 0
        if edit := res.get("_EditSkillId"):
            try:
                self.edit_skill_idx = self.SPECIAL_EDIT_SKILL[edit]
            except KeyError:
                self.edit_skill_idx = self.all_chara_skills[edit][1]

        return conf

    def get(self, name, all_levels=False):
        res = super().get(name, full_query=False)
        if isinstance(res, list):
            res = res[0]
        return self.process_result(res, all_levels=all_levels)

    @staticmethod
    def outfile_name(conf, ext):
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
                outconf = self.process_result(
                    res,
                )
                out_name = self.outfile_name(outconf, ext)
                if ss_res := self.skillshare_data(res):
                    skillshare_data[snakey(outconf["c"]["name"])] = ss_res
                if ex_res := self.exability_data(res):
                    exability_data[snakey(outconf["c"]["ele"])][snakey(outconf["c"]["name"])] = ex_res
                output = os.path.join(advout_dir, out_name)
                with open(output, "w", newline="", encoding="utf-8") as fp:
                    fmt_conf(outconf, f=fp)
            except Exception as e:
                print(res["_Id"])
                pprint(outconf)
                raise e
        if AdvConf.MISSING_ENDLAG:
            print("Missing endlag for:", AdvConf.MISSING_ENDLAG)
        with open(skillshare_out, "w", newline="") as fp:
            fmt_conf(skillshare_data, f=fp)
        self.sort_exability_data(exability_data)
        with open(exability_out, "w", newline="") as fp:
            fmt_conf(exability_data, f=fp, lim=3, sortlim=2)


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
    elif cond == AbilityCondition.QUEST_START and (val := actcond.get("_Tension")):
        return ["eprep", int(val)]
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


def ab_tribe_k(**kwargs):
    if a_id := kwargs.get("var_a"):
        res = [f"k_{TRIBE_TYPES.get(a_id, a_id)}", kwargs.get("upval") / 100]
        if condstr := ab_cond(kwargs.get("ab"), kwargs.get("chains")):
            res.append(condstr)
        return res


def ab_aff_res(**kwargs):
    if a_id := kwargs.get("var_a"):
        aff = a_id
        if aff == 99:
            res = ["affshield", kwargs.get("ab").get("_OccurenceNum")]
        else:
            res = [f"affres_{aff}", kwargs.get("upval")]
        if condstr := ab_cond(kwargs.get("ab"), kwargs.get("chains")):
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


ABILITY_CONVERT = {
    AbilityType.StatusUp: ab_stats,
    AbilityType.ActAddAbs: ab_aff_edge,
    AbilityType.ActDamageUp: ab_damage,
    AbilityType.ActCriticalUp: ab_generic("cc"),
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
}
SPECIAL = {
    448: ["spu", 0.08],
    1402: ["au", 0.08],
    1776: ["corrosion", 3],
    400000838: ["critcombo", 10],
    400000858: ["poised_shadowblight-killer_passive", 0.08],
}


def convert_ability(ab, skip_abtype=tuple(), chains=False):
    if special_ab := SPECIAL.get(ab.get("_Id")):
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
    SKIP_BOON = (0, 7, 8, 9, 10)

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
        try:
            attr = conf["attr"]
            del conf["attr"]
            conf["attr"] = attr
        except KeyError:
            pass
        return conf, k, action

    def process_result(self, res):
        super().process_result(res)

        ab_lst = []
        for i in (1, 2):
            if ab := res.get(f"_Abilities{i}5"):
                ab_lst.append(ab)
        converted, skipped = convert_all_ability(ab_lst)

        conf = {
            "d": {
                "name": res.get("_SecondName", res.get("_Name")),
                "icon": f'{res["_BaseId"]}_{res["_VariationId"]:02}',
                "att": res["_MaxAtk"],
                "hp": res["_MaxHp"],
                "ele": ELEMENTS.get(res["_ElementalType"]).lower(),
                "a": converted,
            }
        }
        # if skipped:
        #     conf['d']['skipped'] = skipped

        for act, key in (
            ("dodge", "_AvoidActionFront"),
            ("dodgeb", "_AvoidActionBack"),
            ("dshift", "_Transform"),
        ):
            try:
                s, r, _ = hit_sr(res[key]["_Parts"], is_dragon=True, signal_end={None})
            except KeyError:
                continue
                # try:
                #     DrgConf.COMMON_ACTIONS[act][tuple(actconf['attr'][0].items())].add(conf['d']['name'])
                # except KeyError:
                #     DrgConf.COMMON_ACTIONS[act][tuple(actconf['attr'][0].items())] = {conf['d']['name']}
            if DrgConf.COMMON_ACTIONS_DEFAULTS[act] != r:
                conf[act] = {"recovery": r}
            if act == "dshift":
                hitattrs = convert_all_hitattr(res[key])
                if hitattrs and hitattrs[0]["dmg"] != 2.0:
                    try:
                        conf[act]["attr"] = hitattrs
                    except KeyError:
                        conf[act] = {"attr": hitattrs}

        if "dodgeb" in conf:
            if "dodge" not in conf or conf["dodge"]["recovery"] > conf["dodgeb"]["recovery"]:
                conf["dodge"] = conf["dodgeb"]
                conf["dodge"]["backdash"] = True
            del conf["dodgeb"]

        dcombo = res["_DefaultSkill"]
        dcmax = res["_ComboMax"]
        for n, xn in enumerate(dcombo):
            n += 1
            if dxconf := convert_x(xn["_Id"], xn, xlen=dcmax, convert_follow=False, is_dragon=True):
                conf[f"dx{n}"] = dxconf

        self.reset_meta()
        dupe_skill = {}
        for act, seq, key in (
            ("ds", 1, "_Skill1"),
            ("ds_final", 0, "_SkillFinalAttack"),
        ):
            if not (dskill := res.get(key)):
                continue
            if dskill["_Id"] in self.chara_skills:
                dupe_skill[act] = self.chara_skills[dskill["_Id"]][0]
            else:
                self.chara_skills[dskill["_Id"]] = (act, seq, dskill, None)
        self.process_skill(res, conf, {})
        for act, src in dupe_skill.items():
            conf[act] = conf[src].copy()

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
        # pprint(DrgConf.COMMON_ACTIONS)

    def get(self, name, by=None):
        res = super().get(name, by=by, full_query=False)
        if isinstance(res, list):
            res = res[0]
        return self.process_result(res)


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
        #     else:
        #         skipped.append(res["_Name"])
        # print('Skipped:', ','.join(skipped))


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
            d = view.get(args.d)
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
                    if xaltconf := convert_x(xn["_Id"], xn, xlen=xalt["_MaxComboNum"]):
                        conf[f"x{n}_{prefix.lower()}"] = xaltconf
        fmt_conf(conf, f=sys.stdout)
    elif args.w:
        if args.w == "base":
            view = BaseConf(index)
            view.export_all_to_folder(out_dir=out_dir)
        elif args.w == "all":
            view = WepConf(index)
            view.export_all_to_folder(out_dir=out_dir)
    elif args.act:
        view = PlayerAction(index)
        action = view.get(int(args.act))
        pprint(hit_sr(action["_Parts"], is_dragon=True))
