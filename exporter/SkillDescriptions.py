import re
from collections import Counter, defaultdict
from tabulate import tabulate

from math import ceil

from loader.Database import DBViewIndex, DBManager, DBView
from exporter.Shared import SkillData, PlayerAction, ActionParts
from exporter.Mappings import AFFLICTION_TYPES

SKILL_DESC_ELEMENT = re.compile(r'(flame|water|wind|light|shadow)(?:-based)? damage to (.+?)[\.,](.*)')
ELEMENTAL_FORMAT = {
    'flame': '{{{{ColorText|Red|{mod:.1%}}}}}',
    'water': '{{{{ColorText|Blue|{mod:.1%}}}}}',
    'wind': '{{{{ColorText|Green|{mod:.1%}}}}}',
    'light': '{{{{ColorText|Yellow|{mod:.1%}}}}}',
    'shadow': '{{{{ColorText|Purple|{mod:.1%}}}}}',
    'neutral': "'''{mod:.1%}'''",
    None: '{mod:.1%}'
}
NUMBER_FORMAT = "'''{mod}'''"
PERCENT_FORMAT = "'''{mod}%'''"
KS_PAST_TENSE = {
    'Poison': 'Poisoned',
    'Burn': 'Burning',
    'Freeze': 'Frozen',
    'Paralysis': 'Paralyzed',
    'Blind': 'Blinded',
    'Stun': 'Stunned',
    'Curse': 'Cursed',
    'UNKNOWN08': 'Bolbed',
    'Bog': 'Bogged',
    'Sleep': 'Sleeping',
    'Frostbite': 'Frostbitten',
    'Def Down': 'Defense reduced',
    'Dispel': 'Buffed',
    'Break': 'Broken'
}
CRISIS = 'crisis'
ALL = 'all'
ALL_CRISIS = 'all_crisis'
TARGET_GROUP = {
    1: 'user',
    2: 'all allies',
    3: 'enemy',
    6: 'all allies',
    7: 'the team member most in need'
}
ROMAN = {
    1: 'I',
    2: 'II',
    3: 'III'
}

def def_down_format(act_cond, percent_fmt, number_fmt, wiki_format):
    effect = 'reduces their defense'
    try:
        value = float_formatter(percent_fmt, -round(act_cond['_RateDefense']*100))
    except:
        value = float_formatter(percent_fmt, -round(act_cond['_RateDefenseB']*100))
    try:
        duration = float_formatter(number_fmt, act_cond['_DurationSec'])
    except:
        duration = 0
    rate = float_formatter(percent_fmt, act_cond['_Rate'])
    return f'{effect} by {value} for {duration} seconds with {rate} base chance'

def atk_down_format(act_cond, percent_fmt, number_fmt, wiki_format):
    effect = 'reduces their strength'
    value = float_formatter(percent_fmt, -round(act_cond['_RateAttack']*100))
    duration = float_formatter(number_fmt, act_cond['_DurationSec'])
    rate = float_formatter(percent_fmt, act_cond['_Rate'])
    return f'{effect} by {value} for {duration} seconds with {rate} base chance'

def cc_format(act_cond, percent_fmt, number_fmt, wiki_format):
    name = act_cond['_Type'].lower()
    name_fmt = name if not wiki_format else f'[[Conditions#Afflictions|{name}]]'
    duration = float_formatter(number_fmt, act_cond['_DurationSec'])
    try:
        if act_cond['_MinDurationSec'] != act_cond['_DurationSec']:
            duration = float_formatter(number_fmt, str(act_cond['_MinDurationSec'])+'-'+str(act_cond['_DurationSec']))
    except:
        pass
    rate = float_formatter(percent_fmt, act_cond['_Rate'])
    return f'inflicts {name_fmt} for {duration} seconds with {rate} base chance'

def regen_self_format(act_cond, percent_fmt, number_fmt, wiki_format):
    duration = float_formatter(number_fmt, act_cond['_DurationSec'])
    value = float_formatter(percent_fmt, act_cond['_RegenePower'])
    interval = float_formatter(number_fmt, round(act_cond['_SlipDamageIntervalSec'], 1))
    rec_potency = '[[Healing Formula|recovery potency]]' if wiki_format else 'recovery potency'
    return f'applies regeneration to the user for {duration} seconds, healing with {value} {rec_potency} every {interval} seconds'

def regen_team_format(act_cond, percent_fmt, number_fmt, wiki_format):
    duration = float_formatter(number_fmt, act_cond['_DurationSec'])
    value = float_formatter(percent_fmt, act_cond['_RegenePower'])
    interval = float_formatter(number_fmt, round(act_cond['_SlipDamageIntervalSec'], 1))
    rec_potency = '[[Healing Formula|recovery potency]]' if wiki_format else 'recovery potency'
    return f'applies regeneration to all allies for {duration} seconds, healing with {value} {rec_potency} every {interval} seconds'

ACT_COND_FMT = {
    1: [
        regen_self_format
    ],
    2: [
        regen_team_format
    ],
    3: [
        def_down_format,
        atk_down_format,
        cc_format
    ],
}

def float_formatter(fmt, modifier):
    return fmt.format(mod=modifier).replace('.0', '')

def all_killer_state(killer_states):
    return ' and '.join([KS_PAST_TENSE.get(ks, ks).lower() for ks in killer_states[:-1] if ks not in (CRISIS, ALL, ALL_CRISIS)])

def describe_skill(data, wiki_format=False, extra_info=None):
    og_desc_by_level = {}
    gen_desc_by_level = {}
    seen_id = {data['_Id']}
    related_skills = {}
    targets = 'enemies'
    element = 'neutral'
    #'_ActionId2', '_ActionId3', '_ActionId4' deal with these later
    if '_AdvancedSkillLv1' in data and data['_AdvancedSkillLv1']:
        adv_lv = data['_AdvancedSkillLv1']
        act_desc_iter = (('_ActionId1', lambda lv: 0 < lv < adv_lv), ('_AdvancedActionId1', lambda lv: adv_lv <= lv))
    else:
        act_desc_iter = [('_ActionId1', lambda lv: 0 < lv < 5)]
    for act_id, check_lv in act_desc_iter:
        action = data[act_id]
        if not action or not isinstance(action, dict):
            continue
        hit_attr_counter = Counter()
        hit_attr_by_level = defaultdict(lambda: {})
        action_parts = [action['_Parts']] if isinstance(action['_Parts'], dict) else action['_Parts']
        for part in action_parts:
            for label in ActionParts.HIT_LABELS:
                if label in part and part[label]:
                    base_label = None
                    if isinstance(part[label], list):
                        part_list = part[label]
                    elif isinstance(part[label], dict):
                        part_list = [part[label]]
                    else:
                        continue
                    for ha in part_list:
                        ha_id = ha['_Id']
                        res = ActionParts.LV_SUFFIX.match(ha_id)
                        if res:
                            base_label, level = res.groups()
                            level = int(level)
                            if check_lv(level):
                                hit_attr_by_level[level][base_label] = ha
                    if base_label:
                        if '_generateNum' in part:
                            count = part['_generateNum']
                        elif '_bulletNum' in part:
                            count = part['_bulletNum']
                        elif '_duration' in part:
                            count = ceil(part['_duration'] / part['_collisionHitInterval'])
                        else:
                            count = 1
                        hit_attr_counter[base_label] += count
        for level, v1 in hit_attr_by_level.items():
            if len(v1) == 0:
                continue
            desc_id = f'_Description{level}'
            hit_mod_counter = Counter()
            hit_text = defaultdict(lambda: [])
            hit_dot = {}
            dot_text = set()
            effect_text = set()
            dmg_fmt = ELEMENTAL_FORMAT[None]
            number_fmt = NUMBER_FORMAT if wiki_format else '{mod}'
            percent_fmt = PERCENT_FORMAT if wiki_format else '{mod}%'
            
            original_desc = None
            if extra_info:
                targets = extra_info['targets']
                element = extra_info['element']
            if desc_id in data and data[desc_id]:
                original_desc = data[desc_id].replace('\\n', ' ')
                res = SKILL_DESC_ELEMENT.search(original_desc)
                if res:
                    targets = res.group(2)
                    element = res.group(1)
            if wiki_format:
                dmg_fmt = ELEMENTAL_FORMAT[element]
            og_desc_by_level[level] = original_desc
            killer_states = set()
            act_cond_effects = defaultdict(lambda: [])
            dp_gain = 0
            rcv_value = 0
            rcv_target = None
            # first pass
            for base_label, hit_attr in v1.items():
                try:
                    if hit_attr['_TargetGroup'] == 3:
                        hit_count = hit_attr_counter[base_label]
                        modifier = hit_attr['_DamageAdjustment']
                        # hit_text[None].append(f'{hit_count} hit{"s" if hit_count > 1 else ""} of {dmg_fmt.format(mod=modifier)}')
                        hit_mod_counter[modifier] += hit_count
                        for ks in ('_KillerState1', '_KillerState2', '_KillerState3'):
                            if ks in hit_attr:
                                killer_states.add(hit_attr[ks])
                        if '_CrisisLimitRate' in hit_attr and hit_attr['_CrisisLimitRate'] > 1:
                            killer_states.add(CRISIS)
                except:
                    pass
                try:
                    dp_gain = max(hit_attr['_AdditionRecoveryDpLv1'], dp_gain)
                except:
                    pass
                try:
                    if hit_attr['_RecoveryValue'] > rcv_value:
                        rcv_value = hit_attr['_RecoveryValue']
                        rcv_target = TARGET_GROUP.get(hit_attr['_TargetGroup'], hit_attr['_TargetGroup'])
                except:
                    pass
                try:
                    act_cond = hit_attr['_ActionCondition1']
                    for es in ('_EnhancedSkill1', '_EnhancedSkill2'):
                        if es in act_cond and isinstance(act_cond[es], dict):
                            related_skills[act_cond[es]['_Id']] = act_cond[es]
                    if '_Type' in act_cond and act_cond['_Type'] in AFFLICTION_TYPES.values() and '_SlipDamagePower' in act_cond:
                        name = act_cond['_Type'].lower()
                        name_fmt = name if not wiki_format else f'[[Conditions#Afflictions|{name}]]'
                    elif '_Text' in act_cond and act_cond['_Text'] == 'Bleeding':
                        name = 'bleeding'
                        name_fmt = name if not wiki_format else f'[[Conditions#Special_Effects|bleeding]]'
                    else:
                        try:
                            act_cond_effects[hit_attr['_TargetGroup']].append(hit_attr['_ActionCondition1'])
                        except:
                            act_cond_effects[0].append(hit_attr['_ActionCondition1'])
                        continue
                    modifier = act_cond['_SlipDamagePower']
                    interval = int(act_cond['_SlipDamageIntervalSec'] * 10)/10
                    duration = int(act_cond['_DurationSec'] * 10)/10
                    rate = int(act_cond['_Rate'])
                    hit_dot[base_label] = (name_fmt, modifier, interval, duration, rate)
                    dot_text.add(f'inflicts {name_fmt} for {float_formatter(number_fmt, duration)} seconds - dealing {float_formatter(dmg_fmt, modifier)} damage every {float_formatter(number_fmt, interval)} seconds - with {float_formatter(percent_fmt, rate)} base chance')
                except:
                    pass

            hit_text = []
            for modifier, hit_count in hit_mod_counter.items():
                hit_text.append(f'{hit_count} hit{"s" if hit_count > 1 else ""} of {float_formatter(dmg_fmt, modifier)}')

            description = ''
            if len(hit_text) > 0:
                description = 'Deals ' + ' and '.join(hit_text) + f' {element} damage to {targets}'
            elif rcv_value > 0:
                description = f'Restores HP to {rcv_target} with {float_formatter(percent_fmt, rcv_value)} '
                if wiki_format:
                    description += '[[Healing Formula|recovery potency]]'
                else:
                    description += 'recovery potency'
            if not description:
                continue

            if dp_gain > 0:
                # raises the dragon gauge by 3% if the attack connects
                effect_text.add(f'raises the dragon gauge by {float_formatter(percent_fmt, dp_gain/10)} if the attack connects')

            if act_cond_effects:
                for target, act_cond_effect_list in act_cond_effects.items():
                    if target not in ACT_COND_FMT:
                        continue
                    for act_cond in act_cond_effect_list:
                        # succeed = False
                        for fmt in ACT_COND_FMT[target]:
                            try:
                                effect_text.add(fmt(act_cond, percent_fmt, number_fmt, wiki_format))
                                # succeed = True
                                break
                            except:
                                pass
                        # if not succeed:
                        #     print(data['_Name'], act_cond)
            
            effect_text = list(effect_text)+list(dot_text)
            if len(effect_text) > 0:
                last_effect = effect_text[-1]
                prev_effects = effect_text[:-1]
                if prev_effects:
                    description += ', ' + ', '.join(prev_effects) + ', and ' + last_effect
                else:
                    description += ' and ' + last_effect

            # killer states pass
            if len(killer_states) > 1:
                killer_states = sorted(list(killer_states), key=lambda ks: ks==CRISIS)
                if CRISIS in killer_states:
                    if len(killer_states) > 2:
                        killer_states.append(ALL)
                    killer_states.append(ALL_CRISIS)
                else:
                    killer_states.append(ALL)
            
            description += ('.\n' if not wiki_format else '. ')
            for ks in killer_states:
                hit_mod_counter = Counter()
                hit_text = []
                dot_text = set()
                for base_label, hit_attr in v1.items():
                    current_ks = [hit_attr[ks] for ks in ('_KillerState1', '_KillerState2', '_KillerState3') if ks in hit_attr]
                    if '_DamageAdjustment' in hit_attr:
                        hit_count = hit_attr_counter[base_label]
                        if ks == ALL_CRISIS:
                            killer_modifier = 1
                            if '_KillerStateDamageRate' in hit_attr and hit_attr['_KillerStateDamageRate']:
                                killer_modifier *= hit_attr['_KillerStateDamageRate']
                            if '_CrisisLimitRate' in hit_attr and hit_attr['_CrisisLimitRate']:
                                killer_modifier *= hit_attr['_CrisisLimitRate']
                        elif ks == CRISIS and '_CrisisLimitRate' in hit_attr:
                            killer_modifier = hit_attr['_CrisisLimitRate']
                        elif (ks == ALL or ks in current_ks) and '_KillerStateDamageRate' in hit_attr and hit_attr['_KillerStateDamageRate']:
                            killer_modifier = hit_attr['_KillerStateDamageRate']
                        else:
                            killer_modifier = 1
                        modifier = hit_attr['_DamageAdjustment'] * killer_modifier
                        # hit_text[ks].append(f'{hit_count} hit{"s" if hit_count > 1 else ""} of {dmg_fmt.format(mod=modifier)}')
                        hit_mod_counter[modifier] += hit_count
                        if base_label in hit_dot:
                            modifier = hit_dot[base_label][1] * killer_modifier
                            dot_text.add(f'{float_formatter(dmg_fmt, modifier)} from {hit_dot[base_label][0]}')

                for modifier, hit_count in hit_mod_counter.items():
                    hit_text.append(f'{hit_count} hit{"s" if hit_count > 1 else ""} of {float_formatter(dmg_fmt, modifier)}')

                if ks == ALL:
                    all_ks = all_killer_state(killer_states)
                    description += f'{all_ks.capitalize()} foes take ' + ' and '.join(hit_text) + f' {element} damage'
                elif ks == CRISIS:
                    description += f'The lower the user\'s HP, the more damage this skill deals. This increase caps at ' + ' and '.join(hit_text) + f' {element} damage'
                elif ks == ALL_CRISIS:
                    all_ks = all_killer_state(killer_states)
                    description += f'For {all_ks} foes, the cap is instead ' + ' and '.join(hit_text) + f' {element} damage'
                else:
                    description += f'{KS_PAST_TENSE.get(ks, ks)} foes take ' + ' and '.join(hit_text) + f' {element} damage'
                if len(dot_text) > 0:
                    description += (', and ' if len(hit_text) > 0 else '') + ' and '.join(dot_text)
                description += '.'
            gen_desc_by_level[level] = description

        # recursion
        # describe_skill(data, wiki_format=False, extra_info=None)
        if not extra_info:
            extra_info = {
                'targets': targets,
                'element': element
            }
        for s in related_skills.values():
            c_gen_disc, _, c_seen_id = describe_skill(s, wiki_format=wiki_format, extra_info=extra_info)
            seen_id.update(c_seen_id)
            for lv, d2 in c_gen_disc.items():
                try:
                    gen_desc_by_level[lv] += ' ' + d2
                except:
                    gen_desc_by_level[lv] = d2

        if '_TransSkill' in data and isinstance(data['_TransSkill'], dict):
            shift_gen_disc = [gen_desc_by_level]
            for s in data['_TransSkill'].values():
                if isinstance(s, dict):
                    c_gen_disc, _, c_seen_id = describe_skill(s, wiki_format=wiki_format, extra_info=extra_info)
                    seen_id.update(c_seen_id)
                    shift_gen_disc.append(c_gen_disc)
            for idx, gen_disc in enumerate(shift_gen_disc):
                for lv, d in gen_disc.items():
                    gen_disc[lv] = f'Shift {ROMAN[idx+1]}: {d}'
                    if idx >= 1:
                        gen_desc_by_level[lv] += '\n' + gen_disc[lv]

    return gen_desc_by_level, og_desc_by_level, seen_id

if __name__ == '__main__':
    index = DBViewIndex()
    view = SkillData(index)

    specific_id = None

    if specific_id:
        skill = view.get(specific_id)
        skill_name = skill['_Name']
        skill_id = str(skill['_Id'])
        gen_disc, og_disc, _ = describe_skill(skill, wiki_format=True)
        for lv, d in gen_disc.items():
            o = og_disc[lv]
            print(f'{skill_id} - {skill_name} LV{lv}')
            print(f'Original:\n{o}')
            print(f'Generated:\n{d}\n')
    else:
        all_seen_id = set()
        skills = view.get_all(exclude_falsy=True)
        with open('DESC_F.txt', 'w') as f_desc, open('DESC_N.txt', 'w') as n_desc:
            f_desc.write('__NOTOC__\n')
            for skill in skills:
                try:
                    skill_name = skill['_Name']
                except:
                    skill_name = '???'
                skill_id = skill['_Id']
                if skill_id in all_seen_id:
                    print(f'Skip {skill_name} - {skill_id}')
                    continue
                skill = view.process_result(skill)
                gen_disc, og_disc, seen_id = describe_skill(skill, wiki_format=True)
                all_seen_id.update(seen_id)
                if gen_disc:
                    f_desc.write(f'=== {skill_id} - {skill_name} ===')
                    for lv, d in gen_disc.items():
                        try:
                            o = og_disc[lv]
                        except:
                            o = '???'
                        f_desc.write(f'\n==== LV{lv} ====\n<p><div><b>Original:</b><br/>\n{o}\n</div>\n<div><b>Wiki:</b><br/>\n{{{{#cargo_query:tables=Skills|fields=Description{lv}|where=SkillId={skill_id}}}}}</div>\n<div><b>Generated:</b><br/>\n{d}\n</div>\n</p>')
                    f_desc.write('</div>\n\n')
                elif skill_name:
                    n_desc.write(str(skill_id))
                    n_desc.write(' - ')
                    n_desc.write(skill_name)
                    n_desc.write(': ')
                    for lv in range(4, 0, -1):
                        k = f'_Description{lv}'
                        if k in skill and skill[k]:
                            n_desc.write(skill[k])
                            break
                    n_desc.write('\n')
