import json
import os
from dataclasses import dataclass
from typing import Dict, List, Any

from Actions import Action, get_action_and_associated

SHIFT_CONDITION_TYPES = {
    0: 'None',
    1: 'Combo',
    2: 'Buff'
}


@dataclass
class UniqueComboData:
    id: int
    action_id: int
    max_combo_num: int
    shift_condition_type: str
    condition_args: int
    buff_hit_attribute: str

    def __hash__(self):
        return (self.id, self.action_id).__hash__()


@dataclass
class UniqueCombo:
    id: int
    actions: List[Action]
    max_combo_num: int
    shift_condition_type: str
    condition_args: int
    buff_hit_attribute: str

    def __hash__(self):
        return (self.id, self.actions).__hash__()


def get_unique_combo_data(in_dir: str) -> Dict[int, UniqueComboData]:
    with open(os.path.join(in_dir, 'CharaUniqueCombo.json')) as f:
        data: List[Dict[str, Any]] = json.load(f)
        combos = {}
        for combo in data:
            combos[combo['_Id']] = UniqueComboData(
                id=combo['_Id'],
                action_id=combo['_ActionId'],
                max_combo_num=combo['_MaxComboNum'],
                shift_condition_type=SHIFT_CONDITION_TYPES.get(combo['_ShiftConditionType'],
                                                               str(combo['_ShiftConditionType'])),
                condition_args=combo['_ConditionArgs1'],
                buff_hit_attribute=combo['_BuffHitAttribute'],
            )
        return combos


def gather_unique_combo(combo_data: UniqueComboData, actions: Dict[int, Action]) -> UniqueCombo:
    return UniqueCombo(
        id=combo_data.id,
        actions=get_action_and_associated(actions[combo_data.action_id], actions),
        max_combo_num=combo_data.max_combo_num,
        shift_condition_type=combo_data.shift_condition_type,
        condition_args=combo_data.condition_args,
        buff_hit_attribute=combo_data.buff_hit_attribute
    )


def get_unique_combos(in_dir: str, actions: Dict[int, Action]) -> Dict[int, UniqueCombo]:
    return {cmb_id: gather_unique_combo(cmb, actions) for cmb_id, cmb in
            get_unique_combo_data(in_dir).items() if cmb_id}
