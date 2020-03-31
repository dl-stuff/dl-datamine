import argparse
import json
import os
from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Union

from Abilities import get_ability_data, AbilityData, get_ability_and_references
from ActionConditions import ActionConditionData, get_action_condition_data
from Actions import get_text_label, \
    get_actions, Action, get_action_metadata
from CharacterMotion import AnimationClipData, get_animation_clip_data_by_id
from Common import run_common
from Mappings import ELEMENTS, WEAPON_TYPES
from Mode import get_modes, Mode
from Skills import Skill, get_skills
from UniqueCombo import get_unique_combos, UniqueCombo


@dataclass
class AdventurerModeData:
    mode_change_type: str
    mode_ids: List[int]
    original_combo_id: int
    mode1_combo_id: int
    mode2_combo_id: int
    fs_id: int
    dash_id: int


@dataclass
class AdventurerMode:
    mode_change_type: str
    modes: List[Optional[Mode]]
    original_combo: Optional[UniqueCombo]
    mode1_combo: Optional[UniqueCombo]
    mode2_combo: Optional[UniqueCombo]
    fs: Optional[Action]
    dash: Optional[Action]


@dataclass
class AdventurerData:
    id: int
    base_id: int
    variation_id: int
    name: str
    atk: int
    hp: int
    weapon_type: str
    rarity: int
    element: str
    ability_ids: Dict[str, int]
    skill1: int
    skill2: int
    modes: AdventurerModeData
    playable: bool
    cv_info: str
    cv_info_en: str
    profile_text: str
    unique_dragon_id: int

    def __hash__(self):
        return (self.id, self.name).__hash__()


@dataclass
class Adventurer:
    id: int
    base_id: int
    variation_id: int
    atk: int
    hp: int
    name: str
    weapon_type: str
    rarity: int
    element: str
    abilities: Dict[str, AbilityData]
    skill1: List[Skill]
    skill2: List[Skill]
    modes: AdventurerMode
    enhanced: Dict
    animation_clips: Dict[str, AnimationClipData]
    playable: bool
    cv_info: str
    cv_info_en: str
    profile_text: str
    unique_dragon_id: int

    def __hash__(self):
        return (self.id, self.name).__hash__()


MODE_CHANGE_TYPES = {
    0: 'Normal',
    1: 'Skill',
    2: 'Hud'
}


def adventurer_mode_data(data: Dict[str, Any]):
    return AdventurerModeData(
        mode_change_type=MODE_CHANGE_TYPES[data['_ModeChangeType']],
        mode_ids=[data['_ModeId1'], data['_ModeId2'], data['_ModeId3']],
        original_combo_id=data['_OriginCombo'],
        mode1_combo_id=data['_Mode1Combo'],
        mode2_combo_id=data['_Mode2Combo'],
        fs_id=data['_BurstAttack'],
        dash_id=data['_DashAttack'],
    )


def gather_adventurer_mode(mode_data: AdventurerModeData, actions: Dict[int, Action], combos: Dict[int, UniqueCombo],
                           modes: Dict[int, Mode]) -> AdventurerMode:
    return AdventurerMode(
        mode_change_type=mode_data.mode_change_type,
        modes=[modes.get(mid) for mid in mode_data.mode_ids],
        original_combo=combos.get(mode_data.original_combo_id),
        mode1_combo=combos.get(mode_data.mode1_combo_id),
        mode2_combo=combos.get(mode_data.mode2_combo_id),
        fs=actions.get(mode_data.fs_id),
        dash=actions.get(mode_data.dash_id)
    )


def get_skill_transforms(skill: Skill, skills: Dict[int, Skill]) -> List[Skill]:
    ids = [skill.id]
    s = skill
    while s.trans_skill_id > 0 and s.trans_skill_id not in ids:
        ids.append(s.trans_skill_id)
        s = skills[s.trans_skill_id]
    return [skills[sid] for sid in ids]


def get_adventurer_data(in_dir: str, label: Dict[str, str]) -> Dict[int, AdventurerData]:
    with open(os.path.join(in_dir, 'CharaData.json')) as f:
        data: List[Dict[str, Any]] = json.load(f)
        adventurers = {}
        for char in data:
            cid = char['_Id']
            if cid == 0:
                continue
            adventurers[cid] = AdventurerData(
                id=cid,
                base_id=char['_BaseId'],
                variation_id=char['_VariationId'],
                name=label.get(char['_SecondName'], label.get(char['_Name'], char['_Name'])),
                atk=sum([char[s] for s in char.keys() if s.startswith('_PlusAtk')]) + char['_McFullBonusAtk5'] + char[
                    '_AddMaxAtk1'],
                hp=sum([char[s] for s in char.keys() if s.startswith('_PlusHp')]) + char['_McFullBonusHp5'] + char[
                    '_AddMaxHp1'],
                weapon_type=WEAPON_TYPES[char['_WeaponType']],
                rarity=char['_Rarity'],
                element=ELEMENTS[char['_ElementalType']],
                ability_ids={s.replace('_Abilities', ''): char[s] for s in
                             char.keys() if s.startswith('_Abilities') and char[s]},
                skill1=char['_Skill1'],
                skill2=char['_Skill2'],
                modes=adventurer_mode_data(char),
                playable=bool(char['_IsPlayable']),
                cv_info=label.get(char['_CvInfo'], ''),
                cv_info_en=label.get(char['_CvInfoEn'], ''),
                profile_text=label.get(char['_ProfileText'], ''),
                unique_dragon_id=char['_UniqueDragonId']
            )
        return adventurers


def get_enhanced(subjects: List[Union[AbilityData, Skill, Action, ActionConditionData]], skills: Dict[int, Skill],
                 actions: Dict[int, Action], action_conditions: Dict[int, ActionConditionData],
                 abilities: Dict[int, AbilityData]) -> Dict:
    queue = subjects
    passed = set()
    s1 = set()
    s2 = set()
    fs = set()

    while queue:
        s = queue.pop()
        if s in passed:
            continue
        passed.add(s)
        if isinstance(s, AbilityData):
            for a in s.abilities:
                if a.ability_type == 14:
                    queue.append(action_conditions[a.ids[0]])
                if a.ability_type == 43:
                    queue.append(abilities[a.ids[0]])
        elif isinstance(s, Skill):
            queue.extend([i for j in s.abilities for i in j])
            queue.extend(s.actions)
            if isinstance(s.advanced_action, Action):
                queue.append(s.advanced_action)
        elif isinstance(s, Action):
            queue.extend(s.action_conditions.values())
        elif isinstance(s, ActionConditionData):
            if s.enhanced_skill1:
                n = skills[s.enhanced_skill1]
                s1.add(n)
                queue.append(n)
            if s.enhanced_skill2:
                n = skills[s.enhanced_skill2]
                s2.add(n)
                queue.append(n)
            if s.enhanced_fs:
                n = actions[s.enhanced_fs]
                fs.add(n)
                queue.append(n)
    return {'skill1': list(s1), 'skill2': list(s2), 'fs': list(fs)}


def gather_adventurer(adventurer_data: AdventurerData, skills: Dict[int, Skill], actions: Dict[int, Action],
                      action_conditions: Dict[int, ActionConditionData],
                      abilities: Dict[int, AbilityData], combos: Dict[int, UniqueCombo],
                      modes: Dict[int, Mode], animation_clips: Dict[int, Dict[str, AnimationClipData]]) -> Adventurer:
    s1 = skills.get(adventurer_data.skill1, None)
    s2 = skills.get(adventurer_data.skill2, None)
    s1 = [] if s1 is None else get_skill_transforms(s1, skills)
    s2 = [] if s2 is None else get_skill_transforms(s2, skills)
    ab = {k: get_ability_and_references(aid, abilities) for k, aid in adventurer_data.ability_ids.items()}
    flat_skills_abilities = [s for s in s1] + [s for s in s2] + [a for al in ab.values() for a in al]
    return Adventurer(
        id=adventurer_data.id,
        base_id=adventurer_data.base_id,
        variation_id=adventurer_data.variation_id,
        name=adventurer_data.name,
        atk=adventurer_data.atk,
        hp=adventurer_data.hp,
        weapon_type=adventurer_data.weapon_type,
        rarity=adventurer_data.rarity,
        element=adventurer_data.element,
        abilities=ab,
        skill1=s1,
        skill2=s2,
        modes=gather_adventurer_mode(adventurer_data.modes, actions, combos, modes),
        enhanced=get_enhanced(flat_skills_abilities, skills, actions, action_conditions, abilities),
        animation_clips=animation_clips.get(int(f'{adventurer_data.base_id}{adventurer_data.variation_id:02d}')),
        playable=adventurer_data.playable,
        cv_info=adventurer_data.cv_info,
        cv_info_en=adventurer_data.cv_info_en,
        profile_text=adventurer_data.profile_text,
        unique_dragon_id=adventurer_data.unique_dragon_id
    )


def get_adventurers(in_dir: str, label: Dict[str, str], skills: Dict[int, Skill], actions: Dict[int, Action],
                    action_conditions: Dict[int, ActionConditionData],
                    abilities: Dict[int, AbilityData], combos: Dict[int, UniqueCombo],
                    modes: Dict[int, Mode], animation_clips: Dict[int, Dict[str, AnimationClipData]]) \
        -> Dict[int, Adventurer]:
    return {
        adv_id: gather_adventurer(adv, skills, actions, action_conditions, abilities, combos, modes, animation_clips)
        for adv_id, adv in get_adventurer_data(in_dir, label).items()}


def run(in_dir: str) -> Dict[int, Adventurer]:
    label = get_text_label(in_dir)
    metadata = get_action_metadata(in_dir)
    actions = get_actions(in_dir, label, metadata)
    action_conditions = get_action_condition_data(in_dir, label)
    abilities = get_ability_data(in_dir, label)
    skills = get_skills(in_dir, label, actions, abilities)
    combos = get_unique_combos(in_dir, actions)
    modes = get_modes(in_dir, actions, skills, combos)
    animation_clips = get_animation_clip_data_by_id(os.path.join(in_dir, 'characters_motion'))
    return get_adventurers(in_dir, label, skills, actions, action_conditions, abilities, combos, modes,
                           animation_clips)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Adventurer Data.')
    parser.add_argument('-i', type=str, help='input dir (from extracting master and actions)', default='./extract')
    parser.add_argument('-o', type=str, help='output dir', default='./out/adventurers')
    args = parser.parse_args()
    run_common(args.o, [(f'{adv.id}_{adv.name}', adv) for adv in run(args.i).values()])
