import json
import os
from dataclasses import dataclass
from typing import Dict, List, Any, Optional

from Actions import Action, get_action_and_associated
from Skills import Skill
from UniqueCombo import UniqueCombo


@dataclass
class ModeData:
    id: int
    action_id: int
    unique_combo_id: int
    skill1_id: int
    skill2_id: int
    effect_name: str
    effect_trigger: int
    icon_name: str

    def __hash__(self):
        return (self.id, self.action_id).__hash__()


@dataclass
class Mode:
    id: int
    action: Optional[Action]
    unique_combo: UniqueCombo
    skill1: Optional[Skill]
    skill2: Optional[Skill]
    effect_name: str
    effect_trigger: int
    icon_name: str

    def __hash__(self):
        return (self.id, self.action).__hash__()


def get_mode_data(in_dir: str) -> Dict[int, ModeData]:
    with open(os.path.join(in_dir, 'CharaModeData.json')) as f:
        data: List[Dict[str, Any]] = json.load(f)
        modes = {}
        for mode in data:
            modes[mode['_Id']] = ModeData(
                id=mode['_Id'],
                action_id=mode['_ActionId'],
                unique_combo_id=mode['_UniqueComboId'],
                skill1_id=mode['_Skill1Id'],
                skill2_id=mode['_Skill2Id'],
                effect_name=mode['_EffectName'],
                effect_trigger=mode['_EffectTrigger'],
                icon_name=mode['_IconName']
            )
        return modes


def gather_mode(mode_data: ModeData, actions: Dict[int, Action], skills: Dict[int, Skill],
                unique_combos: Dict[int, UniqueCombo]) -> Mode:
    return Mode(
        id=mode_data.id,
        action=actions.get(mode_data.action_id) if mode_data.action_id else None,
        unique_combo=unique_combos[mode_data.unique_combo_id],
        skill1=skills.get(mode_data.skill1_id) if mode_data.skill1_id else None,
        skill2=skills.get(mode_data.skill2_id) if mode_data.skill1_id else None,
        effect_name=mode_data.effect_name,
        effect_trigger=mode_data.effect_trigger,
        icon_name=mode_data.icon_name
    )


def get_modes(in_dir: str, actions: Dict[int, Action], skills: Dict[int, Skill],
              unique_combos: Dict[int, UniqueCombo]) -> Dict[int, Mode]:
    return {mode_id: gather_mode(mode_data, actions, skills, unique_combos) for mode_id, mode_data in
            get_mode_data(in_dir).items() if mode_id}
