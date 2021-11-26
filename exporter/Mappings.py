WEAPON_TYPES = {
    1: "Sword",
    2: "Blade",
    3: "Dagger",
    4: "Axe",
    5: "Lance",
    6: "Bow",
    7: "Wand",
    8: "Staff",
    9: "Gun",
}

WEAPON_LABEL = {
    1: "SWD",
    2: "KAT",
    3: "DAG",
    4: "AXE",
    5: "LAN",
    6: "BOW",
    7: "ROD",
    8: "CAN",
    9: "GUN",
}

ELEMENTS = {1: "Flame", 2: "Water", 3: "Wind", 4: "Light", 5: "Shadow"}

CLASS_TYPES = {1: "Attack", 2: "Defense", 3: "Support", 4: "Healing"}


AFFLICTION_TYPES = {
    1: "poison",
    2: "burn",
    3: "freeze",
    4: "paralysis",
    5: "blind",
    6: "stun",
    7: "curse",
    8: "UNKNOWN08",  # revive?
    9: "bog",
    10: "sleep",
    11: "frostbite",
    12: "flashburn",
    13: "stormlash",
    14: "shadowblight",
    15: "scorchrend",
    99: "all",
}

KILLER_STATE = {
    **AFFLICTION_TYPES,
    99: "afflicted",
    103: "debuff_def",
    108: "bleed",
    198: "buffed",
    199: "debuff",
    201: "break",
}

TRIBE_TYPES = {
    1: "thaumian",
    2: "physian",
    3: "demihuman",
    4: "therion",
    5: "undead",
    6: "demon",
    7: "human",
    8: "dragon",
}
