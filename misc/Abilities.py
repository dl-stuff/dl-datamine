import argparse
import json
import os
from dataclasses import dataclass
from typing import List, Dict, Any, Callable

from Actions import get_text_label
from Common import run_common
from Mappings import AFFLICTION_TYPES, ABILITY_CONDITION_TYPES


STAT_ABILITIES = {
    2: 'strength',
    3: 'defense',
    4: 'skill_haste',
    8: 'shapeshift_time',
    10: 'attack_speed',
    12: 'fs_charge_rate'
}


ABILITY_TYPES: Dict[int, Callable[[List[int], str], str]] = {
    1: lambda ids, _: STAT_ABILITIES.get(ids[0], f'stat {ids[0]}'),
    2: lambda ids, _: f'affliction_res {AFFLICTION_TYPES.get(ids[0], ids[0])}',
    3: lambda ids, _: f'affliction_proc_rate {AFFLICTION_TYPES.get(ids[0], ids[0])}',
    4: lambda ids, _: f'tribe_res {ids[0]}',
    5: lambda ids, _: f'bane {ids[0]}',
    6: lambda ids, _: 'damage',
    7: lambda ids, _: f'critical_rate',
    8: lambda ids, _: f'recovery_potency',
    9: lambda ids, _: f'gauge_accelerator',
    11: lambda ids, _: f'striking_haste',
    14: lambda ids, _: f'action_condition {[i for i in ids if i]}',
    16: lambda ids, _: f'debuff_chance',
    17: lambda ids, _: f'skill_prep',
    18: lambda ids, _: f'buff_tim',
    20: lambda ids, _: f'punisher {AFFLICTION_TYPES.get(ids[0], ids[0])}',
    21: lambda ids, _: f'player_exp',
    25: lambda ids, _: f'cond_action_grant {ids[0]}',
    26: lambda ids, _: f'critical_damage',
    27: lambda ids, _: f'shapeshift_prep',
    30: lambda ids, _: f'specific_bane {ids[0]}',
    35: lambda ids, _: f'gauge_inhibitor',
    36: lambda ids, _: f'dragon damage',
    39: lambda ids, _: f'action_grant {ids[0]}',
    40: lambda _, s: f'gauge def/skillboost {s}',
    43: lambda ids, _: f'ability_ref {ids[0]}',
    44: lambda ids, _: f'action {ids[0]}',
    48: lambda ids, _: f'dragon_timer_decrease_rate',
    49: lambda ids, _: f'shapeshift_fill',
    51: lambda ids, _: f'random_buff {ids}',
    52: lambda ids, _: f'critical_rate',
    54: lambda _, s: f'combo_dmg_boost {s}',
    55: lambda ids, _: f'combo_time',
}


@dataclass
class AbilityPart:
    ability_type: int
    ids: List[int]
    id_str: str
    ability_limited_group: int
    target_action: int
    value: float
    description: str = None

    def __post_init__(self):
        if self.description is None:
            if self.ability_type in ABILITY_TYPES:
                self.description = ABILITY_TYPES[self.ability_type](self.ids, self.id_str)
            else:
                self.description = ''


@dataclass
class AbilityData:
    id: int
    event_id: int
    might: int
    name: str
    details: int
    view_ability_group_ids: List[int]
    ability_icon_name: str
    unit_type: str
    element_type: str
    weapon_type: str
    on_skill: int
    condition_type: str
    expire_condition: str
    condition_value: float
    probability: int
    occurrence_num: int
    max_count: int
    cool_time: float
    target_action: int
    shift_group_id: int
    head_text: str
    abilities: List[AbilityPart]

    def __hash__(self):
        return (self.id, self.name).__hash__()


def ability_part(data: Dict[str, Any], suffix: str) -> AbilityPart:
    return AbilityPart(
        ability_type=data[f'_AbilityType{suffix}'],
        ids=[data[f'_VariousId{suffix}a'], data[f'_VariousId{suffix}b'], data[f'_VariousId{suffix}c']],
        id_str=data[f'_VariousId{suffix}str'],
        ability_limited_group=data[f'_AbilityLimitedGroupId{suffix}'],
        target_action=data[f'_TargetAction{suffix}'],
        value=data[f'_AbilityType{suffix}UpValue']
    )


def get_ability_data(in_dir: str, label: Dict[str, str]) -> Dict[int, AbilityData]:
    with open(os.path.join(in_dir, 'AbilityData.json')) as f:
        data: List[Dict[str, Any]] = json.load(f)
        abilities = {}
        for ability in data:
            abilities[ability['_Id']] = AbilityData(
                id=ability['_Id'],
                event_id=ability['_EventId'],
                might=ability['_PartyPowerWeight'],
                name=label.get(ability['_Name'], ability['_Name']),
                details=label.get(ability['_Details'], ability['_Details']),
                view_ability_group_ids=[ability['_ViewAbilityGroupId1'], ability['_ViewAbilityGroupId2'],
                                        ability['_ViewAbilityGroupId3']],
                ability_icon_name=ability['_AbilityIconName'],
                unit_type=str(ability['_UnitType']),
                element_type=str(ability['_ElementalType']),
                weapon_type=str(ability['_WeaponType']),
                on_skill=ability['_OnSkill'],
                condition_type=ABILITY_CONDITION_TYPES.get(ability['_ConditionType'], str(ability['_ConditionType'])),
                expire_condition=str(ability['_ExpireCondition']),
                condition_value=ability['_ConditionValue'],
                probability=ability['_Probability'],
                occurrence_num=ability['_OccurenceNum'],
                max_count=ability['_MaxCount'],
                cool_time=ability['_CoolTime'],
                target_action=ability['_TargetAction'],
                shift_group_id=ability['_ShiftGroupId'],
                head_text=label.get(ability['_HeadText'], ability['_HeadText']),
                abilities=[ability_part(ability, suffix) for suffix in ['1', '2', '3'] if
                           ability[f'_AbilityType{suffix}']]
            )
        return abilities


def get_ability_and_references(ability_id: int, abilities: Dict[int, AbilityData]) -> List[AbilityData]:
    if ability_id not in abilities or ability_id == 0:
        return []
    queue = [abilities[ability_id]]
    referenced = []
    while queue:
        ab = queue.pop()
        if ab not in referenced:
            referenced.append(ab)
            for part in ab.abilities:
                if part.ability_type == 43:
                    queue.append(abilities[part.ids[0]])
    return referenced


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Extract ability data.')
    parser.add_argument('-i', type=str, help='input dir', default='./extract')
    parser.add_argument('-o', type=str, help='output dir', default='./out/abilities')
    args = parser.parse_args()
    run_common(args.o, [(f'{ab.id}_{ab.name}', ab) for ab in get_ability_data(args.i, get_text_label(args.i)).values()])
