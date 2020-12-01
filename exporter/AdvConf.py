import sys
import os
import pathlib
import json
import re
import itertools
from collections import defaultdict
from unidecode import unidecode
from tqdm import tqdm
from pprint import pprint, pformat
import argparse

from loader.Database import DBViewIndex, DBView, check_target_path
from exporter.Shared import ActionParts, PlayerAction, AbilityData
from exporter.Adventurers import CharaData, CharaUniqueCombo
from exporter.Dragons import DragonData
from exporter.Weapons import WeaponType, WeaponBody
from exporter.Wyrmprints import AbilityCrest, UnionAbility
from exporter.Mappings import WEAPON_TYPES, ELEMENTS, CLASS_TYPES, AFFLICTION_TYPES

ONCE_PER_ACT = ('sp', 'dp', 'utp', 'buff', 'afflic', 'bleed', 'extra', 'dispel')
DODGE_ACTIONS = {6, 40}
DEFAULT_AFF_DURATION = {
    'poison': 15,
    'burn': 12,
    'paralysis': 13,
    'frostbite': 21,
    'flashburn': 21,
    'blind': 8,
    'bog': 8,
    'freeze': (3, 6),
    'stun': (6, 7),
    'sleep': (6, 7),
    'shadowblight': 21,
    'stormlash': 21,
    'scorchrend': 21
}
DEFAULT_AFF_IV = {
    'poison': 2.9,
    'burn': 3.9,
    'paralysis': 3.9,
    'frostbite': 2.9,
    'flashburn': 2.9,
    'shadowblight': 2.9,
    'stormlash': 2.9,
    'scorchrend': 2.9
}
DISPEL = 100

def snakey(name):
    return re.sub(r'[^0-9a-zA-Z ]', '', unidecode(name.replace('&', 'and')).strip()).replace(' ', '_')

def ele_bitmap(n):
    seq = 1
    while not n & 1 and n > 0:
        n = n >> 1
        seq += 1
    return ELEMENTS[seq]

def confsort(a):
    k, v = a
    if k[0] == 'x':
        try:
            return 'x'+k.split('_')[1]
        except IndexError:
            return k
    return k

INDENT = '    '
def fmt_conf(data, k=None, depth=0, f=sys.stdout, lim=2):
    if depth >= lim:
        if k == 'attr':
            r_str_lst = []
            end = len(data) - 1
            for idx, d in enumerate(data):
                if isinstance(d, int):
                    r_str_lst.append(' '+str(d))
                elif idx > 0:
                    r_str_lst.append('\n'+INDENT*(depth+1)+json.dumps(d))
                else:
                    r_str_lst.append(json.dumps(d))
            return '[\n' + INDENT*(depth+1) + (',').join(r_str_lst) + '\n' + INDENT*depth + ']' 
        return json.dumps(data)
    if not isinstance(data, dict):
        f.write(json.dumps(data))
    else:
        f.write('{\n')
        # f.write(INDENT*depth)
        end = len(data) - 1
        if depth == 0:
            items = enumerate(sorted(data.items(), key=confsort))
        else:
            items = enumerate(data.items())
        for idx, kv in items:
            k, v = kv
            f.write(INDENT*(depth+1))
            f.write('"')
            f.write(k)
            f.write('": ')
            res = fmt_conf(v, k, depth+1, f, lim)
            if res is not None:
                f.write(res)
            if idx < end:
                f.write(',\n')
            else:
                f.write('\n')
        f.write(INDENT*depth)
        f.write('}')

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
                need_copy = True
            except KeyError:
                continue
    return attr, need_copy

def convert_all_hitattr(action, pattern=None, meta=None, skill=None):
    actparts = action['_Parts']
    clear_once_per_action = action.get('_OnHitExecType') == 1
    hitattrs = []
    once_per_action = set()
    for part in actparts:
        if clear_once_per_action:
            once_per_action.clear()
        part_hitattrs = []
        for label in ActionParts.HIT_LABELS:
            if (hitattr_lst := part.get(label)):
                if len(hitattr_lst) == 1:
                    hitattr_lst = hitattr_lst[0]
                if isinstance(hitattr_lst, dict):
                    if (attr := convert_hitattr(hitattr_lst, part, action, once_per_action, meta=meta, skill=skill)):
                        part_hitattrs.append(attr)
                elif isinstance(hitattr_lst, list):
                    for hitattr in hitattr_lst:
                        if (not pattern or pattern.match(hitattr['_Id'])) and \
                            (attr := convert_hitattr(hitattr, part, action, once_per_action, meta=meta, skill=skill)):
                            part_hitattrs.append(attr)
                            if not pattern:
                                break
        if not part_hitattrs:
            continue
        is_msl = True
        if (blt := part.get('_bulletNum', 0)) > 1 and not 'extra' in part_hitattrs[-1]:
            last_copy, need_copy = clean_hitattr(part_hitattrs[-1].copy(), once_per_action)
            if need_copy:
                part_hitattrs.append(last_copy)
                part_hitattrs.append(blt-1)
            else:
                part_hitattrs.append(blt)
        gen, delay = None, None
        if (gen := part.get('_generateNum')):
            delay = part.get('_generateDelay')
            ref_attrs = part_hitattrs
        elif (abd := part.get('_abDuration', 0)) > (abi := part.get('_abHitInterval', 0)):
            gen = int(abd/abi)
            delay = abi
            idx = -1
            while isinstance(part_hitattrs[idx], int):
                idx -= 1
            ref_attrs = [part_hitattrs[idx]]
        elif (bci := part.get('_collisionHitInterval', 0)) and ((bld := part.get('_bulletDuration', 0)) > bci or (bld := part.get('_duration', 0)) > bci):
                gen = int(bld/bci) + 1
                delay = bci
                ref_attrs = [part_hitattrs[0]]
            # if adv is not None:
            #     print(adv.name)
        elif part.get('_loopFlag'):
            loopnum = part.get('_loopNum', 0)
            loopsec = part.get('_loopSec')
            delay = part.get('_seconds') + (part.get('_loopFrame', 0) / 60)
            if (loopsec := part.get('_loopSec')):
                gen = max(loopnum, int(loopsec // delay))
            else:
                gen = loopnum
            gen += 1
            ref_attrs = [part_hitattrs[0]] if len(part_hitattrs) == 1 else [part_hitattrs[1]]
            is_msl = False
        gen_attrs = []
        timekey = 'msl' if is_msl else 'iv'
        if gen and delay:
            for gseq in range(1, gen):
                for attr in ref_attrs:
                    gattr, _ = clean_hitattr(attr.copy(), once_per_action)
                    if not gattr:
                        continue
                    gattr[timekey] = fr(attr.get(timekey, 0)+delay*gseq)
                    gen_attrs.append(gattr)
        if part.get('_generateNumDependOnBuffCount'):
            # possible that this can be used with _generateNum
            buffcond = part['_buffCountConditionId']
            buffname = snakey(buffcond['_Text']).lower()
            gen = buffcond['_MaxDuplicatedCount']
            for idx, delay in enumerate(map(float, json.loads(part['_bulletDelayTime']))):
                if idx >= gen:
                    break
                delay = float(delay)
                for attr in part_hitattrs:
                    if idx == 0:
                        attr[timekey] = fr(attr.get(timekey, 0)+delay)
                        attr['cond'] = ['var>=', [buffname, idx+1]]
                    else:
                        gattr, _ = clean_hitattr(attr.copy(), once_per_action)
                        if not gattr:
                            continue
                        gattr[timekey] = fr(attr.get(timekey, 0)+delay)
                        gattr['cond'] = ['var>=', [buffname, idx+1]]
                        gen_attrs.append(gattr)
        part_hitattrs.extend(gen_attrs)
        hitattrs.extend(part_hitattrs)
    once_per_action = set()
    return hitattrs

def convert_hitattr(hitattr, part, action, once_per_action, meta=None, skill=None):
    attr = {}
    target = hitattr.get('_TargetGroup')
    if target != 5 and hitattr.get('_DamageAdjustment'):
        attr['dmg'] = fr(hitattr.get('_DamageAdjustment'))
        killers = []
        for ks in ('_KillerState1', '_KillerState2', '_KillerState3'):
            if hitattr.get(ks):
                killers.append(hitattr.get(ks).lower())
        if len(killers) > 0:
            attr['killer'] = [fr(hitattr['_KillerStateDamageRate']-1), killers]
        if (crisis := hitattr.get('_CrisisLimitRate')):
            attr['crisis'] = fr(crisis-1)
        if (bufc := hitattr.get('_DamageUpRateByBuffCount')):
            attr['bufc'] = fr(bufc)
    if 'sp' not in once_per_action:
        if (sp := hitattr.get('_AdditionRecoverySp')):
            attr['sp'] = fr(sp)
            once_per_action.add('sp')
        elif (sp_p := hitattr.get('_RecoverySpRatio')):
            attr['sp'] = [fr(sp_p), '%']
            if (sp_i := hitattr.get('_RecoverySpSkillIndex')) or (sp_i := hitattr.get('_RecoverySpSkillIndex2')):
                attr['sp'].append(f's{sp_i}')
            once_per_action.add('sp')
    if 'dp' not in once_per_action and (dp := hitattr.get('_AdditionRecoveryDpLv1')):
        attr['dp'] = dp
        once_per_action.add('dp')
    if 'utp' not in once_per_action and ((utp := hitattr.get('_AddUtp')) or (utp := hitattr.get('_AdditionRecoveryUtp'))):
        attr['utp'] = utp
        once_per_action.add('utp')
    if (hp := hitattr.get('_HpDrainLimitRate')):
        attr['hp'] = fr(hp*100)
    if (cp := hitattr.get('_RecoveryCP')):
        attr['cp'] = cp
    # if hitattr.get('_RecoveryValue'):
    #     attr['heal'] = fr(hitattr.get('_RecoveryValue'))
    if part.get('commandType') == 'FIRE_STOCK_BULLET' and (stock := action.get('_MaxStockBullet', 0)) > 1:
        attr['extra'] = stock
    if (bc := attr.get('_DamageUpRateByBuffCount')):
        attr['bufc'] = bc
    if 0 < (attenuation := part.get('_attenuationRate', 0)) < 1:
        attr['fade'] = fr(attenuation)

    # attr_tag = None
    if (actcond := hitattr.get('_ActionCondition1')) and actcond['_Id'] not in once_per_action:
        once_per_action.add(actcond['_Id'])
        # attr_tag = actcond['_Id']
        # if (remove := actcond.get('_RemoveConditionId')):
        #     attr['del'] = remove
        if actcond.get('_DamageLink'):
            return convert_hitattr(actcond['_DamageLink'], part, action, once_per_action, meta=meta, skill=skill)
        if actcond.get('_EfficacyType') == DISPEL and (rate := actcond.get('_Rate', 0)):
            attr['dispel'] = rate
        else:
            alt_buffs = []
            if meta and skill:
                for ehs, s in AdvConf.ENHANCED_SKILL.items():
                    if (esk := actcond.get(ehs)):
                        if isinstance(esk, int) or esk.get('_Id') in meta.all_chara_skills:
                            meta.chara_skill_loop.add(skill['_Id'])
                        else:
                            eid = next(meta.eskill_counter)
                            group = 'enhanced' if eid == 1 else f'enhanced{eid}'
                            meta.chara_skills[esk.get('_Id')] = (f's{s}_{group}', s, esk, skill['_Id'])
                            alt_buffs.append(['sAlt', group, f's{s}'])
                if isinstance((eba := actcond.get('_EnhancedBurstAttack')), dict):
                    eid = next(meta.efs_counter)
                    group = 'enhanced' if eid == 1 else f'enhanced{eid}'
                    meta.enhanced_fs.append((group, eba, eba.get('_BurstMarkerId')))
                    alt_buffs.append(['fsAlt', group])

            if target == 3 and (afflic := actcond.get('_Type')):
                affname = afflic.lower()
                attr['afflic'] = [affname, actcond['_Rate']]
                if (dot := actcond.get('_SlipDamagePower')):
                    attr['afflic'].append(fr(dot))
                duration = fr(actcond.get('_DurationSec'))
                min_duration = fr(actcond.get('_MinDurationSec'))
                # duration = fr((duration + actcond.get('_MinDurationSec', duration)) / 2)
                if min_duration:
                    if DEFAULT_AFF_DURATION[affname] != (min_duration, duration):
                        attr['afflic'].append(duration)
                        attr['afflic'].append(min_duration)
                elif DEFAULT_AFF_DURATION[affname] != duration:
                    attr['afflic'].append(duration)
                    duration = None
                if (iv := actcond.get('_SlipDamageIntervalSec')):
                    iv = fr(iv)
                    if DEFAULT_AFF_IV[affname] != iv:
                        if duration:
                            attr['afflic'].append(duration)
                        attr['afflic'].append(iv)
            elif 'Bleeding' == actcond.get('_Text'):
                attr['bleed'] = [actcond['_Rate'], fr(actcond['_SlipDamagePower'])]
            else:
                buffs = []
                for tsn, btype in AdvConf.TENSION_KEY.items():
                    if (v := actcond.get(tsn)):
                        if target in (2, 6):
                            if part.get('_collisionParams_01', 0) > 0:
                                buffs.append([btype, v, 'nearby'])
                            else:
                                buffs.append([btype, v, 'team'])
                        else:
                            buffs.append([btype, v])
                if not buffs:
                    if part.get('_lifetime'):
                        duration = fr(part.get('_lifetime'))
                        btype = 'zone'
                    elif actcond.get('_DurationNum') and not actcond.get('_DurationSec'):
                        duration = actcond.get('_DurationNum')
                        btype = 'next'
                    else:
                        duration = actcond.get('_DurationSec', -1)
                        duration = fr(duration)
                        if target in (2, 6):
                            if part.get('_collisionParams_01', 0) > 0:
                                btype = 'nearby'
                            else:
                                btype = 'team'
                        else:
                            btype = 'self'
                    for b in alt_buffs:
                        if btype == 'next' and b[0] in ('fsAlt', 'sAlt'):
                            b.extend((-1, duration))
                        elif duration > -1:
                            b.append(duration)
                        buffs.append(b)
                    if target == 3:
                        for k, mod in AdvConf.DEBUFFARG_KEY.items():
                            if (value := actcond.get(k)):
                                buffs.append(['debuff', fr(value), duration, actcond.get('_Rate')/100, mod])
                        for k, aff in AdvConf.AFFRES_KEY.items():
                            if (value := actcond.get(k)):
                                buffs.append(['affres', fr(value), duration, aff])
                    else:
                        for k, mod in AdvConf.BUFFARG_KEY.items():
                            if (value := actcond.get(k)):
                                if (bele := actcond.get('_TargetElemental')) and btype != 'self':
                                    buffs.append(['ele', fr(value), duration, *mod, ele_bitmap(bele).lower()])
                                elif k == '_SlipDamageRatio':
                                    buffs.append([btype, -fr(value), duration, *mod])
                                else:
                                    buffs.append([btype, fr(value), duration, *mod])
                if buffs:
                    if len(buffs) == 1:
                        buffs = buffs[0]
                    # if any(actcond.get(k) for k in AdvConf.OVERWRITE):
                    #     buffs.append('-refresh')
                    if actcond.get('_OverwriteGroupId'):
                        buffs.append(f'-overwrite_{actcond.get("_OverwriteGroupId")}')
                    elif actcond.get('_Overwrite'):
                        buffs.append('-refresh')
                    attr['buff'] = buffs
    if attr:
        iv = fr(part['_seconds'])
        if iv > 0:
            attr['iv'] = iv
        # if 'BULLET' in part['commandType']
        if (delay := part.get('_delayTime', 0)):
            attr['msl'] = fr(delay)
        # if attr_tag:
        #     attr['tag'] = attr_tag
        return attr
    else:
        return None


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
        if part['commandType'] == 'SEND_SIGNAL':
            actid = part.get('_actionId', 0)
            if not (is_dragon and actid % 100 in (20, 21)) and not actid in DODGE_ACTIONS:
                signals[actid] = -10
                if part.get('_motionEnd'):
                    signal_end.add(actid)
        elif ('HIT' in part['commandType'] or 'BULLET' in part['commandType']) and s is None:
            s = fr(part['_seconds'])
        elif part['commandType'] == 'ACTIVE_CANCEL':
            # print(part)
            recovery = part['_seconds']
            actid = part.get('_actionId')
            if seq and actid in signals:
                signals[actid] = recovery
            if part.get('_motionEnd') or actid in signal_end:
                motion_end = recovery
            if actid:
                followed_by.add((recovery, actid))
            # else:
            #     recovery = max(timestop, recovery)
        elif part['commandType'] == 'TIMESTOP':
            # timestop = part.get('_seconds', 0) + part.get('_duration', 0)
            ts_second = part.get('_seconds', 0)
            ts_delay = part.get('_duration', 0)
            timestop = ts_second + ts_delay
            # if is_dragon:
            #     found_hit = False
            #     for npart in parts[idx+1:]:
            #         if npart['_seconds'] > ts_second:
            #             # found_hit = found_hit or ('HIT' in npart['commandType'] or 'BULLET' in npart['commandType'])
            #             if 'HIT' in npart['commandType'] or 'BULLET' in npart['commandType']:
            #                 npart['_seconds'] += ts_delay
        elif is_dragon and part['commandType'] == 'TIMECURVE' and not part.get('_isNormalizeCurve'):
            timecurve = part.get('_duration')
        # if part['commandType'] == 'PARTS_MOTION' and part.get('_animation'):
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
        for part in sorted(parts, key=lambda p: -p['_seq']):
            if part['commandType'] == 'ACTIVE_CANCEL' and part['_seconds'] > 0:
                r = part['_seconds']
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
    if r is None or r < s:
        if motion_end:
            r = motion_end
        else:
            for part in reversed(parts):
                if part['commandType'] == 'ACTIVE_CANCEL':
                    r = part['_seconds']
                    break
        if r is not None:
            r = max(timestop, r)
    r = fr(r)
    return s, r, followed_by


def hit_attr_adj(action, s, conf, pattern=None, skip_nohitattr=True):
    if (hitattrs := convert_all_hitattr(action, pattern=pattern)):
        try:
            conf['recovery'] = fr(conf['recovery'] - s)
        except TypeError:
            conf['recovery'] = None
        for attr in hitattrs:
            if not isinstance(attr, int) and 'iv' in attr:
                attr['iv'] = fr(attr['iv'] - s)
                if attr['iv'] == 0:
                    del attr['iv']
        conf['attr'] = hitattrs
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
            act_name = 'dodge'
        elif act % 10 == 5:
            act_name = 'fs'
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
    s, r, followed_by = hit_sr(xn['_Parts'], seq=aid, xlen=xlen, is_dragon=is_dragon)
    if s is None:
        pprint(xn)
    xconf = {
        'startup': s,
        'recovery': r
    }
    xconf = hit_attr_adj(xn, s, xconf, skip_nohitattr=False, pattern=pattern)
    
    if convert_follow:
        xconf['interrupt'], xconf['cancel'] = convert_following_actions(s, followed_by, ('s',))

    return xconf


def convert_fs(burst, marker=None, cancel=None):
    startup, recovery, followed_by = hit_sr(burst['_Parts'])
    fsconf = {}
    if not isinstance(marker, dict):
        fsconf['fs'] = hit_attr_adj(burst, startup, {'startup': startup, 'recovery': recovery}, re.compile(r'.*_LV02$'))
    else:
        mpart = marker['_Parts'][0]
        charge = mpart.get('_chargeSec', 0.5)
        fsconf['fs'] = {'charge': fr(charge), 'startup': startup, 'recovery': recovery}
        if (clv := mpart.get('_chargeLvSec')):
            clv = list(map(float, [charge]+json.loads(clv)))
            totalc = 0
            for idx, c in enumerate(clv):
                if idx == 0:
                    clv_attr = hit_attr_adj(burst, startup, fsconf[f'fs'].copy(), re.compile(f'.*_LV02$'))
                else:
                    clv_attr = hit_attr_adj(burst, startup, fsconf[f'fs'].copy(), re.compile(f'.*_LV02_CHLV0{idx+1}$'))
                totalc += c
                if clv_attr:
                    fsn = f'fs{idx+1}'
                    fsconf[fsn] = clv_attr
                    fsconf[fsn]['charge'] = fr(totalc)
                    fsconf[fsn]['interrupt'], fsconf[fsn]['cancel'] = convert_following_actions(startup, followed_by, ('s',))
            if 'fs2' in fsconf and 'attr' not in fsconf['fs']:
                del fsconf['fs']
            elif 'fs1' in fsconf:
                fsconf['fs'] = fsconf['fs1']
                del fsconf['fs1']
        else:
            fsconf['fs'] = hit_attr_adj(burst, startup, fsconf['fs'], re.compile(r'.*H0\d_LV02$'))
            fsconf['fs']['interrupt'], fsconf['fs']['cancel'] = convert_following_actions(startup, followed_by, ('s',))
    if cancel is not None:
        fsconf['fsf'] = {
            'charge': fr(0.1+cancel['_Parts'][0]['_duration']),
            'startup': 0.0,
            'recovery': 0.0,
        }
        fsconf['fsf']['interrupt'], fsconf['fsf']['cancel'] = convert_following_actions(startup, followed_by, ('s',))

    return fsconf


class BaseConf(WeaponType):
    LABEL_MAP = {
        'AXE': 'axe',
        'BOW': 'bow',
        'CAN': 'staff',
        'DAG': 'dagger',
        'KAT': 'blade',
        'LAN': 'lance',
        'ROD': 'wand',
        'SWD': 'sword',
        'GUN': 'gun'
    }
    GUN_MODES = (40, 41, 42)
    def process_result(self, res, exclude_falsy=True, full_query=True):
        conf = {'lv2':{}}
        if res['_Label'] != 'GUN':
            fs_id = res['_BurstPhase1']
            res = super().process_result(res, exclude_falsy=True, full_query=True)
            # fs_delay = {}
            fsconf = convert_fs(res['_BurstPhase1'], res['_ChargeMarker'], res['_ChargeCancel'])
            startup = fsconf['fs']['startup']
            # for x, delay in fs_delay.items():
            #     fsconf['fs'][x] = {'startup': fr(startup+delay)}
            conf.update(fsconf)
            for n in range(1, 6):
                try:
                    xn = res[f'_DefaultSkill0{n}']
                except KeyError:
                    break
                conf[f'x{n}'] = convert_x(xn['_Id'], xn)
                # for part in xn['_Parts']:
                #     if part['commandType'] == 'ACTIVE_CANCEL' and part.get('_actionId') == fs_id and part.get('_seconds'):
                #         fs_delay[f'x{n}'] = part.get('_seconds')
                if (hitattrs := convert_all_hitattr(xn, re.compile(r'.*H0\d_LV02$'))):
                    for attr in hitattrs:
                        attr['iv'] = fr(attr['iv'] - conf[f'x{n}']['startup'])
                        if attr['iv'] == 0:
                            del attr['iv']
                    conf['lv2'][f'x{n}'] = {'attr': hitattrs}
        else:
            # gun stuff
            for mode in BaseConf.GUN_MODES:
                mode = self.index['CharaModeData'].get(mode, exclude_falsy=exclude_falsy, full_query=True)
                mode_name = f'gun{mode["_GunMode"]}'
                if (burst := mode.get('_BurstAttackId')):
                    marker = burst.get('_BurstMarkerId')
                    if not marker:
                        marker = self.index['PlayerAction'].get(burst['_Id']+4, exclude_falsy=True)
                    for fs, fsc in convert_fs(burst, marker).items():
                        conf[f'{fs}_{mode_name}'] = fsc
                if (xalt := mode.get('_UniqueComboId')):
                    for prefix in ('', 'Ex'):
                        if xalt.get(f'_{prefix}ActionId'):
                            for n, xn in enumerate(xalt[f'_{prefix}ActionId']):
                                n += 1
                                xn_key = f'x{n}_{mode_name}{prefix.lower()}'
                                if xaltconf := convert_x(xn['_Id'], xn, xlen=xalt['_MaxComboNum']):
                                    conf[xn_key] = xaltconf
                                if (hitattrs := convert_all_hitattr(xn, re.compile(r'.*H0\d_LV02$'))):
                                    for attr in hitattrs:
                                        attr['iv'] = fr(attr['iv'] - conf[xn_key]['startup'])
                                        if attr['iv'] == 0:
                                            del attr['iv']
                                    conf['lv2'][xn_key] = {'attr': hitattrs}

        return conf

    @staticmethod
    def outfile_name(res, ext):
        return BaseConf.LABEL_MAP[res['_Label']]+ext

    def export_all_to_folder(self, out_dir='./out', ext='.json'):
        out_dir = os.path.join(out_dir, 'base')
        all_res = self.get_all(exclude_falsy=True)
        check_target_path(out_dir)
        for res in tqdm(all_res, desc=os.path.basename(out_dir)):
            out_name = self.outfile_name(res, ext)
            res = self.process_result(res, exclude_falsy=True)
            output = os.path.join(out_dir, out_name)
            with open(output, 'w', newline='', encoding='utf-8') as fp:
                # json.dump(res, fp, indent=2, ensure_ascii=False)
                fmt_conf(res, f=fp)

def convert_skill_common(skill, lv):
    action = 0
    if lv >= skill.get('_AdvancedSkillLv1', float('inf')):
        action = skill.get('_AdvancedActionId1', 0)
    if isinstance(action, int):
        action = skill.get('_ActionId1')

    startup, recovery = 0.1, None
    actcancel = None
    mstate = None
    timestop = 0
    followed_by = set()
    for part in action['_Parts']:
        if part['commandType'] == 'ACTIVE_CANCEL' and actcancel is None:
            if '_actionId' in part:
                followed_by.add((part['_seconds'], part['_actionId']))
            else:
                actcancel = part['_seconds']
        if part['commandType'] == 'PARTS_MOTION' and mstate is None:
            if (animation := part.get('_animation')):
                if isinstance(animation, list):
                    mstate = sum(a['duration'] for a in animation)
                else:
                    mstate = animation['duration']
            if part.get('_motionState') in AdvConf.GENERIC_BUFF:
                mstate = 1.0
        if part['commandType'] == 'TIMESTOP':
            timestop = part['_seconds'] + part['_duration']
        if actcancel and mstate:
            break
    if actcancel:
        actcancel = max(timestop, actcancel)
    recovery = actcancel or mstate or recovery

    if recovery is None:
        AdvConf.MISSING_ENDLAG.append(skill.get('_Name'))

    sconf = {
        'sp': skill.get(f'_SpLv{lv}', skill.get('_Sp', 0)),
        'startup': startup,
        'recovery': None if not recovery else fr(recovery),
    }

    interrupt, cancel = convert_following_actions(0, followed_by)
    if interrupt:
        sconf['interrupt'] = interrupt
    if cancel:
        sconf['cancel'] = cancel

    if nextaction := action.get('_NextAction'):
        for part in nextaction['_Parts']:
            part['_seconds'] += sconf['recovery'] or 0
        action['_Parts'].extend(nextaction['_Parts'])
        sconf['DEBUG_CHECK_NEXTACT'] = True

    return sconf, action


class SkillProcessHelper:
    def reset_meta(self):
        self.chara_skills = {}
        self.chara_skill_loop = set()
        self.eskill_counter = itertools.count(start=1)
        self.efs_counter = itertools.count(start=1)
        self.all_chara_skills = {}
        self.enhanced_fs = []
        self.ab_alt_buffs = defaultdict(lambda: [])

    def convert_skill(self, k, seq, skill, lv, no_loop=False):
        sconf, action = convert_skill_common(skill, lv)

        if (hitattrs := convert_all_hitattr(action, re.compile(f'.*LV0{lv}$'), meta=None if no_loop else self, skill=skill)):
            sconf['attr'] = hitattrs
        if (not hitattrs or all(['dmg' not in attr for attr in hitattrs if isinstance(attr, dict)])) and skill.get(f'_IsAffectedByTensionLv{lv}'):
            sconf['energizable'] = bool(skill[f'_IsAffectedByTensionLv{lv}'])

        if isinstance((transkills := skill.get('_TransSkill')), dict):
            k = f's{seq}_phase1'
            for idx, ts in enumerate(transkills.items()):
                tsid, tsk = ts
                if tsid not in self.all_chara_skills:
                    self.chara_skills[tsid] = (f's{seq}_phase{idx+1}', seq, tsk, skill.get('_Id'))

        if (ab := skill.get(f'_Ability{lv}')):
            if isinstance(ab, int):
                ab = self.index['AbilityData'].get(ab, exclude_falsy=True)
            for a in (1, 2, 3):
                if ab.get('_AbilityType1') == 44: # alt skill
                    s = int(ab['_TargetAction1'][-1])
                    eid = next(self.eskill_counter)
                    group = 'enhanced' if eid == 1 else f'enhanced{eid}'
                    self.chara_skills[ab[f'_VariousId1a']['_Id']] = (f's{s}_{group}', s, ab[f'_VariousId1a'], skill['_Id'])
        return sconf, k

    def process_skill(self, res, conf, mlvl, all_levels=False):
        # exceptions exist
        while self.chara_skills:
            k, seq, skill, prev_id = next(iter(self.chara_skills.values()))
            self.all_chara_skills[skill.get('_Id')] = (k, seq, skill, prev_id)
            if seq == 99:
                lv = mlvl[res['_EditSkillLevelNum']]
            else:
                lv = mlvl.get(seq, 2)
            cskill, k = self.convert_skill(k, seq, skill, lv)
            conf[k] = cskill
            if all_levels:
                for s_lv in range(1, lv):
                    s_cskill, _ = self.convert_skill(k, seq, skill, s_lv, no_loop=True)
                    conf[k][f'lv{s_lv}'] = s_cskill
            if (ab_alt_buffs := self.ab_alt_buffs.get(seq)):
                if len(ab_alt_buffs) == 1:
                    ab_alt_buffs = [ab_alt_buffs[0], '-refresh']
                else:
                    ab_alt_buffs = [*ab_alt_buffs, '-refresh']
                if 'attr' not in conf[k]:
                    conf[k]['attr'] = []
                conf[k]['attr'].append({'buff': ab_alt_buffs})
            del self.chara_skills[skill.get('_Id')]

        for efs, eba, emk in self.enhanced_fs:
            n = ''
            for fs, fsc in convert_fs(eba, emk).items():
                conf[f'{fs}_{efs}'] = fsc

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


class AdvConf(CharaData, SkillProcessHelper):
    GENERIC_BUFF = ('skill_A', 'skill_B', 'skill_C', 'skill_D', 'skill_006_01')
    BUFFARG_KEY = {
        '_RateAttack': ('att', 'buff'),
        '_RateDefense': ('defense', 'buff'),
        '_RateHP': ('maxhp', 'buff'),
        '_RateCritical': ('crit', 'chance'),
        '_EnhancedCritical': ('crit', 'damage'),
        # '_RegenePower': ('heal', 'buff'),
        '_SlipDamageRatio': ('regen', 'buff'),
        '_RateRecoverySp': ('sp', 'passive'),
        # '_RateHP': ('hp', 'buff')
        '_RateAttackSpeed': ('spd', 'passive'),
        '_RateChargeSpeed': ('cspd', 'passive'),
        '_RateBurst': ('fs', 'buff'),
        '_RateSkill': ('s', 'buff'),
        # '_RateDamageShield': ('shield', 'buff')
    }
    DEBUFFARG_KEY = {
        '_RateDefense': 'def',
        '_RateDefenseB': 'defb',
        '_RateAttack': 'attack'
    }
    AFFRES_KEY = {
        '_RatePoison': 'poison',
        '_RateBurn': 'burn',
        '_RateFreeze': 'freeze',
        '_RateDarkness': 'blind',
        '_RateSwoon': 'stun',
        '_RateSlowMove': 'bog',
        '_RateSleep': 'sleep',
        '_RateFrostbite': 'frostbite',
        '_RateFlashheat': 'flashburn'
    }
    TENSION_KEY = {
        '_Tension': 'energy',
        '_Inspiration': 'inspiration'
    }
    # OVERWRITE = ('_Overwrite', '_OverwriteVoice', '_OverwriteGroupId')
    ENHANCED_SKILL = {
        '_EnhancedSkill1': 1,
        '_EnhancedSkill2': 2,
        '_EnhancedSkillWeapon': 3
    }

    MISSING_ENDLAG = []
    DO_NOT_FIND_LOOP = (
        10350302, # summer norwin
        10650101, # gala sarisse
    )

    def process_result(self, res, exclude_falsy=True, condense=True, all_levels=False):
        self.index['ActionParts'].animation_reference = ('CharacterMotion', int(f'{res["_BaseId"]:06}{res["_VariationId"]:02}'))
        self.reset_meta()

        ab_lst = []
        for i in (1, 2, 3):
            for j in (3, 2, 1):
                if (ab := res.get(f'_Abilities{i}{j}')):
                    ab_lst.append(self.index['AbilityData'].get(ab, full_query=True, exclude_falsy=exclude_falsy))
                    break
        converted, skipped = convert_all_ability(ab_lst)
        res = self.condense_stats(res)
        conf = {
            'c': {
                'name': res.get('_SecondName', res['_Name']),
                'icon': f'{res["_BaseId"]:06}_{res["_VariationId"]:02}_r{res["_Rarity"]:02}',
                'att': res['_MaxAtk'],
                'hp': res['_MaxHp'],
                'ele': ELEMENTS[res['_ElementalType']].lower(),
                'wt': WEAPON_TYPES[res['_WeaponType']].lower(),
                'spiral': res['_MaxLimitBreakCount'] == 5,
                'a': converted,
                # 'skipped': skipped
            }
        }
        # cykagames reeee
        if res['_Id'] == 10750203:
            conf['c']['name'] = 'Forager Cleo'
        if conf['c']['wt'] == 'gun':
            conf['c']['gun'] = []
        self.name = conf['c']['name']

        for ab in ab_lst:
            for i in (1, 2, 3):
                # enhanced s/fs buff
                group = None
                if ab.get(f'_AbilityType{i}') == 14:
                    unique_name = snakey(self.name.lower()).replace('_', '')
                    actcond = ab.get(f'_VariousId{i}a')
                    if not actcond:
                        actcond = ab.get(f'_VariousId{i}str')
                    sid = ab.get('_OnSkill')
                    cd = actcond.get('_CoolDownTimeSec')
                    for ehs, s in AdvConf.ENHANCED_SKILL.items():
                        if (esk := actcond.get(ehs)):
                            eid = next(self.eskill_counter)
                            if group is None:
                                group = unique_name if eid == 1 else f'{unique_name}{eid}'
                            self.chara_skills[esk.get('_Id')] = (f's{s}_{group}', s, esk, None)
                            if sid and not cd:
                                self.ab_alt_buffs[sid].append(['sAlt', group, f's{s}', -1, actcond.get('_DurationNum', 0)])
                    if (eba := actcond.get('_EnhancedBurstAttack')) and isinstance(eba, dict):
                        eid = next(self.efs_counter)
                        group = unique_name if eid == 1 else f'{unique_name}{eid}'
                        self.enhanced_fs.append((group, eba, eba.get('_BurstMarkerId')))
                        if sid and not cd:
                            self.ab_alt_buffs[sid].append(['fsAlt', group])
                    for b in self.ab_alt_buffs[sid]:
                        if dnum := actcond.get('_DurationNum'):
                            b.extend((-1, dnum))
                        elif dtime := actcond.get('_Duration'):
                            b.append(dtime)

        if (burst := res.get('_BurstAttack')):
            burst = self.index['PlayerAction'].get(res['_BurstAttack'], exclude_falsy=exclude_falsy)
            if burst and (marker := burst.get('_BurstMarkerId')):
                conf.update(convert_fs(burst, marker))

        for s in (1, 2):
            skill = self.index['SkillData'].get(res[f'_Skill{s}'], 
                exclude_falsy=exclude_falsy, full_query=True)
            self.chara_skills[res[f'_Skill{s}']] = (f's{s}', s, skill, None)
        if (edit := res.get('_EditSkillId')) and edit not in self.chara_skills:
            skill = self.index['SkillData'].get(res[f'_EditSkillId'], 
                exclude_falsy=exclude_falsy, full_query=True)
            self.chara_skills[res['_EditSkillId']] = (f's99', 99, skill, None)

        for m in range(1, 5):
            if (mode := res.get(f'_ModeId{m}')):
                mode = self.index['CharaModeData'].get(mode, exclude_falsy=exclude_falsy, full_query=True)
                if not mode:
                    continue
                if (gunkind := mode.get('_GunMode')):
                    conf['c']['gun'].append(gunkind)
                    if not any([mode.get(f'_Skill{s}Id') for s in (1, 2)]):
                        continue
                try:
                    mode_name = unidecode(mode['_ActionId']['_Parts'][0]['_actionConditionId']['_Text'].split(' ')[0].lower())
                except:
                    if res.get('_ModeChangeType') == 3:
                        mode_name = 'ddrive'
                    else:
                        mode_name = f'mode{m}'
                for s in (1, 2):
                    if (skill := mode.get(f'_Skill{s}Id')):
                        self.chara_skills[skill.get('_Id')] = (f's{s}_{mode_name}', s, skill, None)
                if (burst := mode.get('_BurstAttackId')):
                    marker = burst.get('_BurstMarkerId')
                    if not marker:
                        marker = self.index['PlayerAction'].get(burst['_Id']+4, exclude_falsy=True)
                    for fs, fsc in convert_fs(burst, marker).items():
                        conf[f'{fs}_{mode_name}'] = fsc
                if (xalt := mode.get('_UniqueComboId')):
                    xalt_pattern = re.compile(r'.*H0\d_LV02$') if conf['c']['spiral'] else None
                    for prefix in ('', 'Ex'):
                        if xalt.get(f'_{prefix}ActionId'):
                            for n, xn in enumerate(xalt[f'_{prefix}ActionId']):
                                n += 1
                                if xaltconf := convert_x(xn['_Id'], xn, xlen=xalt['_MaxComboNum'], pattern=xalt_pattern):
                                    conf[f'x{n}_{mode_name}{prefix.lower()}'] = xaltconf
                                elif xalt_pattern is not None and (xaltconf := convert_x(xn['_Id'], xn, xlen=xalt['_MaxComboNum'])):
                                    conf[f'x{n}_{mode_name}{prefix.lower()}'] = xaltconf
        try:
            conf['c']['gun'] = list(set(conf['c']['gun']))
        except KeyError:
            pass

        # self.abilities = self.last_abilities(res, as_mapping=True)
        # pprint(self.abilities)
        # for k, seq, skill in self.chara_skills.values():

        if (udrg := res.get('_UniqueDragonId')):
            conf['dragonform'] = self.index['DrgConf'].get(udrg, by='_Id')
            del conf['dragonform']['d']

        if conf['c']['spiral']:
            mlvl = {1: 4, 2: 3}
        else:
            mlvl = {1: 3, 2: 2}
        self.process_skill(res, conf, mlvl, all_levels=all_levels)

        return conf

    def get(self, name, all_levels=False):
        res = super().get(name, full_query=False)
        if isinstance(res, list):
            res = res[0]
        return self.process_result(res, all_levels=all_levels)

    @staticmethod
    def outfile_name(conf, ext):
        return snakey(conf['c']['name']) + ext

    def export_all_to_folder(self, out_dir='./out', ext='.json', desc=False):
        all_res = self.get_all(exclude_falsy=True, where='_ElementalType != 99 AND _IsPlayable = 1')
        # ref_dir = os.path.join(out_dir, '..', 'adv')
        if desc:
            desc_out = open(os.path.join(out_dir, 'desc.txt'), 'w')
            out_dir = os.path.join(out_dir, 'advdesc')
        else:
            out_dir = os.path.join(out_dir, 'adv')
        check_target_path(out_dir)
        for res in tqdm(all_res, desc=os.path.basename(out_dir)):
            try:
                outconf = self.process_result(res, exclude_falsy=True, all_levels=desc)
                out_name = self.outfile_name(outconf, ext)
                output = os.path.join(out_dir, out_name)
                # ref = os.path.join(ref_dir, out_name)
                # if os.path.exists(ref):
                #     with open(ref, 'r', newline='', encoding='utf-8') as fp:
                #         refconf = json.load(fp)
                #         try:
                #             outconf['c']['a'] = refconf['c']['a']
                #         except:
                #             outconf['c']['a'] = []
                if desc:
                    desc_out.write(outconf['c']['name'])
                    desc_out.write('\n')
                    desc_out.write(describe_conf(outconf))
                    desc_out.write('\n\n')
                with open(output, 'w', newline='', encoding='utf-8') as fp:
                    # json.dump(res, fp, indent=2, ensure_ascii=False)
                    fmt_conf(outconf, f=fp)
            except Exception as e:
                print(res['_Id'])
                pprint(outconf)
                raise e
        print('Missing endlag for:', AdvConf.MISSING_ENDLAG)
        if desc:
            desc_out.close()


def ab_cond(ab):
    cond = ab.get('_ConditionType')
    condval = ab.get('_ConditionValue')
    ele = ab.get('_ElementalType')
    wep = ab.get('_WeaponType')
    cparts = []
    if ele:
        cparts.append(ele.lower())
    if wep:
        cparts.append(wep.lower())
    if condval:
        condval = int(condval)
    if cond == 'hp geq':
        cparts.append(f'hp{condval}')
    elif cond == 'hp leq':
        cparts.append(f'hp≤{condval}')
    elif cond == 'combo':
        cparts.append(f'hit{condval}')
    if cparts:
        return '_'.join(cparts)


AB_STATS = {
    1: 'hp',
    2: 'a',
    4: 'sp',
    5: 'dh',
    8: 'dt',
    10: 'spd',
    12: 'cspd'
}
def ab_stats(**kwargs):
    if (stat := AB_STATS.get(kwargs.get('var_a'))) and (upval := kwargs.get('upval')):
        res = [stat, upval/100]
        if (condstr := ab_cond(kwargs.get('ab'))):
            res.append(condstr)
        return res

def ab_aff_edge(**kwargs):
    if (a_id := kwargs.get('var_a')):
        return [f'edge_{AFFLICTION_TYPES.get(a_id, a_id).lower()}', kwargs.get('upval')]

def ab_damage(**kwargs):
    if upval := kwargs.get('upval'):
        res = None
        target = kwargs.get('target')
        astr = None
        if target == 'skill':
            astr = 's'
        elif target == 'force strike':
            astr = 'fs'
        if astr:
            res = [astr, upval/100]
        else:
            cond = kwargs.get('ab').get('_ConditionType')
            if cond == 'bleed':
                res = ['bleed', upval/100]
            elif cond == 'overdrive':
                res = ['od', upval/100]
            elif cond == 'break':
                res = ['bk', upval/100]
            elif cond == 'enemy has def down':
                res = ['k_debuff_def', upval/100]
        condstr = ab_cond(kwargs.get('ab'))
        if res:
            if condstr:
                res.append(condstr)
            return res

def ab_actcond(**kwargs):
    ab = kwargs['ab']
    # special case FS prep
    actcond = kwargs.get('var_a')
    if not actcond:
        if (var_str := kwargs.get('var_str')):
            actcond = var_str.get('_ActionCondition1')
    cond = ab.get('_ConditionType')
    astr = None
    extra_args = []
    if cond == 'doublebuff':
        if (cd := kwargs.get('_CoolTime')):
            astr = 'bcc'
        else:
            astr = 'bc'
    elif cond == 'hp drop under':
        if ab.get('_OccurenceNum'):
            astr = 'lo'
        elif ab.get('_MaxCount') == 5:
            astr = 'uo'
        else:
            astr = 'ro'
    elif cond == 'every combo':
        if ab.get('_TargetAction') == 'force strike':
            return ['fsprep', ab.get('_OccurenceNum'), kwargs.get('var_str').get('_RecoverySpRatio')]
        if (val := actcond.get('_Tension')):
            return ['ecombo', int(ab.get('_ConditionValue'))]
    elif cond == 'prep' and (val := actcond.get('_Tension')):
        return ['eprep', int(val)]
    elif cond == 'claws':
        if val := actcond.get('_RateSkill'):
            return ['dcs', 3]
        elif val := actcond.get('_RateDefense'):
            return ['dcd', 3]
        else:
            return ['dc', 3]
    elif cond == 'primed':
        astr = 'primed'
    elif cond == 'slayer/striker':
        if ab.get('_TargetAction') == 'force strike':
            astr = 'sts'
        else:
            astr = 'sls'
    elif cond == 'affliction proc':
        affname = AFFLICTION_TYPES[ab.get('_ConditionValue')].lower()
        if var_str.get('_TargetGroup') == 6:
            astr = f'affteam_{affname}'
        else:
            astr = f'affself_{affname}'
        if (duration := actcond.get('_DurationSec')) != 15:
            extra_args.append(duration)
        if (cooltime := ab.get('_CoolTime')) != 10:
            if not extra_args:
                extra_args.append(fr(actcond.get('_DurationSec')))
            extra_args.append(fr(cooltime))
    elif cond == 'chain hp geq':
        astr = 'achain'
        extra_args = [f'hp{ab.get("_ConditionValue")}']
    if astr:
        full_astr, value = None, None
        if (val := actcond.get('_Tension')):
            full_astr = f'{astr}_energy'
            value = int(val)
        elif (att := actcond.get('_RateAttack')):
            full_astr = f'{astr}_att'
            value = fr(att)
        elif (cchance := actcond.get('_RateCritical')):
            full_astr = f'{astr}_crit_chance'
            value = fr(cchance)
        elif (cdmg := actcond.get('_EnhancedCritical')):
            full_astr = f'{astr}_crit_damage'
            value = fr(cdmg)
        elif (defence := actcond.get('_RateDefense')):
            full_astr = f'{astr}_defense'
            value = fr(defence)
        elif (regen := actcond.get('_SlipDamageRatio')):
            full_astr = f'{astr}_regen'
            value = fr(regen*-100)
        if full_astr and value:
            return [full_astr, value, *extra_args]

def ab_prep(**kwargs):
    ab = kwargs['ab']
    upval = kwargs.get('upval', 0)
    astr = 'prep'
    if ab.get('_OnSkill') == 99:
        astr = 'scharge_all'
        upval /= 100
    if (condstr := ab_cond(ab)):
        return [astr, upval, condstr]
    return [astr, upval]

def ab_generic(name, div=None):
    def ab_whatever(**kwargs):
        if (upval := kwargs.get('upval')):
            res = [name, upval if not div else upval/div]
            if (condstr := ab_cond(kwargs.get('ab'))):
                res.append(condstr)
            return res
    return ab_whatever

def ab_aff_k(**kwargs):
    if (a_id := kwargs.get('var_a')):
        res = [f'k_{AFFLICTION_TYPES.get(a_id, a_id).lower()}', kwargs.get('upval')/100]
        if (condstr := ab_cond(kwargs.get('ab'))):
            res.append(condstr)
        return res


ABILITY_CONVERT = {
    1: ab_stats,
    3: ab_aff_edge,
    6: ab_damage,
    7: ab_generic('cc', 100),
    11: ab_generic('spf', 100),
    14: ab_actcond,
    17: ab_prep,
    18: ab_generic('bt', 100),
    19: ab_generic('dbt', 100),
    20: ab_aff_k,
    26: ab_generic('cd', 100),
    27: ab_generic('dp'),
    36: ab_generic('da', 100),
    59: ab_generic('dbt', 100) # ?
}
SPECIAL = {
    448: ['spu', 0.08],
    1402: ['au', 0.08]
}
def convert_ability(ab, debug=False):
    if special_ab := SPECIAL.get(ab.get('_Id')):
        return [special_ab], []
    converted = []
    skipped = []
    for i in (1, 2, 3):
        if not f'_AbilityType{i}' in ab:
            continue
        atype = ab[f'_AbilityType{i}']
        if (convert_a := ABILITY_CONVERT.get(atype)):
            try:
                res = convert_a(
                    # atype=atype,
                    # cond=ab.get('_ConditionType'),
                    # condval=ab.get('_ConditionValue'),
                    # ele=ab.get('_ElementalType'),
                    # wep=ab.get('_WeaponType'),
                    # cd=ab.get('_CoolTime'),
                    ab=ab,
                    target=ab.get(f'_TargetAction{i}'),
                    upval=ab.get(f'_AbilityType{i}UpValue'),
                    var_a=ab.get(f'_VariousId{i}a'),
                    var_b=ab.get(f'_VariousId{i}b'),
                    var_c=ab.get(f'_VariousId{i}c'),
                    var_str=ab.get(f'_VariousId{i}str'),
                )
            except:
                res = None
            if res:
                converted.append(res)
        elif atype == 43:
            for a in ('a', 'b', 'c'):
                if (subab := ab.get(f'_VariousId{i}{a}')):
                    sub_c, sub_s = convert_ability(subab)
                    converted.extend(sub_c)
                    skipped.extend(sub_s)
    if debug or not converted:
        skipped.append((ab.get('_Id'), ab.get('_Name')))
    return converted, skipped


def convert_all_ability(ab_lst, debug=False):
    all_c, all_s = [], []
    for ab in ab_lst:
        converted, skipped = convert_ability(ab, debug=debug)
        all_c.extend(converted)
        all_s.extend(skipped)
    return all_c, all_s

# ALWAYS_KEEP = {400127, 400406, 400077, 400128, 400092, 400410}
class WpConf(AbilityCrest):
    HDT_PRINT = {
        "name": "High Dragon Print",
        "icon": "HDT",
        "hp": 83,
        "att": 20,
        "rarity": 5,
        "union": 0,
        "a": [["res_hdt", 0.25]]
    }
    SKIP_BOON = (0, 7, 8, 9, 10)
    def process_result(self, res, exclude_falsy=True):
        ab_lst = []
        for i in (1, 2, 3):
            k = f'_Abilities{i}3'
            if (ab := res.get(k)):
                ab_lst.append(self.index['AbilityData'].get(ab, full_query=True, exclude_falsy=exclude_falsy))            
        converted, skipped = convert_all_ability(ab_lst)

        boon = res.get('_UnionAbilityGroupId', 0)
        if boon in WpConf.SKIP_BOON:
            if not converted:
                return
            if converted[0][0].startswith('sts') or converted[0][0].startswith('sls'):
                return

        conf = {
            'name': res['_Name'].strip(),
            'icon': f'{res["_BaseId"]}_02',
            'att': res['_MaxAtk'],
            'hp': res['_MaxHp'],
            'rarity': res['_Rarity'],
            'union': boon,
            'a': converted,
            # 'skipped': skipped
        }
        return conf

    def export_all_to_folder(self, out_dir='./out', ext='.json'):
        all_res = self.get_all(exclude_falsy=True)
        check_target_path(out_dir)
        outdata = {}
        skipped = []
        for res in tqdm(all_res, desc=os.path.basename(out_dir)):
            conf = self.process_result(res, exclude_falsy=True)
            if conf:
                outdata[snakey(res['_Name'])] = conf
            else:
                skipped.append((res['_BaseId'], res['_Name']))
                # skipped.append(res["_Name"])
        outdata['High_Dragon_Print'] = WpConf.HDT_PRINT
        output = os.path.join(out_dir, 'wyrmprints.json')
        with open(output, 'w', newline='', encoding='utf-8') as fp:
            # json.dump(res, fp, indent=2, ensure_ascii=False)
            fmt_conf(outdata, f=fp)
        print('Skipped:', skipped)

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
    COMMON_ACTIONS = {'dodge': {}, 'dodgeb': {}, 'dshift': {}}
    COMMON_ACTIONS_DEFAULTS = {
        # recovery only
        'dodge': 0.66667,
        'dodgeb': 0.66667,
        'dshift': 0.69444,
    }

    def convert_skill(self, k, seq, skill, lv, no_loop=False):
        conf, k = super().convert_skill(k, seq, skill, lv, no_loop=no_loop)
        conf['sp_db'] = skill.get('_SpLv2Dragon', 45)
        conf['uses'] = skill.get('_MaxUseNum', 1)
        try:
            attr = conf['attr']
            del conf['attr']
            conf['attr'] = attr
        except KeyError:
            pass
        return conf, k

    def process_result(self, res, exclude_falsy=True):
        super().process_result(res, exclude_falsy)

        ab_lst = []
        for i in (1, 2):
            if (ab := res.get(f'_Abilities{i}5')):
                ab_lst.append(ab)
        converted, skipped = convert_all_ability(ab_lst)

        conf = {
            'd': {
                'name': res.get('_SecondName', res['_Name']),
                'icon': f'{res["_BaseId"]}_{res["_VariationId"]:02}',
                'att': res['_MaxAtk'],
                'hp': res['_MaxHp'],
                'ele': ELEMENTS.get(res['_ElementalType']).lower(),
                'a': converted
            }
        }
        # if skipped:
        #     conf['d']['skipped'] = skipped

        for act, key in (('dodge', '_AvoidActionFront'), ('dodgeb', '_AvoidActionBack'), ('dshift', '_Transform')):
            s, r, _ = hit_sr(res[key]['_Parts'], is_dragon=True, signal_end={None})
                    # try:
                    #     DrgConf.COMMON_ACTIONS[act][tuple(actconf['attr'][0].items())].add(conf['d']['name'])
                    # except KeyError:
                    #     DrgConf.COMMON_ACTIONS[act][tuple(actconf['attr'][0].items())] = {conf['d']['name']}
            if DrgConf.COMMON_ACTIONS_DEFAULTS[act] != r:
                conf[act] = {'recovery': r}
            if act == 'dshift':
                hitattrs = convert_all_hitattr(res[key])
                if hitattrs and hitattrs[0]['dmg'] != 2.0:
                    try:
                        conf[act]['attr'] = hitattrs
                    except KeyError:
                        conf[act] = {'attr': hitattrs}
        
        if 'dodgeb' in conf:
            if 'dodge' not in conf or conf['dodge']['recovery'] > conf['dodgeb']['recovery']:
                conf['dodge'] = conf['dodgeb']
                conf['dodge']['backdash'] = True
            del conf['dodgeb']

        dcombo = res['_DefaultSkill']
        dcmax = res['_ComboMax']
        for n, xn in enumerate(dcombo):
            n += 1
            if dxconf := convert_x(xn['_Id'], xn, xlen=dcmax, convert_follow=False, is_dragon=True):
                conf[f'dx{n}'] = dxconf

        self.reset_meta()
        dupe_skill = {}
        for act, seq, key in (('ds', 1, '_Skill1'), ('ds_final', 0, '_SkillFinalAttack')):
            if not (dskill := res.get(key)):
                continue
            if dskill['_Id'] in self.chara_skills:
                dupe_skill[act] = self.chara_skills[dskill['_Id']][0]
            else:
                self.chara_skills[dskill['_Id']] = (act, seq, dskill, None)
        self.process_skill(res, conf, {})
        for act, src in dupe_skill.items():
            conf[act] = conf[src].copy()

        return conf

    def export_all_to_folder(self, out_dir='./out', ext='.json'):
        where_str = '_Rarity = 5 AND _IsPlayable = 1 AND (_SellDewPoint = 8500 OR _Id in ('+ ','.join(map(str, DrgConf.EXTRA_DRAGONS)) +')) AND _Id = _EmblemId'
        # where_str = '_IsPlayable = 1'
        all_res = self.get_all(exclude_falsy=True, where=where_str)
        out_dir = os.path.join(out_dir, 'drg')
        check_target_path(out_dir)
        outdata = {ele.lower(): {} for ele in ELEMENTS.values()}
        # skipped = []
        for res in tqdm(all_res, desc=os.path.basename(out_dir)):
            conf = self.process_result(res, exclude_falsy=True)
            # outfile = snakey(conf['d']['ele']) + '.json'
            if conf:
                outdata[conf['d']['ele']][snakey(conf['d']['name'])] = conf
        for ele, data in outdata.items():
            output = os.path.join(out_dir, f'{ele}.json')
            with open(output, 'w', newline='', encoding='utf-8') as fp:
                fmt_conf(data, f=fp, lim=3)
        # pprint(DrgConf.COMMON_ACTIONS)

    def get(self, name, by=None):
        res = super().get(name, by=by, full_query=False)
        if isinstance(res, list):
            res = res[0]
        return self.process_result(res)


class WepConf(WeaponBody, SkillProcessHelper):
    T2_ELE = ('shadow', 'flame')
    def process_result(self, res, exclude_falsy=True):
        super().process_result(res, exclude_falsy)
        skin = res['_WeaponSkinId']
        # if skin['_FormId'] % 10 == 1 and res['_ElementalType'] in WepConf.T2_ELE:
        #     return None
        tier = res.get('_MaxLimitOverCount', 0) + 1
        try:
            ele_type = res['_ElementalType'].lower()
        except AttributeError:
            ele_type = 'any'
        ab_lst = []
        for i in (1, 2, 3):
            for j in (3, 2, 1):
                if (ab := res.get(f'_Abilities{i}{j}')):
                    ab_lst.append(ab)
                    break
        converted, skipped = convert_all_ability(ab_lst)
        conf = {
            'w': {
                'name': res['_Name'],
                'icon': f'{skin["_BaseId"]}_{skin["_VariationId"]:02}_{skin["_FormId"]}',
                'att': res.get(f'_MaxAtk{tier}', 0),
                'hp': res.get(f'_MaxHp{tier}', 0),
                'ele': ele_type,
                'wt': res['_WeaponType'].lower(),
                'series': res['_WeaponSeriesId']['_GroupSeriesName'].replace(' Weapons', ''),
                # 'crest': {
                #     5: res.get('_CrestSlotType1MaxCount', 0),
                #     4: res.get('_CrestSlotType2MaxCount', 0)
                # },
                'tier': tier,
                'a': converted
                # 'skipped': skipped
            }
        }

        self.reset_meta()
        dupe_skill = {}
        for act, seq, key in (('s3', 3, f'_ChangeSkillId3'),):
            if not (skill := res.get(key)):
                continue
            if skill['_Id'] in self.chara_skills:
                dupe_skill[act] = self.chara_skills[skill['_Id']][0]
            else:
                self.chara_skills[skill['_Id']] = (act, seq, skill, None)
        self.process_skill(res, conf, {})

        return conf

    def export_all_to_folder(self, out_dir='./out', ext='.json'):
        all_res = self.get_all(exclude_falsy=True, where='_IsPlayable = 1')
        out_dir = os.path.join(out_dir, 'wep')
        check_target_path(out_dir)
        outdata = {wt.lower(): {ele.lower(): {} for ele in ('any', *ELEMENTS.values())} for wt in WEAPON_TYPES.values()}
        # skipped = []
        for res in tqdm(all_res, desc=os.path.basename(out_dir)):
            conf = self.process_result(res, exclude_falsy=True)
            # outfile = snakey(conf['d']['ele']) + '.json'
            if conf:
                outdata[conf['w']['wt']][conf['w']['ele']][snakey(conf['w']['series']).lower()] = conf
        for wt, data in outdata.items():
            output = os.path.join(out_dir, f'{wt}.json')
            with open(output, 'w', newline='', encoding='utf-8') as fp:
                fmt_conf(data, f=fp, lim=4)
        #     else:
        #         skipped.append(res["_Name"])
        # print('Skipped:', ','.join(skipped))


BUFF_FMT = {
    'self': 'increases the {mtype} of the user by {value:.0%}',
    'team': 'increases the {mtype} of the team by {value:.0%}',
    'nearby': 'increases the {mtype} of the user and nearby allies by {value:.0%}',
    'next': 'increases the damage of the next {mtype} by {value:.0%}',
    'zone': 'creates a buff zone that increases the {mtype} of allies within by {value:.0%}',
}
DEBUFF_FMT = 'reduces enemy {mtype} by {value:.0%} with {rate:.0%} chance'
DEBUFFB_FMT = 'creates a debuff zone that reduces the defense of enemies within by {value:.0%}'
AFFRES_FMT = 'reduces enemy {aff} resist by {value:.0%}'
MTYPE = {
    'att': 'strength',
    'def': 'defense',
    'crit': 'critical',
    'fs': 'force strike',
    's': 'skill',
    'sp': 'skill haste',
    'spd': 'attack speed',
    'cspd': 'charge speed'
}

KS_PAST_TENSE = {
    'poison': 'poisoned',
    'burn': 'burning',
    'freeze': 'frozen',
    'paralysis': 'paralyzed',
    'blind': 'blinded',
    'stun': 'stunned',
    'curse': 'cursed',
    'UNKNOWN08': 'bolbed',
    'bog': 'bogged',
    'sleep': 'sleeping',
    'frostbite': 'Frostbitten',
    'stormlash': 'stormlashed',
    'shadowblight': 'shadowblighted',
    'def down': 'defense reduced',
    'buff': 'buffed',
    'break': 'broken'
}

def condense_desc(desc_list):
    condensed = []
    prev_desc = None
    prev_count = 0
    for desc in sorted(desc_list):
        desc = desc[1:]
        if not desc:
            continue
        if desc != prev_desc:
            if prev_desc is not None and prev_count > 1:
                prev_desc.append(f'{prev_count} times')
            condensed.append(desc)
            prev_desc = desc
            prev_count = 1
        else:
            prev_count += 1
    if prev_desc is not None and prev_count > 1:
        prev_desc.append(f'{prev_count} times')
    return condensed

def describe_buff(buff):
    btype = buff[0]
    if btype in ('energy', 'inspiration'):
        stack = buff[1]
        if len(buff) == 3:
            if buff[2] == 'team':
                return f'increases {btype} level of team by {stack}'
            else:
                return f'increases {btype} level of the user and nearby allies by {stack}'
        else:
            return f'increases {btype} level of the user by {stack}'
    buff_desc = ''
    value = buff[1]

    if btype == 'debuff':
        if buff[4] == 'defb':
            buff_desc = DEBUFFB_FMT.format(value=-value)
        else:
            mtype = MTYPE.get(buff[4], buff[4])
            buff_desc = DEBUFF_FMT.format(mtype=mtype, value=-value, rate=buff[3])
    elif btype == 'affres':
        buff_desc = AFFRES_FMT.format(aff=buff[3], value=-value)
    elif btype in BUFF_FMT:
        mtype = MTYPE.get(buff[3], buff[3])
        if buff[4] != 'buff':
            mtype += ' ' + buff[4]
        buff_desc = BUFF_FMT[btype].format(mtype=mtype, value=value)
    if buff_desc:
        if buff[2] != -1:
            buff_desc += f' for {buff[2]}s'
        return buff_desc
        if buff[-1].startswith('-overwrite') or buff[-1].startswith('-refresh'):
            buff_desc += f', does not stack'

def describe_conf(adv_conf):
    conf_desc = {}
    flatten = {}
    for name, conf in adv_conf.items():
        if ('attr' not in conf):
            continue
        try:
            base, group = name.split('_')
        except ValueError:
            base = name
            group = 'default'
        mlv = 0
        for lv in conf:
            if lv.startswith('lv'):
                nlv = int(lv[-1])
                mlv = nlv + 1
                if ('attr' not in conf[lv]):
                    continue
                flatten[(base, group, nlv)] = conf[lv]
        flatten[(base, group, mlv)] = conf
    for key, conf in flatten.items():
        conf_desc[key] = []
        for attr in conf['attr']:
            if isinstance(attr, int):
                for _ in range(attr-1):
                    conf_desc[key].append(attr_desc.copy())
                continue
            attr_desc = [attr.get('iv', 0)]
            if dmg := attr.get('dmg'):
                attr_desc.append(f'deal {dmg:.2%} damage')
            if bleed := attr.get('bleed'):
                rate = bleed[0]
                mod = bleed[1]
                attr_desc.append(f'inflict bleed for 30s with {rate/100:.0%} chance and deal {mod:.2%} damage every 4.9s')
            if afflic := attr.get('afflic'):
                afflic_desc = []
                aff_type = afflic[0]
                aff_rate = afflic[1]
                if aff_type in DEFAULT_AFF_IV: # dot
                    mod = afflic[2]
                    try:
                        duration = afflic[3]
                    except IndexError:
                        duration = DEFAULT_AFF_DURATION[aff_type]
                    try:
                        iv = afflic[4]
                    except IndexError:
                        iv = DEFAULT_AFF_IV[aff_type]
                    attr_desc.append(f'inflict {aff_type} for {duration}s with {aff_rate/100:.0%} chance and deal {mod:.2%} damage every {iv}s')
                else: # cc
                    durations = afflic[2:]
                    if len(durations) == 0:
                        durations = DEFAULT_AFF_DURATION[aff_type]
                    elif len(durations) == 2:
                        attr_desc.append(f'inflict {aff_type} for {durations[0]}-{durations[1]}s with {aff_rate/100:.2%} chance')
                    else:
                        attr_desc.append(f'inflict {aff_type} for {durations[0]}s with {aff_rate/100:.0%} chance')
            if killer := attr.get('killer'):
                mod = 1 + killer[0]
                cond = ' or '.join([KS_PAST_TENSE.get(state, state) for state in killer[1]])
                attr_desc.append(f'{mod}x damage to {cond} foes')
            if crisis := attr.get('crisis'):
                attr_desc.append(f'more damage as hp decreases, up to {crisis+1}x')
            if buff := attr.get('buff'):
                if isinstance(buff[0], list):
                    for b in buff:
                        if bdesc := describe_buff(b):
                            attr_desc.append(bdesc)
                else:
                    if bdesc := describe_buff(buff):
                        attr_desc.append(bdesc)
            conf_desc[key].append(attr_desc)
        conf_desc[key] = condense_desc(conf_desc[key])
    return pformat(conf_desc)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-a', help='_Name/_SecondName')
    parser.add_argument('--desc', help='wiki describe', action='store_true')
    parser.add_argument('-d', help='_Name')
    parser.add_argument('-wp', help='_Name')
    parser.add_argument('-s', help='_SkillId')
    parser.add_argument('-slv', help='Skill level')
    parser.add_argument('-f', help='_BurstAttackId')
    parser.add_argument('-x', help='_UniqueComboId')
    parser.add_argument('-fm', help='_BurstAttackMarker')
    # parser.add_argument('-x', '_UniqueComboId')
    parser.add_argument('-w', help='_Name')
    parser.add_argument('-act', help='_ActionId')
    args = parser.parse_args()

    index = DBViewIndex()
    # out_dir = os.path.join(pathlib.Path(__file__).parent.absolute(), '..', '..', 'dl', 'conf', 'gen')
    out_dir = os.path.join(pathlib.Path(__file__).parent.absolute(), '..', 'out', 'gen')

    if args.s and args.slv:
        view = AdvConf(index)
        if args.a:
            view.get(args.a)
        view.eskill_counter = itertools.count(start=1)
        view.efs_counter = itertools.count(start=1)
        view.chara_skills = {}
        view.enhanced_fs = []
        view.chara_skill_loop = set()
        sconf, k = view.convert_skill('s1', 0, view.index['SkillData'].get(int(args.s), exclude_falsy=True), int(args.slv))
        sconf = {k: sconf}
        fmt_conf(sconf, f=sys.stdout)
        print('\n')
        pprint(view.chara_skills.keys())
        pprint(view.enhanced_fs)
    elif args.a:
        view = AdvConf(index)
        if args.a == 'all':
            view.export_all_to_folder(out_dir=out_dir, desc=args.desc)
        else:
            adv_conf = view.get(args.a, all_levels=args.desc)
            if args.desc:
                print(describe_conf(adv_conf))
            else:
                fmt_conf(adv_conf, f=sys.stdout)
    elif args.d:
        view = DrgConf(index)
        if args.d == 'all':
            view.export_all_to_folder(out_dir=out_dir)
        else:
            d = view.get(args.d)
            fmt_conf(d, f=sys.stdout)
    elif args.wp:
        view = WpConf(index)
        if args.wp == 'all':
            view.export_all_to_folder(out_dir=out_dir)
        else:
            wp = view.get(args.wp)
            fmt_conf({snakey(wp['name']): wp}, f=sys.stdout)
    elif args.f:
        view = PlayerAction(index)
        burst = view.get(int(args.f), exclude_falsy=True)
        if (mid := burst.get('_BurstMarkerId')):
            marker = mid
        elif args.fm:
            marker = view.get(int(args.fm), exclude_falsy=True)
        else:
            marker = view.get(int(args.f)+4, exclude_falsy=True)
        fmt_conf(convert_fs(burst, marker), f=sys.stdout)
    elif args.x:
        view = CharaUniqueCombo(index)
        xalt = view.get(int(args.x), exclude_falsy=True)
        conf = {}
        for prefix in ('', 'Ex'):
            if xalt.get(f'_{prefix}ActionId'):
                for n, xn in enumerate(xalt[f'_{prefix}ActionId']):
                    n += 1
                    if xaltconf := convert_x(xn['_Id'], xn, xlen=xalt['_MaxComboNum']):
                        conf[f'x{n}_{prefix.lower()}'] = xaltconf
        fmt_conf(conf, f=sys.stdout)
    elif args.w:
        if args.w == 'base':
            view = BaseConf(index)
            view.export_all_to_folder(out_dir=out_dir)
        elif args.w == 'all':
            view = WepConf(index)
            view.export_all_to_folder(out_dir=out_dir)
    elif args.act:
        view = PlayerAction(index)
        action = view.get(int(args.act), exclude_falsy=True)
        pprint(hit_sr(action['_Parts'], is_dragon=True))