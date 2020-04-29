import re
from collections import Counter, defaultdict
from tabulate import tabulate

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
    'neutral': '{{{{ColorText|Black|{mod:.1%}}}}}',
}
NUMBER_FORMAT = "'''{}'''"
PERCENT_FORMAT = "'''{}%'''"
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

def dmg_formatter(dmg_fmt, modifier):
    return dmg_fmt.format(mod=modifier).replace('.0', '')

def describe_skill(data, wiki_format=False):
    descriptions_by_level = {}
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
                        count = 1
                        if '_generateNum' in part:
                            count = part['_generateNum']
                        elif '_bulletNum' in part:
                            count = part['_bulletNum']
                        hit_attr_counter[base_label] += count
        for level, v1 in hit_attr_by_level.items():
            if len(v1) == 0:
                continue
            desc_id = f'_Description{level}'
            hit_mod_counter = Counter()
            hit_text = defaultdict(lambda: [])
            hit_dot = {}
            dot_text = set()
            dmg_fmt = ELEMENTAL_FORMAT['neutral'] if wiki_format else '{mod:.2%}'
            number_fmt = NUMBER_FORMAT if wiki_format else '{}'
            percent_fmt = PERCENT_FORMAT if wiki_format else '{}%'
            targets = 'enemies'
            element = 'UNKNOWN'
            original_desc = '???'
            if desc_id in data and data[desc_id]:
                original_desc = data[desc_id].replace('\\n', ' ')
                res = SKILL_DESC_ELEMENT.search(original_desc)
                if res:
                    element = res.group(1)
                    if wiki_format:
                        dmg_fmt = ELEMENTAL_FORMAT[res.group(1)]
                    targets = res.group(2)
            killer_states = set()
            # first pass
            for base_label, hit_attr in v1.items():
                if '_DamageAdjustment' in hit_attr:
                    hit_count = hit_attr_counter[base_label]
                    modifier = hit_attr['_DamageAdjustment']
                    # hit_text[None].append(f'{hit_count} hit{"s" if hit_count > 1 else ""} of {dmg_fmt.format(mod=modifier)}')
                    hit_mod_counter[modifier] += hit_count
                    for ks in ('_KillerState1', '_KillerState2', '_KillerState3'):
                        if ks in hit_attr:
                            killer_states.add(hit_attr[ks])
                if '_ActionCondition1' in hit_attr:
                    act_cond = hit_attr['_ActionCondition1']
                    if '_Type' in act_cond and act_cond['_Type'] in AFFLICTION_TYPES.values() and '_SlipDamagePower' in act_cond:
                        name = act_cond['_Type'].lower()
                        name_fmt = name if not wiki_format else f'[[Conditions#Afflictions|{name}]]'
                    elif '_Text' in act_cond and act_cond['_Text'] == 'Bleeding':
                        name = 'bleeding'
                        name_fmt = name if not wiki_format else f'[[Conditions#Special_Effects|bleeding]]'
                    else:
                        continue
                    modifier = act_cond['_SlipDamagePower']
                    interval = int(act_cond['_SlipDamageIntervalSec'] * 10)/10
                    duration = int(act_cond['_DurationSec'] * 10)/10
                    rate = int(act_cond['_Rate'])
                    hit_dot[base_label] = (name_fmt, modifier, interval, duration, rate)
                    dot_text.add(f'inflicts {name_fmt} for {duration} seconds - dealing {dmg_formatter(dmg_fmt, modifier)} damage every {number_fmt.format(interval)} seconds - with {percent_fmt.format(rate)} base chance')

            hit_text = []
            for modifier, hit_count in hit_mod_counter.items():
                hit_text.append(f'{hit_count} hit{"s" if hit_count > 1 else ""} of {dmg_formatter(dmg_fmt, modifier)}')

            if len(hit_text) == 0:
                continue
            description = 'Deals ' + ' and '.join(hit_text) + f' {element} damage to {targets}'
            if len(dot_text) > 0:
                description += (', and ' if len(hit_text) > 0 else '') + ' and '.join(dot_text)

            # killer states pass
            for ks in killer_states:
                hit_mod_counter = Counter()
                hit_text = []
                dot_text = set()
                for base_label, hit_attr in v1.items():
                    current_ks = [hit_attr[ks] for ks in ('_KillerState1', '_KillerState2', '_KillerState3') if ks in hit_attr]
                    if '_DamageAdjustment' in hit_attr:
                        hit_count = hit_attr_counter[base_label]
                        killer_modifier = 1 if ks not in current_ks else hit_attr['_KillerStateDamageRate']
                        modifier = hit_attr['_DamageAdjustment'] * killer_modifier
                        # hit_text[ks].append(f'{hit_count} hit{"s" if hit_count > 1 else ""} of {dmg_fmt.format(mod=modifier)}')
                        hit_mod_counter[modifier] += hit_count
                        if base_label in hit_dot:
                            modifier = hit_dot[base_label][1] * killer_modifier
                            dot_text.add(f'{dmg_formatter(dmg_fmt, modifier)} from {hit_dot[base_label][0]}')
                description += ('.\n' if not wiki_format else '.<br/>')

                for modifier, hit_count in hit_mod_counter.items():
                    hit_text.append(f'{hit_count} hit{"s" if hit_count > 1 else ""} of {dmg_formatter(dmg_fmt, modifier)}')

                description += f'{KS_PAST_TENSE.get(ks, ks)} foes take ' + ' and '.join(hit_text) + f' {element} damage'
                if len(dot_text) > 0:
                    description += (', and ' if len(hit_text) > 0 else '') + ' and '.join(dot_text)
            description += '.'
            descriptions_by_level[level] = (original_desc, description)
    return descriptions_by_level

if __name__ == '__main__':
    index = DBViewIndex()
    view = SkillData(index)

    specific_id = None

    if specific_id:
        skill = view.get(specific_id)
        skill_name = skill['_Name']
        skill_id = str(skill['_Id'])
        desc = describe_skill(skill, wiki_format=True)
        for lv, tpl in desc.items():
            o, d = tpl
            print(f'{skill_id} - {skill_name} LV{lv}')
            print(f'Original:\n{o}')
            print(f'Generated:\n{d}\n')
    else:
        skills = view.get_all(exclude_falsy=True)
        with open('DESC_F.txt', 'w') as f_desc, open('DESC_N.txt', 'w') as n_desc:
            for skill in skills:
                skill = view.process_result(skill)
                try:
                    skill_name = skill['_Name']
                except:
                    continue
                skill_id = str(skill['_Id'])
                desc = describe_skill(skill, wiki_format=True)
                if desc:
                    f_desc.write(f'<div><h3>{skill_id} - {skill_name}</h3>')
                    for lv, tpl in desc.items():
                        o, d = tpl
                        # f_desc.write(f'<div><h5>{skill_id} - {skill_name} LV{lv}</h5>')
                        # f_desc.write(f'<h6>Original:</h6><p>{o}</p>')
                        # f_desc.write(f'<h6>Generated:</h6><p>{d}</p>')
                        f_desc.write(f'<p>LV{lv}\n<div><b>Original:</b><br/>\n{o}</div>\n<div><b>Wiki:</b><br/>\n{{{{#cargo_query:tables=Skills|fields=Description{lv}|where=SkillId={skill_id}}}}}</div>\n<div><b>Generated:</b><br/>\n{d}</div>\n</p>')
                    f_desc.write('</div>\n\n')
                elif skill_name:
                    n_desc.write(skill_id)
                    n_desc.write(' - ')
                    n_desc.write(skill_name)
                    n_desc.write(': ')
                    for lv in range(4, 0, -1):
                        k = f'_Description{lv}'
                        if k in skill and skill[k]:
                            n_desc.write(skill[k])
                            break
                    n_desc.write('\n')
