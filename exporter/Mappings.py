from loader.Database import ShortEnum

WEAPON_TYPES = {
    1: 'Sword',
    2: 'Blade',
    3: 'Dagger',
    4: 'Axe',
    5: 'Lance',
    6: 'Bow',
    7: 'Wand',
    8: 'Staff',
    9: 'Gun'
}

ELEMENTS = {
    1: 'Flame',
    2: 'Water',
    3: 'Wind',
    4: 'Light',
    5: 'Shadow'
}

CLASS_TYPES = {
    1: 'Attack', 
    2: 'Defense',
    3: 'Support',
    4: 'Healing'
}


AFFLICTION_TYPES = {
    1: 'poison',
    2: 'burn',
    3: 'freeze',
    4: 'paralysis',
    5: 'blind',
    6: 'stun',
    7: 'curse',
    8: 'UNKNOWN08', # revive?
    9: 'bog',
    10: 'sleep',
    11: 'frostbite',
    12: 'flashburn',
    13: 'stormlash',
    14: 'shadowblight',
    15: 'scorchrend'
}

KILLER_STATE = {
    **AFFLICTION_TYPES,
    99: 'afflicted',
    103: 'debuff_def',
    198: 'buffed',
    199: 'debuff',
    201: 'break'
}

TRIBE_TYPES = {
    1: 'Thaumian',
    2: 'Physian',
    3: 'Demihuman',
    4: 'Therion',
    5: 'Undead',
    6: 'Demon',
    7: 'Human',
    8: 'Dragon'
}

class ActionTargetGroup(ShortEnum):
    NONE = 0
    MYSELF = 1
    ALLY = 2
    HOSTILE = 3
    BOTH = 4
    DUNOBJ = 5
    MYPARTY = 6
    ALLY_HP_LOWEST = 7
    HIT_OR_GUARDED_RECORD = 8
    HIT_RECORD = 9
    HOSTILE_AND_DUNOBJ = 10
    BIND = 11
    MYPARTY_EXCEPT_MYSELF = 12
    MYPARTY_EXCEPT_SAME_CHARID = 13
    HIT_OR_GUARDED_RECORD_ALLY = 14
    HIT_OR_GUARDED_RECORD_MYSELF = 15
    FIXED_OBJECT = 16

class AbilityTargetAction(ShortEnum):
    NONE = 0
    COMBO = 1
    BURST_ATTACK = 2
    SKILL_1 = 3
    SKILL_2 = 4
    SKILL_3 = 5
    SKILL_ALL = 6
    HUMAN_SKILL_1 = 7
    HUMAN_SKILL_2 = 8
    DRAGON_SKILL_1 = 9
    SKILL_4 = 10
    HUMAN_SKILL_3 = 11
    HUMAN_SKILL_4 = 12

class AbilityCondition(ShortEnum):
    NONE = 0
    HP_MORE = 1
    HP_LESS = 2
    BUFF_SKILL1 = 3
    BUFF_SKILL2 = 4
    DRAGON_MODE = 5
    BREAKDOWN = 6
    GET_BUFF_ATK = 7
    GET_BUFF_DEF = 8
    TOTAL_HITCOUNT_MORE = 9
    TOTAL_HITCOUNT_LESS = 10
    KILL_ENEMY = 11
    TRANSFORM_DRAGON = 12
    HP_MORE_MOMENT = 13
    HP_LESS_MOMENT = 14
    QUEST_START = 15
    OVERDRIVE = 16
    ABNORMAL_STATUS = 17
    TENSION_MAX = 18
    TENSION_MAX_MOMENT = 19
    DEBUFF_SLIP_HP = 20
    HITCOUNT_MOMENT = 21
    GET_HEAL_SKILL = 22
    SP1_OVER = 23
    SP1_UNDER = 24
    SP1_LESS = 25
    SP2_OVER = 26
    SP2_UNDER = 27
    SP2_LESS = 28
    CAUSE_ABNORMAL_STATUS = 29
    DAMAGED_ABNORMAL_STATUS = 30
    DRAGONSHIFT_MOMENT = 31
    PARTY_ALIVE_NUM_OVER = 32
    PARTY_ALIVE_NUM_UNDER = 33
    TENSION_LV = 34
    TENSION_LV_MOMENT = 35
    GET_BUFF_TENSION = 36
    HP_NOREACH = 37
    HP_NOREACH_MOMENT = 38
    SKILLCONNECT_SKILL1_MOMENT = 39
    SKILLCONNECT_SKILL2_MOMENT = 40
    DRAGON_MODE2 = 41
    CAUSE_DEBUFF_ATK = 42
    CAUSE_DEBUFF_DEF = 43
    CHANGE_BUFF_TYPE_COUNT = 44
    CAUSE_CRITICAL = 45
    TAKE_DAMAGE_REACTION = 46
    NO_DAMAGE_REACTION_TIME = 47
    BUFFED_SPECIFIC_ID = 48
    DAMAGED = 49
    DEBUFF = 50
    RELEASE_DRAGONSHIFT = 51
    UNIQUE_TRANS_MODE = 52
    DAMAGED_MYSELF = 53
    SP1_MORE_MOMENT = 54
    SP1_UNDER_MOMENT = 55
    SP2_MORE_MOMENT = 56
    SP2_UNDER_MOMENT = 57
    HP_MORE_NOT_EQ_MOMENT = 58
    HP_LESS_NOT_EQ_MOMENT = 59
    HP_MORE_NO_SUPPORT_CHARA = 60
    HP_NOREACH_NO_SUPPORT_CHARA = 61
    CP1_CONDITION = 62
    CP2_CONDITION = 63
    REQUIRED_BUFF_AND_SP1_MORE = 64
    REQUIRED_BUFF_AND_SP2_MORE = 65
    ENEMY_HP_MORE = 66
    ENEMY_HP_LESS = 67
    ALWAYS_REACTION_TIME = 68
    ON_ABNORMAL_STATUS_RESISTED = 69
    BUFF_DISAPPEARED = 70
    BUFFED_SPECIFIC_ID_COUNT = 71
    CHARGE_LOOP_REACTION_TIME = 72
    BUTTERFLYBULLET_NUM_OVER = 73
    AVOID = 74
    CAUSE_DEBUFF_SLIP_HP = 75
    CP1_OVER = 76
    CP2_OVER = 77
    CP1_UNDER = 78
    CP2_UNDER = 79
    BUFF_COUNT_MORE_THAN = 80
    BUFF_CONSUMED = 81
    HP_BETWEEN = 82
    DAMAGED_WITHOUT_MYSELF = 83
    BURST_ATTACK_REGULAR_INTERVAL = 84
    BURST_ATTACK_FINISHED = 85
    REBORN_COUNT_LESS_MOMENT = 86
    DISPEL_SUCCEEDED = 87
    ON_BUFF_FIELD = 88
    ENTER_EXIT_BUFF_FIELD = 89
    GET_DP = 90
    GET_BUFF_FOR_PD_LINK = 91
    GET_HEAL = 92
    BURST_CHARGE_TIME = 93
    HITATTR_COUNT_MORE = 94
    COMBO_COUNT_IV = 95
    DODGE_MOMENT = 96