import re
import itertools
import json
import sys
import os
from tqdm import tqdm
from collections import defaultdict
import math
import copy

from loader.Enums import (
    CommandType,
    AbilityCondition,
    ActionTargetGroup,
    AbilityTargetAction,
    AbilityType,
    AbilityStat,
    PartConditionType,
    ActionCancelType,
    PartConditionComparisonType,
    ActionSignalType,
    CharacterControl,
)
from exporter.Shared import ActionPartsHitLabel, AuraData, AbilityData, ActionCondition, check_target_path
from exporter.Mappings import (
    AFFLICTION_TYPES,
    ELEMENTS,
    TRIBE_TYPES,
    WEAPON_TYPES,
)

BULLET_COMMAND = (
    CommandType.GEN_BULLET,
    CommandType.PARABOLA_BULLET,
    CommandType.PIVOT_BULLET,
    CommandType.ARRANGE_BULLET,
    CommandType.BUTTERFLY_BULLET,
    CommandType.STOCK_BULLET_SHIKIGAMI,
)

PART_COMPARISON_TO_VARS = {
    PartConditionComparisonType.Equality: "=",
    PartConditionComparisonType.Inequality: "!=",
    PartConditionComparisonType.GreaterThan: ">",
    PartConditionComparisonType.GreaterThanOrEqual: ">=",
    PartConditionComparisonType.LessThan: "<",
    PartConditionComparisonType.LessThanOrEqual: "<=",
}

ONCE_PER_ACT = ("sp", "dp", "utp", "actcond")
DODGE_ACTIONS = {6, 7, 40, 900710, 900711}

INDENT = "    "
PRETTY_PRINT_THIS = ("dragonform", "dservant", "repeat")
MULTILINE_LIST = ("abilities", "ref", "chain")
DUMMY_PART = {"_seconds": 0.0}


def fmt_conf(data, k=None, depth=0, f=sys.stdout, lim=2, sortlim=1):
    if k in PRETTY_PRINT_THIS:
        lim += 1
    if depth >= lim:
        if isinstance(data, list) and (k.startswith("attr") or k in MULTILINE_LIST):
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
            key, value = kv
            f.write(INDENT * (depth + 1))
            f.write('"')
            f.write(str(key))
            f.write('": ')
            res = fmt_conf(value, str(key), depth + 1, f, lim, sortlim)
            if res is not None:
                f.write(res)
            if idx < end:
                f.write(",\n")
            else:
                f.write("\n")
        f.write(INDENT * depth)
        f.write("}")
        if k is None:
            f.write("\n")


def fr(num):
    try:
        return round(num, 5)
    except TypeError:
        return 0


def str_to_tuples(value):
    # result = {}
    # for pair in value.split("/"):
    #     key, value = map(int, pair.split("_"))
    #     result[key] = value
    # return result
    return [tuple(map(int, pair.split("_"))) for pair in value.split("/")]


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


def confsort(a):
    k, _ = a
    if isinstance(k, str):
        if k[0] == "x":
            try:
                return "x" + k.split("_")[1]
            except IndexError:
                return k
    return k


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
        # if s is None and part["commandType"] == CommandType.CHARACTER_COMMAND and part.get("_servantActionCommandId"):
        if s is None and part["commandType"] == CommandType.CHARACTER_COMMAND and part["_charaCommand"] in (CharacterControl.ServantAction, CharacterControl.ApplyBuffDebuff):
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


def convert_hitattr(hitattr, part, meta=None, skill=None, from_ab=False, partcond=None, parent_target=None):
    attr = {}
    target = hitattr.get("_TargetGroup")
    if target == ActionTargetGroup.FIXED_OBJECT and parent_target is not None:
        target = parent_target
    if (target in (ActionTargetGroup.HOSTILE, ActionTargetGroup.HIT_OR_GUARDED_RECORD, ActionTargetGroup.HOSTILE_AND_DUNOBJ)) and hitattr.get("_DamageAdjustment"):
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
    if sp := hitattr.get("_AdditionRecoverySp"):
        attr["sp"] = fr(sp)
    elif sp_p := hitattr.get("_RecoverySpRatio"):
        attr["sp"] = [fr(sp_p), "%"]
        if (sp_i := hitattr.get("_RecoverySpSkillIndex")) or (sp_i := hitattr.get("_RecoverySpSkillIndex2")):
            attr["sp"].append(f"s{sp_i}")
    if dp := hitattr.get("_AdditionRecoveryDpLv1"):
        attr["dp"] = dp
    if (utp := hitattr.get("_AddUtp")) or (utp := hitattr.get("_AdditionRecoveryUtp")):
        attr["utp"] = utp
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

    if bc := attr.get("_DamageUpRateByBuffCount"):
        attr["bufc"] = bc

    # if part.get("commandType") == CommandType.STOCK_BULLET_FIRE:
    #     if (stock := part.get("_fireMaxCount", 0)) > 1:
    #         attr["extra"] = stock
    #     elif (stock := action.get("_MaxStockBullet", 0)) > 1:
    #         attr["extra"] = stock
    if 0 < (attenuation := part.get("_attenuationRate", 0)) < 1:
        attr["fade"] = fr(attenuation)

    # attr_tag = None
    if actcond := hitattr.get("_ActionCondition1"):
        # attr_tag = actcond['_Id']
        # if (remove := actcond.get('_RemoveConditionId')):
        #     attr['del'] = remove
        # if actcond.get("_DamageLink"):
        #     return convert_hitattr(
        #         actcond["_DamageLink"],
        #         part,
        #         action,
        #         once_per_action,
        #         meta=meta,
        #         skill=skill,
        #     )
        ACTCOND_CONF.get(actcond)
        attr["actcond"] = str(actcond)

    if add_rng_hitlabels := hitattr.get("_AdditionalRandomHitLabel"):
        add_count = hitattr.get("_AdditionalRandomHitNum")
        add_attrs = [convert_hitattr(hl, DUMMY_PART, meta=meta, skill=skill, parent_target=target) for hl in add_rng_hitlabels]
        if len(add_attrs) == add_count:
            attr["addhit"] = add_attrs
        else:
            attr["DEBUG_ADD_RNG_HITS"] = [add_count, add_attrs]

    if attr:
        # attr[f"DEBUG_FROM_SEQ"] = part.get("_seq", 0)
        attr["target"] = target.name
        attr_with_cond = None
        if partcond:
            # look man i just want partcond to sort first
            attr_with_cond = {"pcond": partcond}
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
        if hitattr.get("_IgnoreFirstHitCheck"):
            attr["ifhc"] = 1
        if from_ab:
            attr["ab"] = 1
        return attr
    else:
        return None


def _apply_blt(part, part_hitattr_map, part_hitattr, attr_list, blt, outer_msl, ncond):
    for attr in attr_list:
        if blt is not None:
            attr["blt"] = blt
        if outer_msl:
            attr = copy.copy(attr)
            attr["msl"] = fr(outer_msl + attr.get("msl", 0))
        if part.get("_removeStockBulletOnFinish"):
            attr["mslc"] = 1
        if ncond:
            attr_with_cond = {}
            if econd := attr.get("cond"):
                attr_with_cond["cond"] = ["and", econd, ncond]
            else:
                attr_with_cond["cond"] = ncond
            attr_with_cond.update(attr)
            attr = attr_with_cond
        part_hitattr.append(attr)


def _single_bullet(part, part_hitattr_map, part_hitattr, outer_msl=None, outer_cnt=1, ncond=None, ha_attrs=None):
    if ha_attrs is None:
        ha_attrs = part_hitattr_map.get("_hitAttrLabel", [])
        if ha_sub := part_hitattr_map.get("_hitAttrLabelSubList"):
            ha_attrs.extend(ha_sub)
    if ha_attrs:
        blt = None
        if (chiv := part.get("_collisionHitInterval")) and (((bd := part.get("_bulletDuration")) and chiv < bd) or ((bd := part.get("_duration")) and chiv < bd)):
            if part.get("_useAccurateCollisionHitInterval"):
                blt = [math.ceil(bd / chiv * outer_cnt), fr(chiv)]
            else:
                blt = [int(round(bd / chiv * outer_cnt)), fr(chiv)]
        elif outer_cnt > 1:
            blt = [outer_cnt, 0.0]
        _apply_blt(part, part_hitattr_map, part_hitattr, ha_attrs, blt, outer_msl, ncond)
    if ab_attrs := part_hitattr_map.get("_abHitAttrLabel"):
        blt = None
        if (abiv := part.get("_abHitInterval")) and (abd := (part.get("_abDuration"))) and abiv < abd:
            blt = [int(round(abd / abiv * outer_cnt)), fr(abiv)]
        elif outer_cnt > 1:
            blt = [outer_cnt, 0.0]
        _apply_blt(part, part_hitattr_map, part_hitattr, ab_attrs, blt, outer_msl, ncond)


def _hit_collision_iv(part, part_hitattr_map, part_hitattr):
    if ha_attrs := part_hitattr_map.get("_hitLabel", tuple()):
        if (chiv := part.get("_collisionHitInterval")) and (((bd := part.get("_bulletDuration")) and chiv < bd) or ((bd := part.get("_duration")) and chiv < bd)):
            if part.get("_useAccurateCollisionHitInterval"):
                blt = [math.ceil(bd / chiv), fr(chiv)]
            else:
                blt = [int(round(bd / chiv)), fr(chiv)]
            _apply_blt(part, part_hitattr_map, part_hitattr, ha_attrs, blt, None, None)
            for attr in ha_attrs:
                attr["blt_iv"] = 1
        else:
            part_hitattr.extend(ha_attrs)


def convert_all_hitattr(action, pattern=None, meta=None, skill=None):
    actparts = action["_Parts"]
    hitattrs = []

    for part in actparts:
        cmdtype = part["commandType"]
        # servant for persona
        if part["commandType"] == CommandType.CHARACTER_COMMAND:
            cmd_attr = None
            if part["_charaCommand"] == CharacterControl.ServantAction:
                cmd_attr = {"DEBUG_SERVANT": part.get("_servantActionCommandId")}
            elif part["_charaCommand"] == CharacterControl.ApplyBuffDebuff:
                actcond = part["_charaCommandArgs"]["_id"]["_Id"]
                ACTCOND_CONF.get(actcond)
                cmd_attr = {"actcond": str(actcond)}
            if cmd_attr is not None:
                iv = fr(part["_seconds"])
                if iv:
                    cmd_attr["iv"] = iv
                hitattrs.append(cmd_attr)
            continue
        # parse part conds
        partcond = None
        if ctype := part.get("_conditionType"):
            condvalue = part["_conditionValue"]
            if ctype == PartConditionType.OwnerBuffCount:
                actcond = condvalue["_actionCondition"]
                if not actcond:
                    continue
                count = condvalue["_count"]
                partcond = ("actcond", str(actcond.get("_Id")), PART_COMPARISON_TO_VARS[condvalue["_compare"]], count)
            elif ctype == PartConditionType.AuraLevel:
                partcond = ("amp", (condvalue["_aura"].value, condvalue["_target"]), PART_COMPARISON_TO_VARS[condvalue["_compare"]], condvalue["_count"])
        # get the hitattrs
        part_hitattr_map = defaultdict(list)
        if raw_hitattrs := part.get("_allHitLabels"):
            for source, hitattr_lst in raw_hitattrs.items():
                for hitattr in reversed(hitattr_lst):
                    if isinstance(hitattr, str):
                        continue
                    if (not pattern or pattern.match(hitattr["_Id"])) and (
                        attr := convert_hitattr(
                            hitattr,
                            part,
                            meta=meta,
                            skill=skill,
                            partcond=partcond,
                        )
                    ):
                        part_hitattr_map[source].append(attr)
                        if not pattern:
                            break
        if not part_hitattr_map:
            continue
        part_hitattr_map = dict(part_hitattr_map)
        # loop & bullets
        part_hitattr = []

        if cmdtype == CommandType.HIT_ATTRIBUTE:
            _hit_collision_iv(part, part_hitattr_map, part_hitattr)
        elif cmdtype == CommandType.SETTING_HIT:
            for attr in part_hitattr_map.get("_hitAttrLabel", tuple()):
                attr["zone"] = part.get("_lifetime", -1)
                part_hitattr.append(attr)
        elif cmdtype == CommandType.REMOVE_BUFF_TRIGGER_BOMB:
            for attr in part_hitattr_map.get("_hitAttrLabel", tuple()):
                attr["triggerbomb"] = part.get("_targetActionConditionId")
                part_hitattr.append(attr)
        elif cmdtype == CommandType.BUFFFIELD_ATTACHMENT and part.get("_isAttachToSelfBuffField"):
            for attr in part_hitattr_map.get("_hitAttrLabel", tuple()):
                attr["msl"] = part.get("_hitDelaySec")
                attr["blt"] = ["zonecount", 0.0]
                part_hitattr.append(attr)
        elif cmdtype in BULLET_COMMAND:
            _single_bullet(part, part_hitattr_map, part_hitattr)
        elif cmdtype == CommandType.STOCK_BULLET_FIRE:
            gn = part.get("_bulletNum", 1)
            if specific_delay := part.get("_delayFireSec"):
                delays = json.loads(specific_delay)
                if ms_gn := action.get("_MaxStockBullet"):
                    for idx in range(ms_gn):
                        ncond = ["var", "buffcount", ">=", idx + 1]
                        _single_bullet(part, part_hitattr_map, part_hitattr, outer_msl=delays[idx], ncond=ncond)
                else:
                    for delay in delays[0:gn]:
                        _single_bullet(part, part_hitattr_map, part_hitattr, outer_msl=delay)
            else:
                if ms_gn := part.get("_MaxStockBullet"):
                    for idx in range(ms_gn):
                        ncond = ["var", "buffcount", ">=", idx + 1]
                        _single_bullet(part, part_hitattr_map, part_hitattr, outer_msl=0.0, ncond=ncond)
                else:
                    _single_bullet(part, part_hitattr_map, part_hitattr, outer_cnt=gn)
        elif cmdtype == CommandType.MULTI_BULLET:
            marker_charge = part.get("_bulletMarkerChargeSec", 0)
            ncond = None
            if part.get("_useFireStockBulletParam"):
                gn = part.get("_bulletNum")
                specific_delay = part.get("_delayFireSec")
            elif part.get("_generateNumDependOnBuffCount"):
                buffcond = part.get("_buffCountConditionId")
                gn = buffcond.get("_MaxDuplicatedCount", 10)
                ncond = ["actcond", str(int(buffcond["_Id"])), ">="]
                specific_delay = part.get("_markerDelay")
            else:
                gn = part.get("_generateNum")
                specific_delay = part.get("_markerDelay")
            if part.get("_stopWhenAllTargetsGen"):
                gn = 1
            if specific_delay:
                delays = [marker_charge + d for d in json.loads(specific_delay)[0:gn]]
                if ncond is not None:
                    for idx, delay in enumerate(delays):
                        _single_bullet(part, part_hitattr_map, part_hitattr, outer_msl=delay, ncond=[*ncond, idx + 1])
                else:
                    for delay in delays:
                        _single_bullet(part, part_hitattr_map, part_hitattr, outer_msl=delay)
            else:
                if ncond is not None:
                    for idx in range(gn):
                        _single_bullet(part, part_hitattr_map, part_hitattr, outer_msl=marker_charge, ncond=[*ncond, idx + 1])
                else:
                    _single_bullet(part, part_hitattr_map, part_hitattr, outer_msl=marker_charge, outer_cnt=gn)
        elif cmdtype == CommandType.FORMATION_BULLET:
            if gn := part.get("_bulletNum"):
                if fb_sub := part_hitattr_map.get("_formationChildHitAttrLabel"):
                    _single_bullet(part, part_hitattr_map, part_hitattr, outer_cnt=gn / 2, ha_attrs=fb_sub)
                _single_bullet(part, part_hitattr_map, part_hitattr)

        if part.get("_loopFlag"):
            lp = [part.get("_loopNum", -2) + 1, fr(part.get("_seconds") - part.get("_loopSec", 0.0))]
            for attr in part_hitattr:
                attr["loop"] = lp

        hitattrs.extend(part_hitattr)

    if action.get("_OnHitExecType") == 1:
        for attr in hitattrs:
            attr["ifhc"] = 1
    return hitattrs


def hitattr_adj(action, s, conf, pattern=None, skip_nohitattr=True, meta=None, skill=None, attr_key="attr", next_idx=0):
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
        next_res = hitattr_adj(
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
    xconf = hitattr_adj(xn, s, xconf, skip_nohitattr=False, pattern=pattern)

    if xn.get("_IsLoopAction") and any((xn["_Id"] == fb[1] for fb in followed_by)):
        xconf["loop"] = 1

    if convert_follow:
        xconf["interrupt"], xconf["cancel"] = convert_following_actions(s, followed_by, ("s",))

    return xconf


def convert_misc(action, convert_follow=True):
    s, r, followed_by = hit_sr(action)
    actconf = {"startup": s, "recovery": r}
    if not (actconf := hitattr_adj(action, s, actconf, skip_nohitattr=True)):
        return None
    if r is not None and convert_follow:
        actconf["interrupt"], actconf["cancel"] = convert_following_actions(s, followed_by, ("s",))
    else:
        del actconf["recovery"]
    return actconf


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
        fsconf[key] = hitattr_adj(
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
        if mpart is not None and mpart.get("_chargeLvSec") and not is_dragon and max_CHLV > 1:
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
                clv_attr = hitattr_adj(burst, startup, base_fs_conf.copy(), clv_pattern)
                totalc += c
                if clv_attr:
                    fsn = f"{key}{idx+1}"
                    fsconf[fsn] = clv_attr
                    fsconf[fsn]["charge"] = fr(totalc)
                    fsconf[fsn]["interrupt"], fsconf[fsn]["cancel"] = convert_following_actions(startup, followed_by, ("s",))
        else:
            fsconf[key] = {"charge": fr(charge), "startup": startup, "recovery": recovery}
            fsconf[key] = hitattr_adj(burst, startup, fsconf[key], hitattr_pattern, skip_nohitattr=False)
            fsconf[key]["interrupt"], fsconf[key]["cancel"] = convert_following_actions(startup, followed_by, ("s",))
    if not is_dragon and cancel is not None:
        fsconf["fsf"] = {
            "charge": fr(0.1 + cancel["_Parts"][0]["_duration"]),
            "startup": 0.0,
            "recovery": 0.0,
            "interrupt": {"s": (0.0, None)},
            "interrupt": {"s": (0.0, None)},
        }

    return fsconf


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


class SDat:
    def __init__(self, sid, base, group, skill=None, from_sid=None) -> None:
        self.sid = sid
        self.base = base
        self.group = group
        if self.group is None:
            self.name = self.base
        else:
            self.name = f"{self.base}_{self.group}"
        self.skill = skill
        self.from_sid = from_sid


class SkillProcessHelper:
    MISSING_ENDLAG = []

    def reset_meta(self):
        self.chara_skills = {}
        self.enhanced_counter = defaultdict(lambda: itertools.count(start=0))
        self.all_chara_skills = {}
        self.enhanced_fs = {}
        self.ab_alt_attrs = defaultdict(lambda: [])
        self.action_ids = {}
        # for advs only
        self.alt_actions = []
        self.utp_chara = None
        self.hit_attr_shift = False
        self.chara_modes = {}
        self.cp1_gauge = 0
        self.combo_shift = False
        self.trans_skill = None

    def get_enhanced_key(self, base):
        nid = next(self.enhanced_counter[base])
        if nid == 0:
            return "enhanced"
        return f"enhanced{nid}"

    def set_ability_and_actcond_meta(self):
        self.index["AbilityConf"].set_meta(self)
        self.index["ActCondConf"].set_meta(self)

    def unset_ability_and_actcond_meta(self, res):
        self.index["AbilityConf"].set_meta(None)
        if curr_conds := self.index["ActCondConf"].curr_actcond_conf:
            res["actconds"] = curr_conds
        self.index["ActCondConf"].set_meta(None)

    def convert_skill(self, sdat, lv):
        if sdat.skill is None:
            sdat.skill = self.index["SkillData"].get(sdat.sid)
        action = 0
        if lv >= sdat.skill.get("_AdvancedSkillLv1", float("inf")):
            skey_pattern = "_AdvancedActionId{}"
            action = sdat.skill.get(skey_pattern.format(1))
        if isinstance(action, int):
            skey_pattern = "_ActionId{}"
            action = sdat.skill.get("_ActionId1")

        startup, recovery, followed_by = hit_sr(action, startup=0)

        if not recovery:
            SkillProcessHelper.MISSING_ENDLAG.append(sdat.skill.get("_Name"))

        sconf = {
            "sp": sdat.skill.get(f"_SpLv{lv}", sdat.skill.get("_Sp", 0)),
            "startup": startup,
            "recovery": recovery,
        }

        if self.hit_attr_shift:
            hitlabel_pattern = re.compile(f".*\d_LV0{lv}.*")
            sconf = hitattr_adj(
                action,
                sconf["startup"],
                sconf,
                skip_nohitattr=False,
                pattern=hitlabel_pattern,
                meta=self,
                skill=sdat.skill,
            )
            sconf = hitattr_adj(action, sconf["startup"], sconf, skip_nohitattr=False, pattern=re.compile(f".*\d_HAS_LV0{lv}.*"), meta=self, skill=sdat.skill, attr_key="attr_HAS")
        else:
            hitlabel_pattern = re.compile(f".*LV0{lv}$")
            sconf = hitattr_adj(
                action,
                sconf["startup"],
                sconf,
                skip_nohitattr=False,
                pattern=hitlabel_pattern,
                meta=self,
                skill=sdat.skill,
            )
        hitattrs = sconf.get("attr")
        if (not hitattrs or all(["dmg" not in attr for attr in hitattrs if isinstance(attr, dict)])) and sdat.skill.get(f"_IsAffectedByTensionLv{lv}"):
            sconf["energizable"] = bool(sdat.skill[f"_IsAffectedByTensionLv{lv}"])

        interrupt, cancel = convert_following_actions(0, followed_by)
        if interrupt:
            sconf["interrupt"] = interrupt
        if cancel:
            sconf["cancel"] = cancel

        for idx in range(2, 5):
            if rng_actions := sdat.skill.get(skey_pattern.format(idx)):
                hitattr_adj(
                    rng_actions,
                    sconf["startup"],
                    sconf,
                    skip_nohitattr=False,
                    pattern=hitlabel_pattern,
                    meta=self,
                    skill=sdat.skill,
                    attr_key=f"DEBUG_attr_R{idx}",
                )

        if isinstance((transkills := sdat.skill.get("_TransSkill")), dict):
            for idx, ts in enumerate(transkills.items()):
                tsid, tsk = ts
                if tsid not in self.all_chara_skills:
                    self.chara_skills[tsid] = SDat(tsid, sdat.base, f"phase{idx+1}", tsk, sdat.sid)
        if tbuff := sdat.skill.get("_TransBuff"):
            self.trans_skill = (sdat.base, sdat.group)
            sconf["phase_buff"] = convert_all_hitattr(tbuff, pattern=re.compile(f".*LV0{lv}$"), meta=self, skill=sdat.skill)

        if isinstance((chainskills := sdat.skill.get("_ChainGroupId")), list):
            for idx, cs in enumerate(chainskills):
                cskill = cs["_Skill"]
                activate = cs.get("_ActivateCondition", 0)
                if cskill["_Id"] not in self.all_chara_skills:
                    self.chara_skills[cskill["_Id"]] = SDat(cskill["_Id"], sdat.base, f"chain{activate}", cskill, sdat.sid)

        if isinstance((ocskill := sdat.skill.get("_OverChargeSkillId")), dict):
            n = 1
            prev_sid = sdat.skill.get("_Id")
            prev_entry = None
            while prev_sid in self.chara_skills:
                prev_entry = self.chara_skills[prev_sid]
                if prev_entry.group is None or not prev_entry.group.startswith("overcharge"):
                    break
                n += 1
                prev_sid = prev_entry.from_sid
            self.chara_skills[ocskill["_Id"]] = SDat(ocskill["_Id"], sdat.base, f"overcharge{n}", ocskill, sdat.sid)

        # if ab := skill.get(f"_Ability{lv}"):
        #     self.parse_skill_ab(k, seq, skill, action, sconf, ab)

        if ab := sdat.skill.get(f"_Ability{lv}"):
            # jank
            if isinstance(ab, dict):
                ab = ab["_Id"]
            sconf["abilities"] = self.index["AbilityConf"].get(ab, source="abilities")

        return sconf, action

    def convert_alt_actions(self, conf):
        for act, actdata in self.alt_actions:
            if not actdata:
                continue
            actconf = None
            if act == "fs" and (marker := actdata.get("_BurstMarkerId")):
                actconf = convert_fs(actdata, marker)["fs"]
                if act in conf:
                    act = f"{act}_abalt"
            else:
                actconf = convert_misc(actdata)
                if act == "dodge":
                    # hax for lv1 of the ability
                    self.action_ids[actdata["_Id"] - 1] = act
            if actconf:
                conf[act] = actconf
                self.action_ids[actdata["_Id"]] = act

    def process_skill(self, res, conf, mlvl):
        # exceptions exist
        while self.chara_skills:
            sdat = next(iter(self.chara_skills.values()))
            if sdat.base == "s99":
                lv = mlvl.get(f's{res["_EditSkillLevelNum"]}')
            else:
                lv = mlvl.get(sdat.base, 2)
            cskill, action = self.convert_skill(sdat, lv)
            conf[sdat.name] = cskill
            self.action_ids[action.get("_Id")] = sdat.name
            self.all_chara_skills[sdat.sid] = sdat
            del self.chara_skills[sdat.sid]

        for efs, eba in self.enhanced_fs.values():
            for fs, fsc in convert_fs(eba, eba.get("_BurstMarkerId")).items():
                if efs in (None, "default"):
                    fsn = fs
                else:
                    fsn = f"{fs}_{efs}"
                conf[fsn] = fsc
                self.action_ids[eba["_Id"]] = "fs"

        self.convert_alt_actions(conf)


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
        for res in tqdm(all_res, desc="amp"):
            outdata[str(res["_Id"])] = self.process_result(res)
        output = os.path.join(out_dir, "amp.json")
        with open(output, "w", newline="", encoding="utf-8") as fp:
            fmt_conf(outdata, f=fp)


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
        AbilityTargetAction.HUMAN_SKILL_2: "s2",
        AbilityTargetAction.DRAGON_SKILL_1: "ds1",
        AbilityTargetAction.SKILL_4: "s4",
        AbilityTargetAction.HUMAN_SKILL_3: "s3",
        AbilityTargetAction.HUMAN_SKILL_4: "s4",
    }
    # ABL_GROUPS = {}

    def __init__(self, index):
        super().__init__(index)
        self.meta = None
        self.source = None
        self.enhanced_key = None
        self.use_ablim_groups = False
        self.use_shift_groups = False
        # if not self.ABL_GROUPS:
        #     self.ABL_GROUPS = {r["_Id"]: r for r in self.index["AbilityLimitedGroup"].get_all()}

    def set_meta(self, meta, use_ablim_groups=False):
        self.meta = meta
        self.source = None
        self.enhanced_key = None
        self.use_ablim_groups = use_ablim_groups or False
        self.use_shift_groups = self.use_ablim_groups

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

    ac_BREAKDOWN = ac_NONE
    ac_OVERDRIVE = ac_NONE
    ac_DEBUFF_SLIP_HP = ac_NONE

    def ac_HP_MORE(self, res):
        return ["hp", ">=", int(res["_ConditionValue"])]

    def ac_HP_LESS(self, res):
        return ["hp", "<=", int(res["_ConditionValue"])]

    def ac_BUFF_SKILL1(self, res):
        return ["buffed_by", "s1"]

    def ac_BUFF_SKILL2(self, res):
        return ["buffed_by", "s2"]

    def ac_DRAGON_MODE(self, res):
        return ["shift", "dform"]

    def ac_GET_BUFF_DEF(self, res):
        return ["doublebuff"]

    def ac_TOTAL_HITCOUNT_MORE(self, res):
        return ["hits", ">=", int(res["_ConditionValue"]), 1]

    def ac_TOTAL_HITCOUNT_LESS(self, res):
        return ["hits", "<", int(res["_ConditionValue"]), 1]

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
        return ["event", "start"]

    def ac_ABNORMAL_STATUS(self, res):
        return ["aff", AFFLICTION_TYPES.get(int(res["_ConditionValue"])).lower()]

    def ac_TENSION_MAX(self, res):
        return ["energy", "=", 5]

    def ac_TENSION_MAX_MOMENT(self, res):
        return ["event", "energized"]

    def ac_HITCOUNT_MOMENT(self, res):
        cond = ["hitcount", int(res["_ConditionValue"])]
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

    def ac_NO_DAMAGE_REACTION_TIME(self, res):
        return ["dauntless"]

    def ac_BUFFED_SPECIFIC_ID(self, res):
        return ["actcond", str(int(res["_ConditionValue"])), ">=", 1]

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
        cp_value = int(res["_ConditionValue"])
        if self.meta is not None:
            self.meta.cp1_gauge = max(cp_value, self.meta.cp1_gauge)
        if cp_value > 0:
            return ["cp", ">=", cp_value]
        else:
            return ["event", "cp_full"]

    def ac_REQUIRED_BUFF_AND_SP1_MORE(self, res):
        # all examples of these have _ConditionValue=-1.0
        return ["sp", "s1", ">", int(res["_ConditionValue"])]

    def ac_ALWAYS_REACTION_TIME(self, res):
        return ["always"]

    def ac_ON_ABNORMAL_STATUS_RESISTED(self, res):
        return ["antiaff", AFFLICTION_TYPES.get(int(res["_ConditionValue"])).lower()]

    def ac_BUFF_DISAPPEARED(self, res):
        return ["actcondend", int(res["_ConditionValue"])]

    def ac_BUFFED_SPECIFIC_ID_COUNT(self, res):
        return ["actcond", str(int(res["_ConditionValue2"])), "=", int(res["_ConditionValue"])]

    def ac_CHARGE_LOOP_REACTION_TIME(self, res):
        return ["fs_hold", "charge"]

    def ac_AVOID(self, res):
        return ["event", "dodge"]

    def ac_CAUSE_DEBUFF_SLIP_HP(self, res):
        return ["bleed", 1]

    def ac_CP1_OVER(self, res):
        return ["cp", ">=", int(res["_ConditionValue"])]

    def ac_BUFF_COUNT_MORE_THAN(self, res):
        return ["actcond", str(int(res["_ConditionValue2"])), ">=", int(res["_ConditionValue"])]

    def ac_BUFF_CONSUMED(self, res):
        return ["actcondend", int(res["_ConditionValue"]), 1]

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

    def ac_DUP_BUFF_ALWAYS_TIMESRATE(self, res):
        return ["mult", "actcond", int(res["_ConditionValue"]), int(res["_ConditionValue2"])]

    def ac_BUFFED_SPECIFIC_ID_COUNT_MORE_ALWAYS_CHECK(self, res):
        return ["actcond", int(res["_ConditionValue2"]), ">=", int(res["_ConditionValue"])]

    def ac_GET_BUFF_FROM_SKILL(self, res):
        return ["event", "buffed"]

    def ac_RELEASE_DIVINEDRAGONSHIFT(self, res):
        return ["event", "divinedragon_end"]

    def ac_HAS_AURA_TYPE(self, res):
        return ["amp", int(res["_ConditionValue2"]), int(res["_ConditionValue"]), ">=", 1]

    def ac_PARTY_AURA_LEVEL_MORE(self, res):
        return ["amp", 2, int(res["_ConditionValue"]), ">=", int(res["_ConditionValue2"])]

    def ac_DRAGONSHIFT(self, res):
        return ["event", "dragon"]

    def ac_DRAGON_MODE_STRICTLY(self, res):
        return ["shift", "dform"]

    def ac_ACTIVATE_SKILL(self, res):
        return ["event", "s"]

    def ac_SELF_AURA_MOMENT(self, res):
        return ["get_amp", int(res["_ConditionValue2"]), int(res["_ConditionValue"])]

    def ac_PARTY_AURA_LEVEL_MORE_REACTION_TIME(self, res):
        return ["amp", 2, int(res["_ConditionValue"]), ">=", int(res["_ConditionValue2"])]

    def ac_ON_REMOVE_ABNORMAL_STATUS(self, res):
        return ["event", "relief"]

    # AbilityType
    STAT_TO_MOD = {
        AbilityStat.Hp: "hp",
        AbilityStat.Atk: "att",
        AbilityStat.Def: "def",
        AbilityStat.Spr: "sph",
        AbilityStat.Dpr: "dph",
        AbilityStat.DragonTime: "dt",
        AbilityStat.AttackSpeed: "aspd",
        AbilityStat.BurstSpeed: "fspd",
        AbilityStat.ChargeSpeed: "cspd",
        AbilityStat.NeedDpRate: "dpcost",
    }

    def _at_upval(self, name, res, i, div=100):
        return [name, self._upval(res, i, div=div)]

    def _at_mod(self, res, i, *modargs, div=100):
        return ["mod", self._upval(res, i, div=div), *modargs]

    def _at_aff(self, name, res, i, div=100):
        return self._at_mod(res, i, f"{name}_{AFFLICTION_TYPES[self._varid_a(res, i)].lower()}", div=div)

    def at_StatusUp(self, res, i):
        try:
            return self._at_mod(res, i, AbilityConf.STAT_TO_MOD[AbilityStat(self._varid_a(res, i))])
        except KeyError:
            return None

    def at_ResistAbs(self, res, i):
        return self._at_aff("affres", res, i)

    def at_ActAddAbs(self, res, i):
        return self._at_aff("edge", res, i)

    def at_ActKillerTribe(self, res, i):
        # return ["killer", TRIBE_TYPES[self._varid_a(res, i)].lower(), self._upval(res, i)]
        return self._at_mod(res, i, f"killer_{TRIBE_TYPES[self._varid_a(res, i)].lower()}")

    ADU_MOD = {
        AbilityCondition.DEBUFF_SLIP_HP: ("killer_bleed",),
        AbilityCondition.BREAKDOWN: ("killer_break", "ex"),
        AbilityCondition.OVERDRIVE: ("killer_overdrive",),
    }

    def at_ActDamageUp(self, res, i):
        # return self._at_mod(res, i, "actdmg")
        if adu_mod := AbilityConf.ADU_MOD.get(res["_ConditionType"]):
            return self._at_mod(res, i, *adu_mod)
        return self._at_upval("actdmg", res, i)

    def at_ActCriticalUp(self, res, i):
        return self._at_mod(res, i, "crit")

    def at_ActRecoveryUp(self, res, i):
        return self._at_mod(res, i, "rcv")

    def at_ActBreakUp(self, res, i):
        return self._at_mod(res, i, "odaccel")

    def at_AddRecoverySp(self, res, i):
        return self._at_mod(res, i, "sph")

    def at_ChangeState(self, res, i):
        buffs = []
        for bid in self._varids(res, i):
            if bid:
                buffs.append(str(bid))
        if buffs:
            for bid in buffs:
                # ik i do have self.index here but i'll keep the oof bits consistent
                # multiple buff id = shifting abilities
                ACTCOND_CONF.get(bid)
            return ["actcond", ActionTargetGroup.MYSELF.name, *buffs]
        else:
            hitattr = convert_hitattr(self.index["PlayerActionHitAttribute"].get(res[f"_VariousId{i}str"]), DUMMY_PART)
            # if set(hitattr.keys()) == {"actcond", "target"} and hitattr["target"] == "MYSELF":
            #     return ["actcond", hitattr["target"], hitattr["actcond"]]
            return ["hitattr", hitattr]

    def at_DebuffGrantUp(self, res, i):
        return self._at_mod(res, i, "debuffrate")

    def at_SpCharge(self, res, i):
        return self._at_upval("prep", res, i)

    def at_BuffExtension(self, res, i):
        return self._at_mod(res, i, "bufftime")

    def at_DebuffExtension(self, res, i):
        return self._at_mod(res, i, "debufftime")

    def at_AbnormalKiller(self, res, i):
        return self._at_aff("killer", res, i)

    def at_ActionGrant(self, res, i):
        action_grant = self.index["ActionGrant"].get(self._varid_a(res, i), full_query=False)
        res[f"_TargetAction{i}"] = action_grant["_TargetAction"]
        ACTCOND_CONF.get(action_grant["_GrantCondition"])
        return ["actgrant", action_grant["_GrantCondition"]]

    def at_CriticalDamageUp(self, res, i):
        return self._at_mod(res, i, "critdmg")

    def at_DpCharge(self, res, i):
        return self._at_upval("dprep", res, i)

    def at_ResistElement(self, res, i):
        return self._at_mod(res, i, "eleres", ELEMENTS[self._varid_a(res, i)].lower())

    def at_DragonDamageUp(self, res, i):
        return self._at_mod(res, i, "dragondmg")

    def at_HitAttribute(self, res, i):
        return self.at_ChangeState(res, i)

    def at_PassiveGrant(self, res, i):
        return self.at_ActionGrant(res, i)

    def at_HitAttributeShift(self, res, i):
        if self.meta is not None:
            self.meta.hit_attr_shift = True
        return ["hit_attr_shift"]

    def at_EnhancedSkill(self, res, i):
        skill_id = self._varid_a(res, i)
        target = AbilityTargetAction(res[f"_TargetAction{i}"])
        seq = int(target.name[-1:])
        sn = f"s{seq}"
        if self.meta is not None:
            if skill_id not in self.meta.chara_skills and skill_id not in self.meta.all_chara_skills:
                if res["_ConditionType"] is None:
                    ekey = None
                else:
                    if self.enhanced_key is None:
                        self.enhanced_key = self.meta.get_enhanced_key(sn)
                    ekey = self.enhanced_key
                self.meta.chara_skills[skill_id] = SDat(skill_id, sn, ekey)
            else:
                if res["_ConditionType"] is None:
                    ekey = None
                else:
                    try:
                        sdat = self.meta.chara_skills[skill_id]
                    except KeyError:
                        sdat = self.meta.all_chara_skills[skill_id]
                    ekey = sdat.group or "default"
            if ekey is None:
                return None
            return ["altskill", ekey]

    def at_EnhancedBurstAttack(self, res, i):
        # will assume only albert uses this and unconditionally for now
        burst_id = self._varid_a(res, i)
        if self.meta is not None:
            if burst_id not in self.meta.enhanced_fs:
                burst = self.index["PlayerAction"].get(burst_id)
                if res["_ConditionType"] == AbilityCondition.NONE:
                    ekey = None
                else:
                    if self.enhanced_key is None:
                        self.enhanced_key = self.meta.get_enhanced_key("fs")
                    ekey = self.enhanced_key
                self.meta.enhanced_fs[burst_id] = (ekey, burst)
            else:
                ekey = self.meta.enhanced_fs[burst_id][0]
            if ekey is None:
                return None
            return ["altfs", ekey]

    def at_AbnoramlExtension(self, res, i):
        return self._at_aff("afftime", res, i)

    def at_DragonTimeSpeedRate(self, res, i):
        value = 100 / (100 + self._upval(res, i))
        return ["mod", value, "dt"]

    def at_DpChargeMyParty(self, res, i):
        return self._at_upval("dprep", res, i)

    def at_CriticalUpDependsOnBuffTypeCount(self, res, i):
        return self._at_mod(res, i, "crit")

    def at_ChainTimeExtension(self, res, i):
        return self._at_upval("ctime", res, i, div=1)

    def at_UniqueTransform(self, res, i):
        if self.meta is not None:
            self.meta.utp_chara = [res[f"_VariousId{i}a"], *(int(v) for v in res[f"_VariousId{i}str"].split("/"))]
        return None

    def at_EnhancedElementDamage(self, res, i):
        return self._at_mod(res, i, "eledmg", ELEMENTS[self._varid_a(res, i)].lower())

    def at_UtpCharge(self, res, i):
        return self._at_upval("utprep", res, i)

    def at_ChangeMode(self, res, i):
        m = self._varid_a(res, i) + 1
        # mode name stuff
        if res["_ConditionType"] == AbilityCondition.BUFF_DISAPPEARED and res["_ConditionValue"] == 1152:
            mode_name = "sigil"
        elif res["_ConditionType"] == AbilityCondition.CP1_CONDITION:
            mode_name = "modecp"
        else:
            if m == 1:
                mode_name = ""
            else:
                mode_name = f"mode{m}"
        if self.meta is not None:
            if mode_name:
                self.meta.chara_modes[m] = f"_{mode_name}"
            else:
                self.meta.chara_modes[m] = mode_name
        return ["mode", mode_name]

    def at_ModifyBuffDebuffDurationTime(self, res, i):
        # this is actually a percent, based on _DurationSec/(_DurationTimeScale or 1)
        return ["ac_t", self._varid_a(res, i), self._upval(res, i)]

    def at_CpCoef(self, res, i):
        return self._at_mod(res, i, "cph")

    def at_UniqueAvoid(self, res, i):
        # can this take a cond? unclear
        avoid_id = self._varid_a(res, i)
        if self.meta is not None:
            avoid = self.index["PlayerAction"].get(avoid_id)
            self.meta.alt_actions.append(("dodge", avoid))
        return None

    def at_ChangeStateHostile(self, res, i):
        ab = self.at_ChangeState(res, i)
        ab[1] = ActionTargetGroup.HOSTILE.name
        return ab

    def at_CpContinuationDown(self, res, i):
        return self._at_upval("cp_degen", res, i, div=1)

    def at_AddCpRate(self, res, i):
        return self._at_upval("cprep", res, i)

    def at_RunOptionAction(self, res, i):
        try:
            if (act := self.index["PlayerAction"].get(self._varid_a(res, i))) and (actconf := convert_misc(act, convert_follow=False)):
                for hitattr in actconf["attr"]:
                    for key in list(hitattr):
                        if key.startswith("DEBUG_"):
                            del hitattr[key]
                return ["hitattr", *actconf["attr"]]
        except Exception:
            pass
        return None

    def at_ConsumeSpToRecoverHp(self, res, i):
        return ["to_hp", "sp", self._upval(res, i)]  # only instance of this has a SR, unclear what happens on normal adv

    def at_CrestGroupScoreUp(self, res, i):
        return ["psalm", res["_BaseCrestGroupId"], res["_TriggerBaseCrestGroupCount"], int(self._upval(res, i, div=1))]

    def at_ModifyBuffDebuffDurationTimeByRecoveryHp(self, res, i):
        return ["ac_t_healed", res[f"_VariousId{i}a"], self._upval(res, i), res[f"_VariousId{i}b"], res[f"_VariousId{i}c"]]

    def at_CrisisRate(self, res, i):
        return self._at_upval("crisis", res, i)

    def at_ActDamageDown(self, res, i):
        return self._at_mod(res, i, "actdmgdown")

    def at_RunOptionActionRemoteToo(self, res, i):
        return self.at_RunOptionAction(res, i)

    def at_ConsumeUtpToRecoverHp(self, res, i):
        return ["to_hp", "utp", self._upval(res, i)]

    def at_DpGaugeCap(self, res, i):
        return self._at_upval("dprep_cap", res, i)

    def at_AbnormalTypeNumKiller(self, res, i):
        return ["aff_num_k", [int(r) for r in res[f"_VariousId{i}str"].split("/")]]

    def at_ActDamageUpDependsOnHitCount(self, res, i):
        return ["actdmg_hitcount", [int(r) for r in res[f"_VariousId{i}str"].split("/")]]

    def at_RebornHpRateUp(self, res, i):
        return ["reborn_hp", self._upval(res, i)]

    # processing
    def process_result(self, res, source=None):
        if self.use_shift_groups and (shiftgroup := res.get("_ShiftGroupId")):
            return [{"id": str(res["_Id"]), "shiftgroup": str(shiftgroup)}]
        self.enhanced_key = None
        if source is not None:
            self.source = source
        conf = {}
        if self.source == "ex":
            if res["_Name"]:
                conf["name"] = res["_Name"]
            if res["_AbilityIconName"]:
                conf["icon"] = res["_AbilityIconName"]
        if self.source == "talisman":
            if res["_Name"]:
                conf["name"] = res["_Name"].format(element_owner="Element", weapon_owner="Weapon", ability_val0=int(res.get("_AbilityType1UpValue", 0)))
            if res["_AbilityIconName"]:
                conf["icon"] = res["_AbilityIconName"]
        # cond
        condtype = AbilityCondition(res["_ConditionType"])
        try:
            if cond := getattr(self, f"ac_{condtype.name}")(res):
                conf["cond"] = cond
        except AttributeError:
            condtype = None
        res["_ConditionType"] = condtype
        # actcond
        if reqac := res.get("_RequiredBuff"):
            conf["actcond"] = str(reqac)
        # cd
        if cd := res.get("_CoolTime"):
            conf["cd"] = cd
        # count
        if count := res.get("_MaxCount"):
            conf["count"] = count
        # ele
        if ele := res.get("_ElementalType"):
            try:
                conf["ele"] = ELEMENTS[ele].lower()
            except KeyError:
                pass
        # wt
        if wt := res.get("_WeaponType"):
            try:
                conf["wt"] = WEAPON_TYPES[wt].lower()
            except KeyError:
                pass
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
                            ab.append(f"-t:{AbilityConf.TARGET_ACT[target]}")
                        # if self.use_ablim_groups and res[f"_AbilityLimitedGroupId{i}"]:
                        #     if (idx := res[f"_AbilityLimitedGroupId{i}"]):
                        #         ab.append(f"-lg:{idx}")
                        ablist.append(ab)
                except (AttributeError, ValueError):
                    pass
        if ablist and condtype:
            conf["ab"] = ablist
            conflist.insert(0, conf)

        # AbilityLimitedGroup does not reflect irl mix outside of certain buff abilities on wyrmprints
        if self.use_ablim_groups and res["_AbilityLimitedGroupId1"]:
            if len(ablist) == 1:
                conf["lg"] = str(res["_AbilityLimitedGroupId1"])
            else:
                conf["DEBUG_LIMGROUP"] = str(res["_AbilityLimitedGroupId1"])

        if source is not None:
            self.source = None
        return list(filter(None, conflist))

    def export_all_talisman_to_folder(self, out_dir="./out", ext=".json"):
        check_target_path(out_dir)
        self.use_ablim_groups = True
        self.use_shift_groups = False
        output = os.path.join(out_dir, f"talisman{ext}")
        all_res = self.get_all(where="_Id > 340000000 AND _Id < 400000000")
        outdata = defaultdict(dict)
        for res in tqdm(all_res, desc="talisman"):
            if conf := self.process_result(res, source="talisman"):
                ab = conf[0].get("ab")
                if not ab or len(ab) > 1:
                    ab_key = "hitter"
                else:
                    ab = ab[0]
                    if ab[0] == "actdmg":
                        ab_key = ab[2].split(":")[-1]
                    elif ab[0] == "mod":
                        ab_key = ab[2]
                    else:
                        ab_key = ab[0]
                outdata[ab_key][str(res["_Id"])] = conf
        with open(output, "w") as fn:
            fmt_conf(outdata, f=fn)
        self.use_ablim_groups = False
        self.use_shift_groups = False


class ActCondConf(ActionCondition):
    EXCLUDE_FALSY = False

    def __init__(self, index):
        super().__init__(index)
        self.meta = None
        self.all_actcond_conf = {}
        self._curr_actcond_conf = {}

    def set_meta(self, meta):
        self.meta = meta
        self._curr_actcond_conf = {}

    @property
    def curr_actcond_conf(self):
        return dict(sorted(self._curr_actcond_conf.items()))

    UNITY_TEXT_FMT = re.compile(r"<.+>|\\n")

    @staticmethod
    def clean_text(conf, text):
        if "mods" in conf and "{0:P0}" in text:
            text = text.replace("{0:P0}", f'{abs(conf["mods"][0][0]):.0%}')
        return ActCondConf.UNITY_TEXT_FMT.sub(" ", text).strip()

    def _process_metadata(self, conf, res):
        # no clue: _UnifiedManagement/_DebuffCategory/_RemoveDebuffCategory
        # visuals, prob: _UsePowerUpEffect/_NotUseStartEffect/_StartEffectCommon/_StartEffectAdd/_DurationNumConsumedHeadText
        # _KeepOnDragonShift: assume this is default
        # _RestoreOnReborn: no revive in sim
        flag = res["_InternalFlag"]
        if flag & 1:  # NoIcon = 1
            conf["icon"] = 0
        elif res["_BuffIconId"]:
            conf["icon"] = res["_BuffIconId"]
        if res["_Text"]:
            conf["text"] = ActCondConf.clean_text(conf, res["_Text"])
        if flag >> 1 & 1:  # NoCount = 2
            conf["hide"] = 1
        if res["_OverwriteGroupId"]:
            conf["overwrite"] = res["_OverwriteGroupId"]
        elif res["_OverwriteIdenticalOwner"] or res["_Overwrite"]:
            conf["refresh"] = 1
        if res["_MaxDuplicatedCount"] > 1:
            conf["maxstack"] = res["_MaxDuplicatedCount"]
        elif res["_StackData"]:  # StackBuffData
            conf["maxstack"] = self.index["StackBuffData"].get(res["_StackData"]).get("_LimitNum")
        if res["_Rate"] and res["_Rate"] != 100:
            conf["rate"] = res["_Rate"] / 100
        if res["_LostOnDragon"]:
            conf["lost_on_drg"] = res["_LostOnDragon"]
        if res["_CurseOfEmptinessInvalid"]:
            conf["coei"] = res["_CurseOfEmptinessInvalid"]
        if res["_ResistBuffReset"] or res["_ResistDebuffReset"]:
            conf["unremovable"] = 1
        # if res["_ExtraBuffType"]:
        #     conf["ebt"] = res["_ExtraBuffType"]

    RATE_TO_MOD = {
        "_RateHP": ("hp", "buff"),
        "_RateAttack": ("att", "buff"),
        "_RateDefense": ("def", "buff"),
        "_RateDefenseB": ("defb", "buff"),
        "_RateCritical": ("crit", "buff"),
        "_RateSkill": ("s", "buff"),
        "_RateBurst": ("fs", "buff"),
        "_RateRecovery": ("rcv", "buff"),
        "_RateRecoveryDp": ("dph", "buff"),
        "_RateRecoveryUtp": ("utph", "buff"),
        "_RateAttackSpeed": ("aspd", "buff"),
        "_RateChargeSpeed": ("cspd", "buff"),
        "_RateBurstSpeed": ("fspd", "buff"),
        "_MoveSpeedRate": ("mspd", "buff"),  # imba
        "_MoveSpeedRateB": ("mspdb", "buff"),  # very imba
        "_RateFire": ("res_flame", "buff"),
        "_RateWater": ("res_water", "buff"),
        "_RateWind": ("res_wind", "buff"),
        "_RateLight": ("res_light", "buff"),
        "_RateDark": ("res_shadow", "buff"),
        "_EnhancedFire2": ("dmg_flame", "buff"),
        "_EnhancedWater2": ("dmg_water", "buff"),
        "_EnhancedWind2": ("dmg_wind", "buff"),
        "_EnhancedLight2": ("dmg_light", "buff"),
        "_EnhancedDark2": ("dmg_shadow", "buff"),
        "_EnhancedNoElement": ("dmg_nullele", "buff"),
        "_EnhancedDisadvantagedElement": ("dmg_weakele", "buff"),
        # skipping the _Rate<tribe> stuff since no one uses it
        "_RateDamageCut": ("res", "buff"),
        "_RateDamageCut2": ("res", "buff2"),
        "_RateDamageCutB": ("res", "buffB"),
        "_RateGetHpRecovery": ("getrcv", "buff"),
        "_RateArmored": ("kbres", "buff"),
        "_EnhancedCritical": ("critdmg", "buff"),
    }
    RATE_TO_AFFKEY = {
        "_RatePoison": "poison",
        "_RateBurn": "burn",
        "_RateFreeze": "freeze",
        "_RateParalysis": "paralysis",
        "_RateDarkness": "blind",
        "_RateSwoon": "stun",
        "_RateCurse": "curse",
        "_RateSlowMove": "slowmove",
        "_RateSleep": "sleep",
        "_RateFrostbite": "frostbite",
        "_RateFlashheat": "flashburn",
        "_RateCrashWind": "stormlash",
        "_RateDarkAbs": "shadowblight",
        "_RateDestroyFire": "scorchrend",
    }

    def _process_values(self, conf, res):
        # _RemoveAciton: maybe this disables ur fs?
        # unused: _TargetAction/_ConditionAbs/_Enhanced<ele>
        mods = []
        maybe_debuff = set()
        maybe_buff = set()

        def _check_debuff(key, value):
            if value > 0:
                maybe_buff.add(key)
            elif value < 0:
                maybe_debuff.add(key)

        try:
            aff = AFFLICTION_TYPES[res["_Type"]].lower()
            conf["aff"] = aff
        except KeyError:
            aff = None
        if res["_RemoveConditionId"]:
            conf["remove"] = str(res["_RemoveConditionId"])
        if res["_EfficacyType"] == 100:
            conf["dispel"] = "buff"
        # elif res["_EfficacyType"] == 97:
        #     conf["dispel"] = "buff"
        elif res["_EfficacyType"] == 98:
            conf["dispel"] = "debuff"
        elif res["_EfficacyType"] == 99:
            conf["dispel"] = "actcond"
        elif res["_EfficacyType"] == 1:
            conf["relief"] = 1
        if duration := res["_DurationSec"]:
            if res["_MinDurationSec"]:
                duration = fr((duration + res["_MinDurationSec"]) / 2)
            conf["duration"] = duration
            if res["_DurationTimeScale"]:
                conf["duration_scale"] = res["_DurationTimeScale"]
        elif res["_DurationNum"]:
            conf["count"] = res["_DurationNum"]
            if res["_MaxDurationNum"]:
                conf["maxcount"] = res["_MaxDurationNum"]
                conf["addcount"] = res["_IsAddDurationNum"]
        if res["_CoolDownTimeSec"]:
            conf["cd"] = res["_CoolDownTimeSec"]
        # general slip damage stuff
        # will leave these values at negative
        slip = {}
        for func, slipkey in (("fixed", "_SlipDamageFixed"), ("percent", "_SlipDamageRatio"), ("mod", "_SlipDamagePower"), ("heal", "_RegenePower")):
            if res[slipkey]:
                slip["value"] = [func, fr(res[slipkey])]
                break
        if slip:
            if res["_ValidSlipHp"]:
                if res["_SlipDamageGroup"] == 0:
                    # bleed
                    slip["kind"] = "bleed"
                else:
                    # corrosion
                    slip["add"] = res["_RateIncreaseByTime"]
                    slip["addiv"] = fr(res["_RateIncreaseDuration"])
                    slip["threshold"] = res["_RequiredRecoverHp"]
                    slip["kind"] = "corrosion"
                    maybe_debuff.add("_ValidSlipHp")
            else:
                if res["_ValidRegeneHP"]:
                    slip["kind"] = "hp"
                elif res["_ValidRegeneSP"]:
                    slip["kind"] = "sp"
                elif res["_AutoRegeneS1"]:
                    slip["kind"] = "sp"
                    slip["target"] = "s1"
                elif res["_UniqueRegeneSp01"]:
                    slip["kind"] = "sp"
                    slip["target"] = "s2"
                elif res["_AutoRegeneSW"]:
                    slip["kind"] = "sp"
                    slip["target"] = "s3"
                elif res["_ValidRegeneDP"]:
                    slip["kind"] = "dp"
            if "kind" in slip and slip["kind"] not in ("bleed",):
                if slip["value"][1] > 0:
                    maybe_debuff.add(slip["kind"])
                elif slip["value"][1] < 0:
                    maybe_buff.add(slip["kind"])
            if res["_SlipDamageIntervalSec"]:
                slip["iv"] = fr(res["_SlipDamageIntervalSec"])
            conf["slip"] = slip

        if res["_EventProbability"] and aff == "blind":
            conf[aff] = res["_EventProbability"]
        if res["_TargetElemental"]:
            conf["ele"] = ele_bitmap(res["_TargetElemental"])
        if res["_ConditionDebuff"] == 16:
            conf["ifbleed"] = 1

        # generic buffs
        for key, modargs in ActCondConf.RATE_TO_MOD.items():
            if res[key]:
                mods.append((fr(res[key]), *modargs))
                _check_debuff(key, res[key])

        if res["_RateRecoverySp"]:
            if n := res["_RateRecoverySpExceptTargetSkill"]:
                for i in range(0, 4):
                    if not (n >> i):
                        mods.append((fr(res["_RateRecoverySp"]), f"sph_s{i+1}", "buff"))
            else:
                mods.append((fr(res["_RateRecoverySp"]), "sph", "buff"))
            _check_debuff("_RateRecoverySp", res["_RateRecoverySp"])

        for key, aff in ActCondConf.RATE_TO_AFFKEY.items():
            if res[key]:
                mods.append((fr(res[key]), f"affres_{aff}", "buff"))
                _check_debuff(key, res[key])
            killer_key = f"{key}Killer"
            if killer := res[killer_key]:
                mods.append((fr(killer), f"killer_{aff}", "buff"))
                _check_debuff(killer_key, res[killer_key])
            edge_key = f"{key}Add"
            if edge := res[edge_key]:
                mods.append((fr(edge), f"edge_{aff}", "buff"))
                _check_debuff(edge_key, res[edge_key])

        if res["_HealInvalid"]:
            mods.append((-1, "getrcv", "buff"))

        if res["_DebuffGrantRate"]:
            mods.append((res["_DebuffGrantRate"], "debuffrate", "buff"))
        if res["_DamageCoefficient"] and aff == "bog":
            # there is also _EventCoefficient presumably for movement speed
            conf[aff] = res["_DamageCoefficient"]

        if mods:
            conf["icon"] = "-".join(mods[0][1:])
            conf["mods"] = mods

        if res["_TensionUpInvalid"]:
            conf["no_energy"] = res["_TensionUpInvalid"]
            maybe_debuff.add("_TensionUpInvalid")

        shield = {}
        if res["_RateDamageShield"]:
            shield[1] = fr(res["_RateDamageShield"])
        if res["_RateDamageShield2"]:
            shield[2] = fr(res["_RateDamageShield2"])
        if res["_RateDamageShield3"]:
            shield[3] = fr(res["_RateDamageShield3"])
        if shield:
            conf["shield"] = shield

        if res["_RateSacrificeShield"]:
            # dunno what _SacrificeShieldType imply
            conf["lifeshield"] = res["_RateSacrificeShield"]

        if res["_CurseOfEmptinessInvalid"]:
            conf["coei"] = res["_CurseOfEmptinessInvalid"]

        if res["_GrantSkill"]:
            action_grant = self.index["ActionGrant"].get(res["_GrantSkill"], full_query=False)
            target = AbilityTargetAction(action_grant["_TargetAction"])
            ACTCOND_CONF.get(action_grant["_GrantCondition"])
            conf["actgrant"] = [action_grant["_GrantCondition"], f"-t:{AbilityConf.TARGET_ACT[target]}"]

        if res["_DamageLink"]:
            conf["damagelink"] = convert_hitattr(self.index["PlayerActionHitAttribute"].get(res["_DamageLink"]), DUMMY_PART)

        if res["_AutoAvoid"]:
            conf["avoid"] = res["_AutoAvoid"]

        alt = {}
        ekey = None
        if res["_EnhancedBurstAttack"]:
            alt["fs"] = f"b{res['_Id']}"
            if self.meta is not None:
                burst_id = res["_EnhancedBurstAttack"]
                if not burst_id in self.meta.enhanced_fs:
                    if ekey is None:
                        ekey = self.meta.get_enhanced_key("fs")
                    self.meta.enhanced_fs[burst_id] = (ekey, self.index["PlayerAction"].get(burst_id))
                    alt["fs"] = ekey
                else:
                    alt["fs"] = self.meta.enhanced_fs[burst_id][0]

        for sn, skey in (("s1", "_EnhancedSkill1"), ("s2", "_EnhancedSkill2"), ("s3", "_EnhancedSkillWeapon")):
            if not res[skey]:
                continue
            alt[sn] = f"b{res['_Id']}"
            if self.meta is not None:
                esid = res[skey]
                if esid not in self.meta.chara_skills and esid not in self.meta.all_chara_skills:
                    if ekey is None:
                        ekey = self.meta.get_enhanced_key(sn)
                    self.meta.chara_skills[esid] = SDat(esid, sn, ekey)
                    alt[sn] = ekey
                else:
                    try:
                        sdat = self.meta.chara_skills[esid]
                    except KeyError:
                        sdat = self.meta.all_chara_skills[esid]
                    alt[sn] = sdat.group or "default"

        if res["_TransSkill"] and self.meta.trans_skill:
            # conf["phase_up"] = int(res["_TransSkill"])
            base, group = self.meta.trans_skill
            alt[base] = group

        if res["_ComboShift"]:
            alt["x"] = "enhanced"
            self.meta.combo_shift = "enhanced"

        if alt:
            conf["alt"] = alt

        if res["_Tension"]:
            conf["energy"] = res["_Tension"]
        if res["_Inspiration"]:
            conf["inspiration"] = res["_Inspiration"]

        if res["_RateHpDrain"]:
            conf["drain"] = res["_RateHpDrain"]

        if res["_HpConsumptionRate"]:
            conf["selfdamage"] = res["_HpConsumptionRate"]

        if res["_AdditionAttack"]:
            addattack = self.index["PlayerActionHitAttribute"].get(res["_AdditionAttack"], full_query=False)
            conf["echo"] = addattack["_DamageAdjustment"]

        if res["_LevelUpId"]:
            conf["-lv"] = res["_LevelUpId"]

        if res["_LevelDownId"]:
            conf["+lv"] = res["_LevelDownId"]

        if res["_ExcludeFromBuffExtension"]:
            conf["nobufftime"] = 1

        if res["_RemoveTrigger"]:
            conf["triggerbomb"] = 1
            maybe_buff.add(1)

        if maybe_debuff and not maybe_buff:
            conf["debuff"] = 1

    def process_result(self, res):
        actcond_id = res["_Id"]
        if actcond_id not in self.all_actcond_conf:
            conf = {}
            self.all_actcond_conf[actcond_id] = conf
            self._process_values(conf, res)
            self._process_metadata(conf, res)
            for k, v in conf.items():
                if isinstance(v, float):
                    conf[k] = fr(v)
        self._curr_actcond_conf[actcond_id] = self.all_actcond_conf[actcond_id]
        return self.all_actcond_conf[actcond_id]
        # if retconf:
        #     return conf
        # else:
        #     return super().process_result(res)

    def export_all_to_folder(self, out_dir="./out", ext=".json"):
        check_target_path(out_dir)
        output = os.path.join(out_dir, f"actcond{ext}")
        if self.all_actcond_conf:
            print("found", len(self.all_actcond_conf), "actconds")
            with open(output, "w", newline="", encoding="utf-8") as fp:
                fmt_conf(self.all_actcond_conf, f=fp, lim=1)
        else:
            all_res = self.get_all()
            outdata = {}
            not_parsed = []
            for res in tqdm(all_res, desc="actcond"):
                if conf := self.process_result(res):
                    outdata[str(res["_Id"])] = conf
                else:
                    not_parsed.append(f'[{res["_Id"]}] {res["_Text"]}'.strip())
            with open(output, "w", newline="", encoding="utf-8") as fp:
                fmt_conf(outdata, f=fp, lim=1)


# my sadness very big
ACTCOND_CONF = None
