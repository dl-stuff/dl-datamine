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
    99: 'Afflicted',
    103: 'Def Down',
    198: 'Buff', # or maybe only burning ambition?
    199: 'Debuff',
    201: 'Break'
}

ABILITY_CONDITION_TYPES = {
    1: 'hp geq',
    2: 'hp leq',
    4: 'buff effect',
    5: 'transformed',
    6: 'break',
    8: 'doublebuff',
    9: 'combo',
    11: 'slayer/striker',
    12: 'claws',
    13: 'chain hp geq',
    14: 'hp drop under',
    15: 'prep',
    16: 'overdrive',
    18: 'energized skill shift',
    19: 'energized',
    20: 'bleed',
    21: 'every combo',
    25: 's1 charge under',
    28: 's2 charge under',
    29: 'affliction proc',
    30: 'affliction resisted',
    31: 'transform',
    32: 'teammates alive',
    34: 'energy level',
    36: 'energy buffed',
    37: 'hp lt',
    39: 'primed',
    43: 'def down proc',
    44: 'buff icons',
    45: 'on crit',
    46: 'knocked back',
    47: 'not knocked back',
    48: 'buffed',
    50: 'enemy has def down'
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

TARGET_ACTION_TYPES = {
    1: 'auto',
    2: 'force strike',
    3: 'skill 1',
    4: 'skill 2',
    5: 'skill 3',
    6: 'skill',
}