from loader.Database import ShortEnum


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
    ON_REVIVE = 125
    ON_IN_BURST_GUARD_COUNTER = 126
    QUEST_START_AND_CHANGE_EQUIPMENT = 127
    LETHAL_DAMAGED = 128
    HITCOUNT_TIMESRATE = 129
    TOTAL_HITCOUNT_LESS_MOMENT = 130
    TOTAL_HITCOUNT_MORE_MOMENT = 131
    ON_CHARASTATE_ENTER_EXIT = 132
    DAMAGED_WITHOUT_MYSELF_BEFORE_DAMAGE_REACTION = 133
    ON_DEAD = 134
    GUTS_MOMENT = 135
    ON_HIT_TRAP = 136
    ON_HIT_TRAP_COOLTIME = 137


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
    MoveSpeedRateC = 19


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
    SHARE_SKILL = 13


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
    RecoverySpCutRate = 90
    ActRecoveryMulForDyingTarget = 91
    CallCpCommand = 92
    AdditionalHitCollision = 93
    RecoveryOnDamage = 94
    Guts = 95
    SendSignal = 96
    RemoveSignal = 97
    StatusUpBaseOnCharaType = 98
    ChangeStateOtherPartyMembers = 99
    DpGaugeCap2 = 100
    DpChargeMyParty2 = 101
    Reserved_102 = 102
    Reserved_103 = 103
    Reserved_104 = 104
    Reserved_105 = 105
    Reserved_106 = 106
    Reserved_107 = 107
    Reserved_108 = 108
    Reserved_109 = 109
    Reserved_110 = 110


class ActionCancelType(ShortEnum):
    NONE = 0
    BurstAttack = 1
    Avoid = 2
    AvoidFront = 3
    AvoidBack = 4
    AnyCombo = 5


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
    SELF_GROUND_ON_SKILL_START = 26
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
    Reserve_23 = 23
    Reserve_24 = 24
    Reserve_25 = 25
    Reserve_26 = 26
    Reserve_27 = 27
    Reserve_28 = 28
    Reserve_29 = 29
    Reserve_30 = 30
    Reserve_31 = 31
    Reserve_32 = 32
    Unique_10350104_01 = 33
    Unique_10950503_01 = 34


class ActionHitExecType(ShortEnum):
    NONE = 0
    DAMAGE = 1
    HEAL = 2
    CUSTOM = 3
    TRANS = 4
    DAMAGE_OBJ = 5
    NODAMAGE = 6
    HEAL_SP = 7
    MYSELF = 8
    HEAL_SP_HUMANONLY = 9
    DUMMY_DAMAGE = 10
    HEAL_SP_DRAGONONLY = 11
    HEAL_ABS_TIME = 12


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
    RecoveryOnDamage = 37
    HideTransformEffect = 38
    RESERVE_05 = 39
    RESERVE_06 = 40
    RESERVE_07 = 41
    RESERVE_08 = 42
    RESERVE_09 = 43
    RESERVE_10 = 44


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


class AuraType(ShortEnum):
    NONE = 0
    HP = 1
    ATTACK = 2
    DEFENSE = 3
    CRITICAL = 4


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
    CPCommand = 50
    NevOptionRemoteSync = 51
    DisplayEnemyAbilityIconForZako = 52
    CancelTransform = 53
    DeleteSettingHitOfSelf = 54
    RESERVE_36 = 55
    RESERVE_37 = 56
    RESERVE_38 = 57
    RESERVE_39 = 58
    AreaChange = 59
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


class CommandType(ShortEnum):
    NONE = 0
    POSSIBE_NEXT_ACTION = 1
    PLAY_MOTION = 2
    BLEND_MOTION = 3
    STOP_MOTION = 4
    MOVE = 5
    MOVE_TO_TARGET = 6
    ROTATE = 7
    GEN_MARKER = 8
    GEN_BULLET = 9
    HIT_ATTRIBUTE = 10
    EFFECT = 11
    SOUND = 12
    CAMERA = 13
    SEND_SIGNAL = 14
    ACTIVE_CANCEL = 15
    LOITERING = 16
    ROTATE_TO_TARGET = 17
    MOVE_TO_TELEPORT = 18
    EFFECT_TO_TARGET = 19
    EVENT_ACTION = 20
    FALL = 21
    BREAK_FINISH = 22
    FREEZE_POSITION = 23
    MULTI_BULLET = 24
    VISIBLE_OBJECT = 25
    BULLET_CANE_COMBO_005 = 26
    BREAK_CHANCE = 27
    APPEAR_ENEMY = 28
    DROP_BULLET = 29
    CHARACTER_COMMAND = 30
    B00250 = 31
    B00252 = 32
    B00254 = 33
    B00255 = 34
    EFFECT_STRETCH = 35
    EXTRA_CAMERA = 36
    ARRANGE_BULLET = 37
    E02660 = 38
    D00562 = 39
    COLOR = 40
    PARABOLA_BULLET = 41
    ENEMY_GUARD = 42
    E02950 = 43
    EMOTION = 44
    NAVIGATENPC = 45
    DESTROY_MOTION = 46
    BULLET_WITH_MARKER = 47
    HIT_STOP = 48
    MOVE_TIME_CURVE = 49
    MOVE_ORBIT = 50
    WINDY_STREAM = 51
    VOLCANO = 52
    PIVOT_BULLET = 53
    MOVE_INPUT = 54
    ROTATE_INPUT = 55
    THUNDER = 56
    LIGHTNING_PILLAR = 57
    STOCK_BULLET_ROUND = 58
    STOCK_BULLET_FIRE = 59
    OPERATE_PARAMETER = 60
    UPTHRUST = 61
    MULTI_EFFECT = 62
    HEAD_TEXT = 63
    CALL_MINION = 64
    AI_TARGET = 65
    SETTING_HIT = 66
    DARK_TORRENT = 67
    BODY_SCALE = 68
    DESTROY_LOCK = 69
    RECLOSE_BOX = 70
    SALVATION_BUBBLE = 71
    BIND = 72
    SWITCHING_TEXTURE = 73
    FLAME_ARM = 74
    ENEMY_ABILITY = 75
    TANATOS_HIT = 76
    TANATOS_HOURGLASS_SETACTION = 77
    TANATOS_HOURGLASS_DROP = 78
    TANATOS_PLAYER_EFFECT = 79
    INITIALIZE_WEAK = 80
    APPEAR_WEAK = 81
    SEITENTAISEI_HEAL = 82
    EA_MIRAGE = 83
    TANATOS_HIT_PIVOT_BULLET = 84
    MULTI_MARKER_NEED_REGISTER_POS = 85
    TANATOS_GENERAL_PURPOSE = 86
    GM_EVENT = 87
    MULTI_DROP_BULLET_REGISTERED_POS = 88
    LEVEL_HIT = 89
    SERVANT = 90
    ORDER_TO_SUB = 91
    THUNDERBALL = 92
    WATCH_WIND = 93
    BIND_BULLET = 94
    SYNC_CHARA_POSITION = 95
    TIME_STOP = 96
    ORDER_FROM_SUB = 97
    SHAPE_SHIFT = 98
    DEATH_TIMER = 99
    FORMATION_BULLET = 100
    SHADER_PARAM = 101
    FISHING_POWER = 102
    FISHING_DANCE_D = 103
    FISHING_DANCE_C = 104
    REMOVE_BUFF_TRIGGER_BOMB = 105
    FISHING_DANCE_AB = 106
    ORDER_TO_MINION = 107
    RESIST_CLEAR = 108
    HUNTER_HORN = 109
    HUMAN_CANNON = 110
    BUFF_CAPTION = 111
    REACTIVE_LIGHTNING = 112
    LIGHT_SATELLITE = 113
    OPERATE_BG = 114
    ICE_RAY = 115
    OPERATE_SHADER = 116
    APPEAR_MULTIWEAK = 117
    COMMAND_MULTIWEAK = 118
    UNISON = 119
    ROTATE_TIME_CURVE = 120
    SCALE_BLAST = 121
    EA_CHILDPLAY = 122
    DOLL = 123
    PUPPET = 124
    BUFFFIELD_ATTACHMENT = 125
    OPERATE_GMK = 126
    BUTTERFLY_BULLET = 127
    SEIUNHA = 128
    TERMINATE_OTHER = 129
    SETUP_LASTGASP = 130
    SETUP_MIASMA = 131
    MIASMA_POINTUP = 132
    HOLYLIGHT_LEVELUP = 133
    PLAYER_STOP = 134
    DESTORY_ALL_PRAY_OBJECT = 135
    GOZ_TACKLE = 136
    TARGET_EFFECT = 137
    STOCK_BULLET_SHIKIGAMI = 138
    SETUP_2ND_ELEMENTS = 139
    SETUP_ALLOUT_ASSAULT = 140
    IGNORE_ENEMY_PUSH = 141
    ACT_UI = 142
    ENEMY_BOOST = 143
    PARTY_SWITCH = 144
    ROTATE_NODE = 145
    AUTOMATIC_FIRE = 146
    SWITCH_ELEMENT = 147
    ODCOUNTERED_HIT = 148
    EA_GENESIS = 149
    SCAPEGOAT_RITES = 150
    ROSE_TOKEN = 151
    SETUP_DRASTICFORCE = 152
    OPERATE_DRASTICFORCE = 153
    EA_MELODY = 154
    MULTI_MOVE = 155
    SETUP_EVENTHEAL = 156
    EA_LINKED_BUFF = 157
    OPERATE_CUTT = 158
    CHANGE_PARTSMESH = 159
    EA_POWERCRYSTAL = 160
    SETUP_CTS = 161
    STOCK_BULLET_NEVOPTION = 162
    REBORN = 163
    RESERVE_83 = 164
    RESERVE_84 = 165
    RESERVE_85 = 166
    RESERVE_86 = 167
    RESERVE_87 = 168
    RESERVE_88 = 169
    RESERVE_89 = 170
    SETUP_X3RD_SUB = 171
    RESERVE_91 = 172
    RESERVE_92 = 173
    RESERVE_93 = 174
    RESERVE_94 = 175
    RESERVE_95 = 176
    RESERVE_96 = 177
    RESERVE_97 = 178
    RESERVE_98 = 179
    RESERVE_99 = 180
    ELEMENTAL_TRAP = 181
    RESERVE_101 = 182
    RESERVE_102 = 183
    RESERVE_103 = 184
    RESERVE_104 = 185
    RESERVE_105 = 186
    RESERVE_106 = 187
    RESERVE_107 = 188
    RESERVE_108 = 189
    RESERVE_109 = 190
    RESERVE_110 = 191


class EnemyAbilityType(ShortEnum):
    NONE = 0
    DISSEVER = 1
    MIRAGE = 2
    NICKED = 3
    FURY = 4
    DP_DOWN = 5
    ATTACK_RANGE_TOLERANCE = 6
    BLAZING = 7
    SKILL_GUARD = 8
    IGNORE_PLAYER_ATK = 9
    VERONICA_MIRAGE = 10
    RIPTIDE = 11
    ELECTRIFY = 12
    FURY_2 = 13
    GRUDGE = 14
    PETRIFACTION = 15
    MALAISE = 16
    DRAIN = 17
    ATK_GUARD = 18
    RAMPAGE = 19
    GIANT = 20
    IGNORE_ATK_ON_ACTION = 21
    VIRUS = 22
    ARENA = 23
    GOLDEN_BARRIER = 24
    SHOWING = 25
    MIST = 26
    UNISON = 27
    CHILD_PLAY = 28
    BLOCKING = 29
    OPENNESS = 30
    DISPEL_GUARD = 31
    HEAL_BLOCK = 32
    DRAGON_BUSTER = 33
    HOPELESSNESS = 34
    SUBSPACE = 35
    GODS_ROCK = 36
    BERSERK_01 = 37
    BERSERK_02 = 38
    BERSERK_03 = 39
    BERSERK_04 = 40
    BERSERK_05 = 41
    YIN_YANG = 42
    BLACK_FLAME = 43
    BOOK_OF_GENESIS = 44
    BOOK_OF_DOOM = 45
    SCAPEGOAT = 46
    TRIAD_MASKS = 47
    WEAKEN_FOR_DRAGON = 48
    MELODY = 49
    DISSONANCE = 50
    LINKED_ENEMY_BUFF = 51
    BURNING = 52
    PHOENIX = 53
    POWER_CRYSTAL = 54
    DEVIL_FIELD = 55
    ELEMENTAL_TRAP = 56
    METEOR_STRIKE = 57
    TENTACLE_LIFE = 58


class FirePositionPattern(ShortEnum):
    NONE = 0
    Horizontal = 1
    Radial = 2
    Circle = 3


class FireStockPattern(ShortEnum):
    NONE = 0
    StockBullet = 1
    BuffCount = 2
    SpecifiedNum = 3
    ButterflyNum = 4
    DuplicatedBuffCount = 5
    PartyAuraLevel = 6


class KillerState(ShortEnum):
    NONE = 0
    AbsPoison = 1
    AbsBurn = 2
    AbsFreeze = 3
    AbsParalysis = 4
    AbsDarkness = 5
    AbsSwoon = 6
    AbsCurse = 7
    AbsRebirth = 8
    AbsSlowMove = 9
    AbsSleep = 10
    AbsFrostbite = 11
    AbsFlashheat = 12
    AbsCrashwind = 13
    AbsDarkabs = 14
    AbsDestroyfire = 15
    AbsAll = 99
    DbfHp = 101
    DbfAttack = 102
    DbfDefense = 103
    DbfCritical = 104
    DbfSkillPower = 105
    DbfBurstPower = 106
    DbfRecovery = 107
    DbfGash = 108
    BfDbfAll = 197
    BfAll = 198
    DbfAll = 199
    Break = 201


class MarkerShape(ShortEnum):
    Circle = 0
    Line = 1
    Cross_01 = 2
    Cross_02 = 3
    Fan30 = 4
    Fan100 = 5
    Arrow = 6
    ArrowCircle = 7
    Fan120 = 8
    Fan180 = 9
    Donuts = 10
    Fan60 = 11
    Fan90 = 12
    Fan150 = 13
    Fan210 = 14
    Fan240 = 15
    Fan270 = 16
    Fan15 = 17
    Fan45 = 18
    Fan10 = 19
    Tube180 = 20
    Fan300 = 21
    Fan330 = 22
    EnumMax = 23


class PartConditionComparisonType(ShortEnum):
    Equality = 0
    Inequality = 1
    GreaterThan = 2
    GreaterThanOrEqual = 3
    LessThan = 4
    LessThanOrEqual = 5


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
    AxisPosition = 19
    RESERVE_06 = 20
    RESERVE_07 = 21
    RESERVE_08 = 22
