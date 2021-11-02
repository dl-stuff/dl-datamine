from loader.Database import ShortEnum

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
    MYSELF_CHECK_COLLISION = 17
    RESERVE_11 = 18
    RESERVE_12 = 19
    RESERVE_13 = 20


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
    CHARGE_TIME_MORE_MOMENT = 93
    EVERY_TIME_HIT_OCCURS = 94
    HITCOUNT_MOMENT_TIMESRATE = 95
    JUST_AVOID = 96
    GET_BRITEM = 97
    DUP_BUFF_ALWAYS_TIMESRATE = 98
    BUFFED_SPECIFIC_ID_COUNT_MORE_ALWAYS_CHECK = 99
    GET_BUFF_FROM_SKILL = 100
    HP_RECOVERED_BETWEEN = 101
    RELEASE_DIVINEDRAGONSHIFT = 102
    HAS_AURA_TYPE = 103
    SELF_AURA_LEVEL_MORE = 104
    PARTY_AURA_LEVEL_MORE = 105
    DRAGONSHIFT = 106
    DRAGON_MODE_STRICTLY = 107
    HITCOUNT_MOMENT_WITH_ACTION = 108
    ACTIVATE_SKILL = 109
    SELF_AURA_MOMENT = 110
    PARTY_AURA_MOMENT = 111
    BUFFFIELD_COUNT = 112
    PARTY_AURA_LEVEL_MORE_REACTION_TIME = 113
    NEAREST_ENEMY_DISTANCE = 114
    CHARA_MODE = 115
    ON_REMOVE_ABNORMAL_STATUS = 116
    SUBSTITUDE_DAMAGE = 117
    AUTO_AVOID = 118
    ABNORMAL_STATUS_ALLY = 119
    ABNORMAL_STATUS_TIME_ELAPSED = 120
    ABNORMAL_STATUS_RECEIVED = 121
    IN_PURSUIT_RANGE = 122
    ABNORMAL_STATUS_RELEACED = 123
    BURST_ATTACKING = 124


class AbilityType(ShortEnum):
    NONE = 0
    StatusUp = 1
    ResistAbs = 2
    ActAddAbs = 3
    ResistTribe = 4
    ActKillerTribe = 5
    ActDamageUp = 6
    ActCriticalUp = 7
    ActRecoveryUp = 8
    ActBreakUp = 9
    ResistTrap = 10
    AddRecoverySp = 11
    AddRecoveryDp = 12
    RecoveryHpOnHitCount = 13
    ChangeState = 14
    ResistInstantDeath = 15
    DebuffGrantUp = 16
    SpCharge = 17
    BuffExtension = 18
    DebuffExtension = 19
    AbnormalKiller = 20
    UserExpUp = 21
    CharaExpUp = 22
    CoinUp = 23
    ManaUp = 24
    ActionGrant = 25
    CriticalDamageUp = 26
    DpCharge = 27
    ResistElement = 28
    ResistUnique = 29
    UniqueKiller = 30
    Dummy01 = 31
    Dummy02 = 32
    Dummy03 = 33
    Dummy04 = 34
    ModeGaugeSuppression = 35
    DragonDamageUp = 36
    EnemyAbilityKiller = 37
    HitAttribute = 38
    PassiveGrant = 39
    ActiveGaugeStatusUp = 40
    Dummy05 = 41
    HitAttributeShift = 42
    ReferenceOther = 43
    EnhancedSkill = 44
    EnhancedBurstAttack = 45
    DragonTimeForParty = 46
    AbnoramlExtension = 47
    DragonTimeSpeedRate = 48
    DpChargeMyParty = 49
    DontAct = 50
    RandomBuff = 51
    CriticalUpDependsOnBuffTypeCount = 52
    InvalidDragonAbility = 53
    ActDamageUpDependsOnHitCount = 54
    ChainTimeExtension = 55
    UniqueTransform = 56
    EnhancedElementDamage = 57
    UtpCharge = 58
    DebuffTimeExtensionForSpecificDebuffs = 59
    RemoveAllStockBullets = 60
    ChangeMode = 61
    RandomBuffNoTDuplicate_Param1Times = 62
    ModifyBuffDebuffDurationTime = 63
    CpCoef = 64
    UniqueAvoid = 65
    RebornHpRateUp = 66
    AttackBaseOnHPUpRate = 67
    ChangeStateHostile = 68
    CpContinuationDown = 69
    AddCpRate = 70
    RunOptionAction = 71
    SecondElements = 72
    KickAuraEffectTritter = 73
    ConsumeSpToRecoverHp = 74
    CrestGroupScoreUp = 75
    ModifyBuffDebuffDurationTimeByRecoveryHp = 76
    CrisisRate = 77
    ActDamageDown = 78
    AutoAvoidProbability = 79
    LimitCriticalAddRate = 80
    AddReborn = 81
    RunOptionActionRemoteToo = 82
    ConsumeUtpToRecoverHp = 83
    DpGaugeCap = 84
    AbnormalTypeNumKiller = 85
    RegisterKeepComboAction = 86
    NotUpdateDragonTime = 87
    SetCharacterState = 88
    ChangeModeRemoteToo = 89
    Reserve_090 = 90
    Reserve_091 = 91
    Reserve_092 = 92
    Reserve_093 = 93
    Reserve_094 = 94
    Reserve_095 = 95
    Reserve_096 = 96
    Reserve_097 = 97
    Reserve_098 = 98
    Reserve_099 = 99
    Reserve_100 = 100


class AbilityStat(ShortEnum):
    NONE = 0
    Hp = 1
    Atk = 2
    Def = 3
    Spr = 4
    Dpr = 5
    Dummy1 = 6
    ChargeTime = 7
    DragonTime = 8
    DamageCut = 9
    AttackSpeed = 10
    BurstSpeed = 11
    ChargeSpeed = 12
    ConsumeDpRate = 13
    FinalDragonTimeRate = 14
    Utpr = 15
    DamageCutB = 16
    MoveSpeedRateB = 17
    NeedDpRate = 18


class PartConditionType(ShortEnum):
    NONE = 0
    OwnerBuffCount = 1
    CPValue = 2
    Random = 3
    NearestEnemyDistance = 4
    SingleOrMultiPlay = 5
    SpecificTaggedBulletValid = 6
    ShikigamiLevel = 7
    SettingHitObjTagContains = 8
    ActionContainerHitCount = 9
    ActionCriticalStatus = 10
    HumanOrDragon = 11
    BulletTagContains = 12
    InitialOwner = 13
    RenderPartVisibility = 14
    TargetIdContains = 15
    AuraLevel = 16
    AllyHpRateLowest = 17
    CharaMode = 18
    RESERVE_05 = 19
    RESERVE_06 = 20
    RESERVE_07 = 21
    RESERVE_08 = 22


class PartConditionComparisonType(ShortEnum):
    Equality = 0
    Inequality = 1
    GreaterThan = 2
    GreaterThanOrEqual = 3
    LessThan = 4
    LessThanOrEqual = 5


class ActionCancelType(ShortEnum):
    NONE = 0
    BurstAttack = 1
    Avoid = 2
    AvoidFront = 3
    AvoidBack = 4
    AnyCombo = 5


class AuraType(ShortEnum):
    NONE = 0
    HP = 1
    ATTACK = 2
    DEFENSE = 3
    CRITICAL = 4


class ActionSignalType(ShortEnum):
    Input = 0
    SuperArmor = 1
    Invincible = 2
    AttachWeaponLeft = 3
    AttachWeaponRight = 4
    NonUse01 = 5
    NonUse02 = 6
    PutUpEffect = 7
    Show = 8
    Hide = 9
    NoReaction = 10
    SuperArmorLv1 = 11
    SuperArmorLv2 = 12
    SuperArmorLv3 = 13
    Omit01 = 14
    AdditionalInput = 15
    InvincibleLv1 = 16
    InvincibleLv2 = 17
    InvincibleLv3 = 18
    SpecialDead = 19
    NoTarget = 20
    SuperArmorLv4 = 21
    DisableCheckOutside = 22
    DisableExternalVelocity = 23
    ShowWeapon = 24
    HideWeapon = 25
    DamageCounter = 26
    CancelInvincible = 27
    ChangePartsMesh = 28
    EnableAction = 29
    RecordHitTarget = 30
    GuardCounter = 31
    GuardReactionInCharge = 32
    HideStockBullet = 33
    Stop1 = 34
    HitCount = 35
    ActionCriticalStatus = 36
    RESERVE_03 = 37
    RESERVE_04 = 38
    RESERVE_05 = 39
    RESERVE_06 = 40
    RESERVE_07 = 41
    RESERVE_08 = 42
    RESERVE_09 = 43
    RESERVE_10 = 44


class CharacterControl(ShortEnum):
    Dummy_03 = 0
    Leave = 1
    Dummy_01 = 2
    Dummy_02 = 3
    PartDemolishUI = 4
    EnemySkillTitle = 5
    ResetAbnormal = 6
    DelayEffect = 7
    AllPartsRepair = 8
    EffectControl = 9
    TargetReticleUI = 10
    SpecialHate = 11
    SyncTargetToSub = 12
    RegisterPosition = 13
    ChildCommand = 14
    BulletDelete = 15
    DisableCheckOutside = 16
    WeakAction = 17
    TargetOnOff = 18
    RegisterMultiPosition = 19
    SkipThisActionEndPlayIdleMotion = 20
    EnemyAiSpecialMode = 21
    Invincible = 22
    SoundCtrlStop = 23
    ResetPitchRoll = 24
    SwitchBgmBlock = 25
    SwitchBgModel = 26
    AttachEffTrigger = 27
    ExtraActionMode = 28
    SetCharaMarkUIVisibility = 29
    PlayerPushOnOff = 30
    ResistBuffDebuff = 31
    WeaponVisible = 32
    ResetTension = 33
    SelectMultiTarget = 34
    ResetBuffDebuff = 35
    ResistAllAbnormal = 36
    AttachObject = 37
    SetMoveSyncDisabled = 38
    ScaleOverdrivePoint = 39
    AllUnitInvincible = 40
    Stop1 = 41
    DisplayMyHpToPartsUI = 42
    ServantAction = 43
    DropDp = 44
    DamageImmunity = 45
    SwitchWeaponSkin = 46
    SetFace = 47
    ApplyBuffDebuff = 48
    SetFollowerTargetToPlayerTarget = 49
    RESERVE_31 = 50
    RESERVE_32 = 51
    RESERVE_33 = 52
    RESERVE_34 = 53
    RESERVE_35 = 54
    RESERVE_36 = 55
    RESERVE_37 = 56
    RESERVE_38 = 57
    RESERVE_39 = 58
    RESERVE_40 = 59
    RESERVE_41 = 60
    RESERVE_42 = 61
    RESERVE_43 = 62
    RESERVE_44 = 63
    RESERVE_45 = 64
    RESERVE_46 = 65
    RESERVE_47 = 66
    RESERVE_48 = 67
    RESERVE_49 = 68
    RESERVE_50 = 69


class ActionCollision(ShortEnum):
    NONE = 0
    SPHERE_SINGLEHIT = 1
    SPHERE = 2
    FAN = 3
    LINE = 4
    OMIT_001 = 5
    OMIT_002 = 6
    CROSS = 7
    OMIT_003 = 8
    WHOLE = 9
    DONUT_2D = 10
    FAN_IGNORE_HEIGHT = 11
    CIRCLE = 12
    FAN_HEIGHT = 13
    LINE_02 = 14
    BOX_NO_ROT = 15
    FAN_HEIGHT_02 = 16
    RESERVE_07 = 17
    RESERVE_08 = 18
    RESERVE_09 = 19
    RESERVE_10 = 20


class ActionCollisionPos(ShortEnum):
    NONE = 0
    SELF = 1
    SELF_C = 2
    TARGET = 3
    TARGET_C = 4
    FRONT_R = 5
    FRONT_CR = 6
    FRONT_CHR = 7
    SLOT_ATTACK = 8
    SLOT_ARM_R = 9
    SLOT_ARM_L = 10
    SLOT_TAIL_B = 11
    SLOT_HEAD = 13
    SLOT_JAW = 14
    SELF_GROUND = 15
    TARGET_GROUND = 16
    SLOT_HAND_R = 17
    SLOT_HAND_L = 18
    MARKER = 19
    MARKER_U_RANDOM = 20
    SLOT_WEAPON_R = 21
    SLOT_WEAPON_L = 22
    SPECIFY_ID = 23
    AREA_ANCHOR = 24
    TARGET_P = 25
    RESERVE_02 = 26
    RESERVE_03 = 27
    RESERVE_04 = 28
    RESERVE_05 = 29
    RESERVE_06 = 30
    RESERVE_07 = 31
    RESERVE_08 = 32
    RESERVE_09 = 33
    RESERVE_10 = 34


class ActionDefDebuff(ShortEnum):
    NONE = 0
    Hp = 1
    Attack = 2
    Defense = 3
    Critical = 4
    SkillDamage = 5
    BurstDamage = 6
    Recovery = 7
    Regeneration = 8
    ElementalResist = 9
    EnhancedBurst = 10
    EnhancedSkill = 11
    AttackSpeed = 12
    EnhancedAttack = 13
    Hp_Attack = 14
    CriticalDamage = 15
    SlipHp = 16
    Nicked = 17
    Malaise = 18
    SPDamage = 19
    DisableAction = 20
    AttackOrDefense = 21
    HLExclusive = 22
