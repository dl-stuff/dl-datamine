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
    11: 'Frostbite',
    12: 'Flashburn',
    13: 'Stormlash',
    14: 'Shadowblight',
    15: 'Scorchrend'
}

KILLER_STATE = {
    **AFFLICTION_TYPES,
    99: 'afflicted',
    103: 'debuff_def',
    198: 'buffed',
    199: 'debuff',
    201: 'break'
}

ABILITY_CONDITION_TYPES = {
    1: 'hp geq',
    2: 'hp leq',
    # 3
    4: 'buff effect',
    5: 'transformed',
    6: 'break',
    # 7
    8: 'doublebuff',
    9: 'combo',
    # 10 (seen in chains to remove a buff)
    11: 'slayer/striker',
    12: 'claws',
    13: 'chain hp geq',
    14: 'hp drop under',
    15: 'prep',
    16: 'overdrive',
    17: 'affliction',
    18: 'energized skill shift',
    19: 'energized',
    20: 'bleed',
    21: 'every combo',
    # 22 23 24
    25: 's1 charge under',
    26: 'skill gauge level',
    # 27
    28: 's2 charge under',
    29: 'affliction proc',
    30: 'affliction resisted',
    31: 'shapeshift',
    32: 'teammates alive',
    # 33
    34: 'energy level',
    # 35
    36: 'energy buffed',
    37: 'hp leq',
    38: 'hp leq proc',
    39: 'primed',
    # 40 41 42
    43: 'def down proc',
    44: 'buff icons',
    45: 'on crit',
    46: 'knocked back',
    47: 'not knocked back',
    48: 'buffed',
    49: 'damaged',
    50: 'enemy has def down',
    51: 'shapeshift end',
    52: 'dragondrive',
    53: 'dragondrive',
    # 54 55 56
    # 57: 'aether',
    58: 'hp leq', # chains
    59: 'hp geq', # chains
    60: 'hp geq then', # diff effect per hp thresh
    61: 'hp else',
    62: 'unique gauge',
    # 63
    # 64: 'unique buff',
    65: 'skill reservoir level',
    # 66
    67: 'enemy hp leq',
    68: 'periodic buff',
    69: 'affliction resisted',
    70: 'has action condition',
    71: 'has multi debuff',
    72: 'in fs marker',
    73: 'butterfly bullets',
    74: 'on dodge',
    75: 'on bleed',
    # 76 77 78 79
    80: 'has multi buff',
    81: 'has cartridge',
    82: 'scale with hp',
    # 83: 'mode from buff(?)'
    # 84 85
    86: 'has revive',
    87: 'on dispel',
    88: 'in buffzone',
    # 89
    90: 'on dragon gauge',
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