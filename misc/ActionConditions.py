import argparse
import os
from dataclasses import dataclass
from typing import Dict

from Common import run_common, load_by_id
from Mappings import AFFLICTION_TYPES
from TextLabel import get_text_label


@dataclass
class ActionConditionData:
    id: int
    type: str
    text: str
    text_ex: str
    unique_icon: int
    resist_buff_reset: int
    unified_management: int
    overwrite: int
    overwrite_identical_owner: int
    overwrite_group_id: int
    user_power_up_effect: int
    lost_on_dragon: int
    restore_on_reborn: int
    rate: int
    efficacy_type: int
    remove_condition_id: int
    duration: float
    duration_num: int
    min_duration: float
    remove_action: int
    slip_damage_interval: float
    slip_damage_fixed: int
    slip_damage_ratio: float
    slip_damage_max: int
    slip_damage_power: float
    regen_power: float
    event_probability: int
    event_coefficient: float
    damage_coefficient: float
    target_action: int
    target_elemental: int
    condition_abs: int
    condition_debuff: int
    hp: float
    attack: float
    defense: float
    defense_b: float
    critical: float
    skill: float
    fs: float
    recovery: float
    sp: float
    attack_speed: float
    charge_speed: float
    # rate_poison: float
    # rate_burn: float
    # rate_freeze: float
    # rate_paralysis: float
    # rate_blind: float
    # rate_stun: float
    # rate_curse: float
    # rate_bog: float
    # rate_sleep: float
    # rate_frostbite: float
    # rate_fire: float
    # rate_water: float
    # rate_wind: float
    # rate_light: float
    # rate_dark: float
    # rate_thaumian: float
    # rate_physian: float
    # rate_demihuman: float
    # rate_therion: float
    # rate_undead: float
    # rate_demon: float
    # rate_human: float
    # rate_dragon: float
    damage_cut: float
    damage_cut_2: float
    weak_invalid: float
    heal_invalid: int
    valid_regen_hp: float
    valid_regen_sp: float
    valid_regen_dp: float
    valid_slip_hp: float
    unique_regen_sp: float
    auto_regen_s1: float
    auto_regen_s2: float
    rate_reraise: float
    rate_armored: float
    shield1: float
    shield2: float
    shield3: float
    # malaise1: int  # vnidd
    # malaise2: int
    # malaise3: int
    # rate_nicked: float  # dull
    transform_skill: float
    grant_skill: int
    disable_action: int
    disable_move: int
    invincible_lv: int
    combo_shift: int
    enhanced_fs: int
    enhanced_skill1: int
    enhanced_skill2: int
    enhanced_weapon_skill: int
    enhanced_critical: float
    tension: int
    inspiration: int
    sparking: int
    rate_hp_drain: float
    hp_drain_limit_rate: float
    self_damage_rate: float
    hp_consumption_rate: float
    hp_consumption_coef: float
    remove_trigger: int
    damage_link: str
    extra_buff_type: int

    def __hash__(self):
        return (self.id, self.text).__hash__()


def parse_action_condition(data: dict, labels: Dict[str, str]) -> ActionConditionData:
    return ActionConditionData(
        id=data['_Id'],
        type=AFFLICTION_TYPES.get(data['_Type'], str(data['_Type'])),
        text=labels.get(data['_Text'], data['_Text']),
        text_ex=labels.get(data['_TextEx'], data['_TextEx']),
        unique_icon=data['_UniqueIcon'],
        resist_buff_reset=data['_ResistBuffReset'],
        unified_management=data['_UnifiedManagement'],
        overwrite=data['_Overwrite'],
        overwrite_identical_owner=data['_OverwriteIdenticalOwner'],
        overwrite_group_id=data['_OverwriteGroupId'],
        user_power_up_effect=data['_UsePowerUpEffect'],
        lost_on_dragon=data['_LostOnDragon'],
        restore_on_reborn=data['_RestoreOnReborn'],
        rate=data['_Rate'],
        efficacy_type=data['_EfficacyType'],
        remove_condition_id=data['_RemoveConditionId'],
        duration=data['_DurationSec'],
        duration_num=data['_DurationNum'],
        min_duration=data['_MinDurationSec'],
        remove_action=data['_RemoveAciton'],
        slip_damage_interval=data['_SlipDamageIntervalSec'],
        slip_damage_fixed=data['_SlipDamageFixed'],
        slip_damage_ratio=data['_SlipDamageRatio'],
        slip_damage_max=data['_SlipDamageMax'],
        slip_damage_power=data['_SlipDamagePower'],
        regen_power=data['_RegenePower'],
        event_probability=data['_EventProbability'],
        event_coefficient=data['_EventCoefficient'],
        damage_coefficient=data['_DamageCoefficient'],
        target_action=data['_TargetAction'],
        target_elemental=data['_TargetElemental'],
        condition_abs=data['_ConditionAbs'],
        condition_debuff=data['_ConditionDebuff'],
        hp=data['_RateHP'],
        attack=data['_RateAttack'],
        defense=data['_RateDefense'],
        defense_b=data['_RateDefenseB'],
        critical=data['_RateCritical'],
        skill=data['_RateSkill'],
        fs=data['_RateBurst'],
        recovery=data['_RateRecovery'],
        sp=data['_RateRecoverySp'],
        attack_speed=data['_RateAttackSpeed'],
        charge_speed=data['_RateChargeSpeed'],
        damage_cut=data['_RateDamageCut'],
        damage_cut_2=data['_RateDamageCut2'],
        weak_invalid=data['_RateWeakInvalid'],
        heal_invalid=data['_HealInvalid'],
        valid_regen_hp=data['_ValidRegeneHP'],
        valid_regen_sp=data['_ValidRegeneSP'],
        valid_regen_dp=data['_ValidRegeneDP'],
        valid_slip_hp=data['_ValidSlipHp'],
        unique_regen_sp=data['_UniqueRegeneSp01'],
        auto_regen_s1=data['_AutoRegeneS1'],
        auto_regen_s2=data['_AutoRegeneSW'],
        rate_reraise=data['_RateReraise'],
        rate_armored=data['_RateArmored'],
        shield1=data['_RateDamageShield'],
        shield2=data['_RateDamageShield2'],
        shield3=data['_RateDamageShield3'],
        transform_skill=data['_TransSkill'],
        grant_skill=data['_GrantSkill'],
        disable_action=data['_DisableAction'],
        disable_move=data['_DisableMove'],
        invincible_lv=data['_InvincibleLv'],
        combo_shift=data['_ComboShift'],
        enhanced_fs=data['_EnhancedBurstAttack'],
        enhanced_skill1=data['_EnhancedSkill1'],
        enhanced_skill2=data['_EnhancedSkill2'],
        enhanced_weapon_skill=data['_EnhancedSkillWeapon'],
        enhanced_critical=data['_EnhancedCritical'],
        tension=data['_Tension'],
        inspiration=data['_Inspiration'],
        sparking=data['_Sparking'],
        rate_hp_drain=data['_RateHpDrain'],
        hp_drain_limit_rate=data['_HpDrainLimitRate'],
        self_damage_rate=data['_SelfDamageRate'],
        hp_consumption_rate=data['_HpConsumptionRate'],
        hp_consumption_coef=data['_HpConsumptionCoef'],
        remove_trigger=data['_RemoveTrigger'],
        damage_link=data['_DamageLink'],
        extra_buff_type=data['_ExtraBuffType']
    )


def get_action_condition_data(in_dir: str, label: Dict[str, str]) -> Dict[int, ActionConditionData]:
    return {data[0]: parse_action_condition(data[1], label) for data in
            load_by_id(os.path.join(in_dir, 'ActionCondition.json')).items()}


def get_action_condition_filename(ac: ActionConditionData):
    if ac.type != 'Normal':
        return f'{ac.id}_{ac.type}'
    elif ac.text:
        return f'{ac.id}_{ac.text}'
    elif ac.efficacy_type == 100:
        return f'{ac.id}_Dispel'
    else:
        return f'{ac.id}'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Extract action condition data.')
    parser.add_argument('-i', type=str, help='input dir', default='./extract')
    parser.add_argument('-o', type=str, help='output dir', default='./out/action_conditions')
    args = parser.parse_args()
    run_common(args.o, [(get_action_condition_filename(ac), ac) for ac in
                        get_action_condition_data(args.i, get_text_label(args.i)).values()])
