import sys
import os
import pathlib
import json
import re
import itertools
from unidecode import unidecode
from tqdm import tqdm
from pprint import pprint
import argparse

from loader.Database import DBViewIndex, DBView, check_target_path
from exporter.Shared import ActionParts, PlayerAction, AbilityData
from exporter.Adventurers import CharaData
from exporter.Dragons import DragonData
from exporter.Weapons import WeaponType, WeaponData
from exporter.Wyrmprints import AmuletData
from exporter.Mappings import WEAPON_TYPES, ELEMENTS, CLASS_TYPES, AFFLICTION_TYPES


def snakey(name):
    return re.sub(r'[^0-9a-zA-Z ]', '', unidecode(name).strip()).replace(' ', '_')

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
def fmt_conf(data, k=None, depth=0, f=sys.stdout):
    if depth >= 2:
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
        res = fmt_conf(v, k, depth+1, f)
        if res is not None:
            f.write(res)
        if idx < end:
            f.write(',\n')
        else:
            f.write('\n')
    f.write(INDENT*depth)
    f.write('}')

def fr(num):
    return round(num, 5)

def convert_all_hitattr(action, pattern=None, adv=None, skill=None):
    actparts = action['_Parts']
    hitattrs = []
    once_per_action = set()
    for part in actparts:
        part_hitattrs = []
        for label in ActionParts.HIT_LABELS:
            if (hitattr_lst := part.get(label)):
                if len(hitattr_lst) == 1:
                    hitattr_lst = hitattr_lst[0]
                if isinstance(hitattr_lst, dict):
                    if (attr := convert_hitattr(hitattr_lst, part, action, once_per_action, adv=adv, skill=skill)):
                        part_hitattrs.append(attr)
                elif isinstance(hitattr_lst, list):
                    for hitattr in hitattr_lst:
                        if (not pattern or pattern.match(hitattr['_Id'])) and \
                            (attr := convert_hitattr(hitattr, part, action, once_per_action, adv=adv, skill=skill)):
                            part_hitattrs.append(attr)
                            if not pattern:
                                break
        if not part_hitattrs:
            continue
        if (blt := part.get('_bulletNum', 0)) > 1:
            part_hitattrs.append(blt)
        gen, delay = None, None
        if (gen := part.get('_generateNum')):
            delay = part.get('_generateDelay')
            ref_attrs = part_hitattrs
        elif (abd := part.get('_abDuration', 0)) > (abi := part.get('_abHitInterval', 0)):
            gen = int(abd/abi)
            delay = abi
            ref_attrs = [part_hitattrs[-1]]
        if gen and delay:
            gen_attrs = []
            for gseq in range(1, gen):
                for attr in ref_attrs:
                    gattr = attr.copy()
                    gattr['iv'] = fr(attr.get('iv', 0)+delay*gseq)
                    gen_attrs.append(gattr)
            part_hitattrs.extend(gen_attrs)
        hitattrs.extend(part_hitattrs)
    once_per_action = set()
    return hitattrs

def convert_hitattr(hitattr, part, action, once_per_action, adv=None, skill=None):
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
            if (sp_i := hitattr.get('_RecoverySpSkillIndex')):
                attr['sp'].append(f's{sp_i}')
            once_per_action.add('sp')
    if 'dp' not in once_per_action and (dp := hitattr.get('_AdditionRecoveryDpLv1')):
        attr['dp'] = dp
        once_per_action.add('dp')
    if 'utp' not in once_per_action and ((utp := hitattr.get('_AddUtp')) or (utp := hitattr.get('_AdditionRecoveryUtp'))):
        attr['utp'] = utp
        once_per_action.add('utp')
    # if hitattr.get('_RecoveryValue'):
    #     attr['heal'] = fr(hitattr.get('_RecoveryValue'))
    if part.get('commandType') == 'FIRE_STOCK_BULLET' and (stock := action.get('_MaxStockBullet', 0)) > 1:
        attr['extra'] = stock
    if (bc := attr.get('_DamageUpRateByBuffCount')):
        attr['bufc'] = bc
    if 0 < (attenuation := part.get('_attenuationRate', 0)) < 1:
        attr['fade'] = fr(attenuation)

    if (actcond := hitattr.get('_ActionCondition1')) and actcond['_Id'] not in once_per_action:
        once_per_action.add(actcond['_Id'])
        if actcond.get('_DamageLink'):
            return convert_hitattr(actcond['_DamageLink'], part, action, once_per_action, adv=adv, skill=skill)
        alt_buffs = []
        if adv and skill:
            for ehs in AdvConf.ENHANCED_SKILL:
                if (esk := actcond.get(ehs)):
                    if isinstance(esk, int) or esk.get('_Id') in adv.all_chara_skills:
                        adv.chara_skill_loop.add(skill['_Id'])
                    else:
                        s = int(ehs[-1])
                        eid = next(adv.eskill_counter)
                        group = 'enhanced' if eid == 1 else f'enhanced{eid}'
                        adv.chara_skills[esk.get('_Id')] = (f's{s}_{group}', s, esk, skill['_Id'])
                        alt_buffs.append(['sAlt', group, f's{s}'])
            if (eba := actcond.get('_EnhancedBurstAttack')) and isinstance(eba, dict):
                eid = next(adv.efs_counter)
                group = 'enhanced' if eid == 1 else f'enhanced{eid}'
                adv.enhanced_fs.append((group, eba, eba.get('_BurstMarkerId')))
                alt_buffs.append(['fsAlt', group])

        if target == 3 and (afflic := actcond.get('_Type')):
            attr['afflic'] = [afflic.lower(), actcond['_Rate']]
            if (dot := actcond.get('_SlipDamagePower')):
                attr['afflic'].append(fr(dot))
        elif 'Bleeding' == actcond.get('_Text'):
            attr['bleed'] = [actcond['_Rate'], fr(actcond['_SlipDamagePower'])]
        else:
            buffs = []
            for tsn, btype in AdvConf.TENSION_KEY.items():
                if (v := actcond.get(tsn)):
                    if target == 6:
                        buffs.append([btype, v, 'team'])
                    else:
                        buffs.append([btype, v])
            if not buffs:
                if part.get('_lifetime'):
                    duration = fr(part.get('_lifetime'))
                    btype = 'zone'
                elif actcond.get('_DurationNum'):
                    duration = actcond.get('_DurationNum')
                    btype = 'next'
                else:
                    duration = actcond.get('_DurationSec', -1)
                    duration = fr(duration)
                    btype = 'team' if target == 6 else 'self'
                for b in alt_buffs:
                    if btype == 'next' and b[0] == 'fsAlt':
                        b.extend((-1, duration))
                    elif duration > -1:
                        b.append(duration)
                    buffs.append(b)
                if target == 3:
                    for k, mod in AdvConf.DEBUFFARG_KEY.items():
                        if (value := actcond.get(k)):
                            buffs.append(['debuff', fr(value), duration, actcond.get('_Rate')/100, mod])
                else:
                    # BUFFARG_KEY SABARG_KEY
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
                if any(actcond.get(k) for k in AdvConf.OVERWRITE):
                    buffs.append('-refresh')
                attr['buff'] = buffs
    if attr:
        iv = fr(part['_seconds'] + part.get('_delayTime', 0))
        if iv > 0:
            attr['iv'] = iv
        if 'BULLET' in part['commandType']:
            attr['msl'] = 1
        return attr
    else:
        return None


def hit_sr(parts, seq=None, xlen=None):
    s, r = None, None
    for part in parts:
        if part['commandType'] in ('HIT', 'BULLET', 'FORMATION_BULLET', 'SETTING_HIT') and s is None:
            s = fr(part['_seconds'])
        if part['commandType'] == 'ACTIVE_CANCEL':
            recovery = part['_seconds']
            if seq:
                if (seq + 1 == part.get('_actionId', 0)) or ((seq + 1 - xlen - part.get('_actionId', 0)) % 100 == 0):
                    r = recovery
            elif s is not None:
                r = recovery
    if r is None:
        for part in reversed(parts):
            if part['commandType'] == 'ACTIVE_CANCEL':
                r = part['_seconds']
                break
    return s, r


def hit_attr_adj(action, s, conf, pattern=None, skip_nohitattr=True):
    if (hitattrs := convert_all_hitattr(action, pattern=pattern)):
        conf['recovery'] = fr(conf['recovery'] - s)
        for attr in hitattrs:
            if not isinstance(attr, int) and 'iv' in attr:
                attr['iv'] = fr(attr['iv'] - s)
                if attr['iv'] == 0:
                    del attr['iv']
        conf['attr'] = hitattrs
    if not hitattrs and skip_nohitattr:
        return None
    return conf


def convert_x(aid, xn, xlen=5):
    # convert_hitattr(self, hitattr, part, once_per_action, skill=None)
    s, r = hit_sr(xn['_Parts'], seq=aid, xlen=xlen)
    xconf = {
        'startup': s,
        'recovery': r
    }
    xconf = hit_attr_adj(xn, s, xconf, skip_nohitattr=False)
    return xconf


def convert_fs(burst, marker=None, cancel=None):
    startup, recovery = hit_sr(burst['_Parts'])
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
                    fsconf[f'fs{idx+1}'] = clv_attr
                    fsconf[f'fs{idx+1}']['charge'] = fr(totalc)
            if 'fs2' in fsconf and 'attr' not in fsconf['fs']:
                del fsconf['fs']
            elif 'fs1' in fsconf:
                fsconf['fs'] = fsconf['fs1']
                del fsconf['fs1']
        else:
            fsconf['fs'] = hit_attr_adj(burst, startup, fsconf['fs'], re.compile(r'.*H0\d_LV02$'))
    if cancel is not None:
        fsconf['fsf'] = {
            'charge': fr(0.1+cancel['_Parts'][0]['_duration']),
            'startup': 0,
            'recovery': 0,
        }
    return fsconf


class WepConf(WeaponType):
    LABEL_MAP = {
        'AXE': 'axe',
        'BOW': 'bow',
        'CAN': 'staff',
        'DAG': 'dagger',
        'KAT': 'blade',
        'LAN': 'lance',
        'ROD': 'wand',
        'SWD': 'sword',
    }
    def process_result(self, res, exclude_falsy=True, full_query=True):
        xnconf = {'lv2':{}}
        fs_id = res['_BurstPhase1']
        res = super().process_result(res, exclude_falsy=True, full_query=True)
        fs_delay = {}
        for n in range(1, 6):
            xn = res[f'_DefaultSkill0{n}']
            xnconf[f'x{n}'] = convert_x(xn['_Id'], xn)
            for part in xn['_Parts']:
                if part['commandType'] == 'ACTIVE_CANCEL' and part.get('_actionId') == fs_id and part.get('_seconds'):
                    fs_delay[f'x{n}'] = part.get('_seconds')
            if (hitattrs := convert_all_hitattr(xn, re.compile(r'.*H0\d_LV02$'))):
                for attr in hitattrs:
                    attr['iv'] = fr(attr['iv'] - xnconf[f'x{n}']['startup'])
                    if attr['iv'] == 0:
                        del attr['iv']
                xnconf['lv2'][f'x{n}'] = {'attr': hitattrs}
        fsconf = convert_fs(res['_BurstPhase1'], res['_ChargeMarker'], res['_ChargeCancel'])
        startup = fsconf['fs']['startup']
        for x, delay in fs_delay.items():
            fsconf['fs'][x] = {'startup': fr(startup+delay)}
        xnconf.update(fsconf)
        return xnconf

    @staticmethod
    def outfile_name(res, ext):
        return WepConf.LABEL_MAP[res['_Label']]+ext

    def export_all_to_folder(self, out_dir='./out', ext='.json'):
        out_dir = os.path.join(out_dir, 'wep')
        all_res = self.get_all(exclude_falsy=True)
        check_target_path(out_dir)
        for res in tqdm(all_res, desc=os.path.basename(out_dir)):
            out_name = self.outfile_name(res, ext).lower()
            res = self.process_result(res, exclude_falsy=True)
            output = os.path.join(out_dir, out_name)
            with open(output, 'w', newline='', encoding='utf-8') as fp:
                # json.dump(res, fp, indent=2, ensure_ascii=False)
                fmt_conf(res, f=fp)

class AdvConf(CharaData):
    GENERIC_BUFF = ('skill_A', 'skill_B', 'skill_C', 'skill_D')
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
    TENSION_KEY = {
        '_Tension': 'energy',
        '_Inspiration': 'inspiration'
    }
    OVERWRITE = ('_Overwrite', '_OverwriteVoice', '_OverwriteGroupId')
    ENHANCED_SKILL = ('_EnhancedSkill1', '_EnhancedSkill2')

    MISSING_ENDLAG = []
    DO_NOT_FIND_LOOP = (
        10350302, # summer norwin
        10650101, # gala sarisse
    )

    def convert_skill(self, k, seq, skill, lv):
        action = skill.get('_AdvancedActionId1', skill.get('_ActionId1'))
        if isinstance(action, int):
            action = skill.get('_ActionId1')

        timing = (0.1, None)
        actcancel = None
        mstate = None
        for part in action['_Parts']:
            if part['commandType'] == 'ACTIVE_CANCEL' and '_actionId' not in part and actcancel is None:
                actcancel = (0.1, part['_seconds'])
            if part['commandType'] == 'PARTS_MOTION' and mstate is None:
                if (animation := part.get('_animation')):
                    mstate = (0.1, animation['duration'])
                if part.get('_motionState') in AdvConf.GENERIC_BUFF:
                    mstate = (0.1, 1.05)
            if actcancel and mstate:
                break
        timing = actcancel or mstate or timing

        if timing[1] is None:
            AdvConf.MISSING_ENDLAG.append(skill.get('_Name'))

        sconf = {
            'sp': skill.get(f'_SpLv{lv}', skill.get('_Sp', 0)),
            'startup': fr(timing[0]),
            'recovery': None if not timing[1] else fr(timing[1]),
        }

        if (hitattrs := convert_all_hitattr(action, re.compile(f'.*LV0{lv}$'), adv=self, skill=skill)):
            adj = None
            sconf['attr'] = hitattrs

        if (transkills := skill.get('_TransSkill')) and isinstance(transkills, dict):
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
                    self.chara_skills[ab[f'_VariousId{s}a']['_Id']] = (f's{s}_{group}', s, ab[f'_VariousId{s}a'], skill['_Id'])
        return sconf, k


    def process_result(self, res, exclude_falsy=True, condense=True):
        self.index['ActionParts'].animation_reference = ('CharacterMotion', int(f'{res["_BaseId"]:06}{res["_VariationId"]:02}'))
        res = self.condense_stats(res)
        conf = {
            'c': {
                'name': res.get('_SecondName', res['_Name']),
                'icon': f'{res["_BaseId"]:06}_{res["_VariationId"]:02}_r{res["_Rarity"]:02}',
                'att': res['_MaxAtk'],
                'hp': res['_MaxHp'],
                'ele': ELEMENTS[res['_ElementalType']].lower(),
                'wt': WEAPON_TYPES[res['_WeaponType']].lower(),
                'spiral': res['_MaxLimitBreakCount'] == 5
            }
        }

        if (burst := res.get('_BurstAttack')):
            burst = self.index['PlayerAction'].get(res['_BurstAttack'], exclude_falsy=exclude_falsy)
            if burst and (marker := burst.get('_BurstMarkerId')):
                conf.update(convert_fs(burst, marker))

        # exceptions exist
        if conf['c']['spiral']:
            mlvl = {1: 4, 2: 3}
        else:
            mlvl = {1: 3, 2: 2}
        self.chara_skills = {}
        for s in (1, 2):
            skill = self.index['SkillData'].get(res[f'_Skill{s}'], 
                exclude_falsy=exclude_falsy, full_query=True)
            self.chara_skills[res[f'_Skill{s}']] = (f's{s}', s, skill, None)
        for m in range(1, 5):
            if (mode := res.get(f'_ModeId{m}')):
                mode = self.index['CharaModeData'].get(mode, exclude_falsy=exclude_falsy, full_query=True)
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
                    for prefix in ('', 'Ex'):
                        if xalt.get(f'_{prefix}ActionId'):
                            for n, xn in enumerate(xalt[f'_{prefix}ActionId']):
                                n += 1
                                if xaltconf := convert_x(xn['_Id'], xn, xlen=xalt['_MaxComboNum']):
                                    conf[f'x{n}_{mode_name}{prefix.lower()}'] = convert_x(xn['_Id'], xn, xlen=xalt['_MaxComboNum'])

        # self.abilities = self.last_abilities(res, as_mapping=True)
        # pprint(self.abilities)

        self.chara_skill_loop = set()
        self.eskill_counter = itertools.count(start=1)
        self.efs_counter = itertools.count(start=1)
        self.all_chara_skills = {}
        self.enhanced_fs = []
        # for k, seq, skill in self.chara_skills.values():
        while self.chara_skills:
            k, seq, skill, prev_id = next(iter(self.chara_skills.values()))
            self.all_chara_skills[skill.get('_Id')] = (k, seq, skill, prev_id)
            lv = mlvl[seq]
            cskill, k = self.convert_skill(k, seq, skill, lv)
            # cskill['curr_id'] = skill.get('_Id')
            # cskill['prev_id'] = prev_id
            conf[k] = cskill
            del self.chara_skills[skill.get('_Id')]

        for efs, eba, emk in self.enhanced_fs:
            n = ''
            for fs, fsc in convert_fs(eba, emk).items():
                conf[f'{fs}_{efs}'] = fsc

        if res.get('_Id') not in AdvConf.DO_NOT_FIND_LOOP:
            if self.chara_skill_loop:
                for loop_id in self.chara_skill_loop:
                    k, seq, _, prev_id = self.all_chara_skills.get(loop_id)
                    loop_sequence = [(k, seq)]
                    while prev_id != loop_id and prev_id is not None:
                        k, seq, _, pid = self.all_chara_skills.get(prev_id)
                        loop_sequence.append((k, seq))
                        prev_id = pid
                    for p, ks in enumerate(reversed(loop_sequence)):
                        k, seq = ks
                        conf[f's{seq}_phase{p+1}'] = conf[k]
                        del conf[k]

        return conf

    def get(self, name):
        res = super().get(name, full_query=False)
        return self.process_result(res)

    @staticmethod
    def outfile_name(conf, ext):
        return snakey(conf['c']['name']) + ext

    def export_all_to_folder(self, out_dir='./out', ext='.json'):
        all_res = self.get_all(exclude_falsy=True)
        ref_dir = os.path.join(out_dir, '..', 'adv')
        out_dir = os.path.join(out_dir, 'adv')
        check_target_path(out_dir)
        for res in tqdm(all_res, desc=os.path.basename(out_dir)):
            if not res.get('_IsPlayable'):
                continue
            try:
                outconf = self.process_result(res, exclude_falsy=True)
                out_name = self.outfile_name(outconf, ext)
                output = os.path.join(out_dir, out_name)
                ref = os.path.join(ref_dir, out_name)
                if os.path.exists(ref):
                    with open(ref, 'r', newline='', encoding='utf-8') as fp:
                        refconf = json.load(fp)
                        try:
                            outconf['c']['a'] = refconf['c']['a']
                        except:
                            outconf['c']['a'] = []
                with open(output, 'w', newline='', encoding='utf-8') as fp:
                    # json.dump(res, fp, indent=2, ensure_ascii=False)
                    fmt_conf(outconf, f=fp)
            except Exception as e:
                print(res['_Id'])
                pprint(outconf)
                raise e
        print('Missing endlag for:', AdvConf.MISSING_ENDLAG)


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
            if cond == 'overdrive':
                res = ['od', upval/100]
            elif cond == 'break':
                res = ['bk', upval/100]
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
        actcond = kwargs.get('var_str').get('_ActionCondition1')
    cond = ab.get('_ConditionType')
    astr = None
    if cond == 'doublebuff':
        if (cd := kwargs.get('_CoolTime')):
            astr = 'bcc'
        else:
            astr = 'bc'
    if cond == 'hp drop under':
        if ab.get('_OccurenceNum'):
            astr = 'lo'
        else:
            astr = 'ro'
    if cond == 'every combo':
        if ab.get('_TargetAction') == 'force strike':
            return ['fsprep', ab.get('_OccurenceNum'), kwargs.get('var_str').get('_RecoverySpRatio')]
        if (val := actcond.get('_Tension')):
            return ['ecombo', int(ab.get('_ConditionValue'))]
    if cond == 'prep' and (val := actcond.get('_Tension')):
        return ['eprep', int(val)]
    if cond == 'claws':
        if val := actcond.get('_RateSkill'):
            return ['dcs', 3]
        else:
            return ['dc', 3]
    if astr:
        if (val := actcond.get('_Tension')):
            return [f'{astr}_energy', int(val)]
        if (att := actcond.get('_RateAttack')):
            return [f'{astr}_att', fr(att)]
        if (cchance := actcond.get('_RateCritical')):
            return [f'{astr}_crit_chance', fr(cchance)]
        if (cdmg := actcond.get('_EnhancedCritical')):
            return [f'{astr}_crit_damage', fr(cdmg)]

        if (att := actcond.get('_RateDefense')):
            return [f'{astr}_defense', fr(att)]
        if (regen := actcond.get('_SlipDamageRatio')):
            return [f'{astr}_regen', fr(regen*-100)]


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
    17: ab_generic('prep'),
    18: ab_generic('bt'),
    20: ab_aff_k,
    26: ab_generic('cd', 100),
    27: ab_generic('dp'),
    36: ab_generic('da'),
}
SPECIAL = {
    448: ['sp', 0.08]
}
def convert_ability(ab):
    if special_ab := SPECIAL.get(ab.get('_Id')):
        return [special_ab], []
    converted = []
    skipped = []
    for i in (1, 2, 3):
        if not f'_AbilityType{i}' in ab:
            continue
        atype = ab[f'_AbilityType{i}']
        if (convert_a := ABILITY_CONVERT.get(atype)):
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
            if res:
                converted.append(res)
        elif atype == 43:
            for a in ('a', 'b', 'c'):
                if (subab := ab.get(f'_VariousId{i}{a}')):
                    sub_c, sub_s = convert_ability(subab)
                    converted.extend(sub_c)
                    skipped.extend(sub_s)
    if not converted:
        skipped.append((ab.get('_Id'), ab.get('_Name')))
    # skipped.append((ab.get('_Id'), ab.get('_Name')))
    return converted, skipped


def convert_all_ability(ab_lst):
    all_c, all_s = [], []
    for ab in ab_lst:
        converted, skipped = convert_ability(ab)
        all_c.extend(converted)
        all_s.extend(skipped)
    return all_c, all_s

ALWAYS_KEEP = {400127, 400406, 400077, 400128, 400092}
class WpConf(AmuletData):
    HDT_PRINT = {
        "name": "High Dragon Print",
        "hp": 176,
        "att": 39,
        "icon": "HDT",
        "a": []
    }
    def process_result(self, res, exclude_falsy=True):
        ab_lst = []
        for i in (1, 2):
            k = f'_Abilities{i}3'
            if res.get(k):
                ab_lst.append(self.index['AbilityData'].get(res[k], full_query=True, exclude_falsy=exclude_falsy))
        converted, skipped = convert_all_ability(ab_lst)

        if (len(converted) == 1 or len(skipped) > 0) and res['_BaseId'] not in ALWAYS_KEEP:
            return None

        conf = {
            'name': res['_Name'].strip(),
            'att': res['_MaxAtk'],
            'hp': res['_MaxHp'],
            'icon': f'{res["_BaseId"]}_02',
            'a': converted,
            # 'skipped': skipped
        }
        return conf

    def export_all_to_folder(self, out_dir='./out', ext='.json'):
        all_res = self.get_all(exclude_falsy=True, where='_Rarity > 3')
        check_target_path(out_dir)
        outdata = {}
        skipped = []
        for res in tqdm(all_res, desc=os.path.basename(out_dir)):
            conf = self.process_result(res, exclude_falsy=True)
            if conf:
                outdata[snakey(res['_Name'])] = conf
            elif res['_Rarity'] > 3:
                # skipped.append(f'{res["_BaseId"]}-{res["_Name"]}')
                skipped.append(res["_Name"])
        outdata['High_Dragon_Print'] = WpConf.HDT_PRINT
        output = os.path.join(out_dir, 'wyrmprints.json')
        with open(output, 'w', newline='', encoding='utf-8') as fp:
            # json.dump(res, fp, indent=2, ensure_ascii=False)
            fmt_conf(outdata, f=fp)
        print('Skipped:', ','.join(skipped))

    def get(self, name):
        res = super().get(name, full_query=False)
        return self.process_result(res)

# class DrgConf(DragonData):
#     def process_result(self, res, exclude_falsy=True):
#         ab_lst = []
#         for i in (1, 2):
#             k = f'_Abilities{i}3'
#             if res.get(k):
#                 ab_lst.append(self.index['AbilityData'].get(res[k], full_query=True, exclude_falsy=exclude_falsy))
#         converted, skipped = convert_all_ability(ab_lst)

#         if (len(converted) == 1 or len(skipped) > 0) and res['_BaseId'] not in ALWAYS_KEEP:
#             return None

#         conf = {
#             'name': res['_Name'].strip(),
#             'att': res['_MaxAtk'],
#             'hp': res['_MaxHp'],
#             'ele': res['']
#             'icon': f'{res["_BaseId"]}_02',
#             'a': converted,
#             # 'skipped': skipped
#         }
#         return conf

#     def export_all_to_folder(self, out_dir='./out', ext='.json'):
#         all_res = self.get_all(exclude_falsy=True, where='_Rarity = 5')
#         check_target_path(out_dir)
#         outdata = {}
#         skipped = []
#         for res in tqdm(all_res, desc=os.path.basename(out_dir)):
#             conf = self.process_result(res, exclude_falsy=True)
#             if conf:
#                 outdata[snakey(res['_Name'])] = conf
#             elif res['_Rarity'] > 3:
#                 # skipped.append(f'{res["_BaseId"]}-{res["_Name"]}')
#                 skipped.append(res["_Name"])
#         outdata['High_Dragon_Print'] = WpConf.HDT_PRINT
#         output = os.path.join(out_dir, 'wyrmprints.json')
#         with open(output, 'w', newline='', encoding='utf-8') as fp:
#             # json.dump(res, fp, indent=2, ensure_ascii=False)
#             fmt_conf(outdata, f=fp)
#         print('Skipped:', ','.join(skipped))

#     def get(self, name):
#         res = super().get(name, full_query=False)
#         return self.process_result(res)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-a', help='_Name/_SecondName')
    parser.add_argument('-d', help='_Name')
    parser.add_argument('-wp', help='_Name')
    parser.add_argument('-s', help='_SkillId')
    parser.add_argument('-slv', help='Skill level')
    parser.add_argument('-f', help='_BurstAttackId')
    parser.add_argument('-fm', help='_BurstAttackMarker')
    # parser.add_argument('-x', '_UniqueComboId')
    parser.add_argument('-w', help='_Name')
    args = parser.parse_args()

    index = DBViewIndex()
    out_dir = os.path.join(pathlib.Path(__file__).parent.absolute(), '..', '..', 'dl', 'conf', 'gen')

    if args.s and args.slv:
        view = AdvConf(index)
        if args.a:
            view.get(args.a)
        view.eskill_counter = itertools.count()
        view.efs_counter = itertools.count()
        view.chara_skills = {}
        view.enhanced_fs = []
        view.chara_skill_loop = set()
        sconf, k = view.convert_skill('s1', 1, view.index['SkillData'].get(int(args.s), exclude_falsy=True), int(args.slv))
        sconf = {k: sconf}
        fmt_conf(sconf, f=sys.stdout)
        print('\n')
        pprint(view.chara_skills.keys())
        pprint(view.enhanced_fs)
    elif args.a:
        view = AdvConf(index)
        if args.a == 'all':
            view.export_all_to_folder(out_dir=out_dir)
        else:
            fmt_conf(view.get(args.a), f=sys.stdout)
    # elif args.d:
    #     view = DrgConf(index)
    #     if args.d == 'all':
    #         view.export_all_to_folder(out_dir=out_dir)
    #     else:
    #         wp = view.get(args.d)
    #         fmt_conf({snakey(wp['name']): wp}, f=sys.stdout)
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
    elif args.w:
        if args.w == 'base':
            view = WepConf(index)
            view.export_all_to_folder(out_dir=out_dir)
