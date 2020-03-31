import argparse
import json
import os
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Union

from Abilities import AbilityData, get_ability_and_references
from Actions import Action, get_text_label, get_action_and_associated
from Common import run_common


@dataclass
class SkillData:
    id: int
    name: str
    icons: List[str]
    descriptions: List[str]
    sp: int
    sp_lv2: int
    action_ids: List[int]
    advanced_action_id: int
    ability_ids: List[int]
    trans_skill_id: int
    tension: bool

    def __hash__(self):
        return (self.id, self.name).__hash__()


@dataclass
class Skill:
    id: int
    name: str
    icons: List[str]
    descriptions: List[str]
    sp: int
    sp_lv2: int
    actions: List[Action]
    advanced_action: Union[Action, int]
    abilities: List[List[AbilityData]]
    trans_skill_id: int
    tension: bool

    def __hash__(self):
        return (self.id, self.name).__hash__()


def get_skill_data(in_dir: str, label: Dict[str, str]) -> Dict[int, SkillData]:
    with open(os.path.join(in_dir, 'SkillData.json')) as f:
        data: List[Dict[str, Any]] = json.load(f)
        skills = {}
        for skill in data:
            action_ids = [aid for aid in
                          [skill['_ActionId1'], skill['_ActionId2'], skill['_ActionId3'], skill['_ActionId4']] if
                          aid > 0]
            advanced_action_id = skill['_AdvancedActionId1']
            skills[skill['_Id']] = SkillData(
                id=skill['_Id'],
                name=label.get(skill['_Name'], skill['_Name']),
                icons=[skill['_SkillLv1IconName'], skill['_SkillLv2IconName'], skill['_SkillLv3IconName'],
                       skill['_SkillLv4IconName']],
                descriptions=[desc for desc in
                              [label.get(skill['_Description1'], None), label.get(skill['_Description2'], None),
                               label.get(skill['_Description3'], None), label.get(skill['_Description4'], None)] if
                              desc],
                sp=skill['_Sp'],
                sp_lv2=skill['_SpLv2'],
                action_ids=action_ids,
                advanced_action_id=advanced_action_id,
                ability_ids=[skill[n] for n in
                             ['_Ability1', '_Ability2', '_Ability3', '_Ability4']],
                trans_skill_id=skill['_TransSkill'],
                tension=bool(skill['_IsAffectedByTension'])
            )
        return skills


def gather_skill(skill_data: SkillData, actions: Dict[int, Action], abilities: Dict[int, AbilityData]):
    return Skill(
        id=skill_data.id,
        name=skill_data.name,
        icons=skill_data.icons,
        descriptions=skill_data.descriptions,
        sp=skill_data.sp,
        sp_lv2=skill_data.sp_lv2,
        actions=[a for acts in [get_action_and_associated(actions[aid], actions) for aid in skill_data.action_ids if
                                aid in actions.keys()] for a in acts],
        advanced_action=actions.get(skill_data.advanced_action_id, skill_data.advanced_action_id),
        abilities=[get_ability_and_references(n, abilities) for n in
                   skill_data.ability_ids],
        trans_skill_id=skill_data.trans_skill_id,
        tension=skill_data.tension
    )


def gather_skills(skill_data: Dict[int, SkillData], actions: Dict[int, Action],
                  abilities: Dict[int, AbilityData]):
    return {i: gather_skill(s, actions, abilities) for i, s in skill_data.items()}


def get_skills(in_dir: str, label: Dict[str, str], actions: Dict[int, Action], abilities: Dict[int, AbilityData]) -> \
        Dict[int, Skill]:
    return gather_skills(get_skill_data(in_dir, label), actions, abilities)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Adventurer Data.')
    parser.add_argument('-i', type=str, help='input dir (from extracting master and actions)', default='./extract')
    parser.add_argument('-o', type=str, help='output dir', default='./out/skills')
    args = parser.parse_args()
    run_common(args.o, [(f'{skill.id}_{skill.name}', skill) for skill in
                        get_skill_data(args.i, get_text_label(args.i)).values()])
