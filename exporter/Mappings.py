WEAPON_TYPES = {
    1: 'Sword',
    2: 'Blade',
    3: 'Dagger',
    4: 'Axe',
    5: 'Lance',
    6: 'Bow',
    7: 'Wand',
    8: 'staff'
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
    1: 'Poison',
    2: 'Burn',
    3: 'Freeze',
    4: 'Paralysis',
    5: 'Blind',
    6: 'Stun',
    7: 'Curse',
    8: 'UNKNOWN08',
    9: 'Bog',
    10: 'Sleep',
    11: 'Frostbite'
}

KILLER_STATE = {
    **AFFLICTION_TYPES,
    103: 'Def Down',
    198: 'Buff', # or maybe only burning ambition?
    201: 'Break'
}

ABILITY_CONDITION_TYPES = {
    1: 'hp_geq',
    2: 'hp_leq',
    4: 'buff_effect',
    5: 'transformed',
    6: 'break',
    8: 'doublebuff',
    9: 'combo',
    11: 'slayer/striker',
    12: 'claws',
    14: 'hp_drop_under',
    15: 'prep',
    16: 'overdrive',
    18: 'yaten_s1',
    19: 'energized',
    20: 'bleed',
    21: 'every_combo',
    25: 's1_charge_under',
    28: 's2_charge_under',
    29: 'affliction_proc',
    30: 'affliction_resisted',
    31: 'transform',
    32: 'teammates alive',
    34: 'energy level',
    36: 'energy buffed',
    37: 'hp_lt',
    39: 'primed',
    43: 'def_down_proc',
    44: 'buff_icons',
    45: 'on_crit',
    46: 'knocked_back',
    47: 'not_knocked_back',
    48: 'buffed',
    50: 'enemy_has_def_down'
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