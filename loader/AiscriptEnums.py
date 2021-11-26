from loader.Database import ShortEnum


class Command(ShortEnum):
    Def = 0
    EndDef = 1
    If = 2
    Else = 3
    ElseIF = 4
    EndIf = 5
    Set = 6
    Add = 7
    Sub = 8
    SetTarget = 9
    EndScript = 10
    Action = 11
    Function = 12
    MoveAction = 13
    TurnAction = 14
    Random = 15
    RecTimer = 16
    RecHpRate = 17
    AliveNum = 18
    Jump = 19
    Wake = 20
    ClearDmgCnt = 21
    UnusualPosture = 22
    FromActionSet = 23
    GM_SetTurnEvent = 24
    GM_CompleteTurnEvent = 25
    GM_SetTurnMax = 26
    GM_SetSuddenEvent = 27
    GM_SetBanditEvent = 28
    Mul = 29
    OrderCloser = 30
    OrderAliveFather = 31
    FromActionSetBoost = 32
    UnitNumInCircle = 33
    Reserve08 = 34
    Reserve09 = 35
    Reserve10 = 36


class Compare(ShortEnum):
    largeEqual = 0
    smallEqual = 1
    repudiation = 2
    equal = 3
    large = 4
    small = 5
    none = 6


class Move(ShortEnum):
    none = 0
    approch = 1
    escape = 2
    escapeTL = 3
    pivot = 4
    anchor = 5


class Target(ShortEnum):
    NONE = 0
    MYSELF_00 = 1
    ALLY_HP_02 = 4
    ALLY_HP_03 = 5
    ALLY_HP_04 = 6
    ALLY_DISTANCE_00 = 7
    ALLY_DISTANCE_01 = 8
    ALLY_STRENGTH_00 = 9
    ALLY_STRENGTH_01 = 10
    ALLY_BUFF_00 = 11
    ALLY_BUFF_01 = 12
    ALLY_BUFF_04 = 15
    HOSTILE_DISTANCE_00 = 16
    HOSTILE_DISTANCE_01 = 17
    HOSTILE_HP_00 = 18
    HOSTILE_STRENGTH_00 = 19
    HOSTILE_STRENGTH_01 = 20
    HOSTILE_TARGET_00 = 21
    HOSTILE_TARGET_01 = 22
    HOSTILE_TARGET_02 = 23
    HOSTILE_RANDOM_00 = 24
    HOSTILE_FRONT_00 = 25
    HOSTILE_BEHIND_00 = 26
    ALL_DISTANCE_00 = 27
    ALL_DISTANCE_01 = 28
    ALL_RANDOM_00 = 29
    PLAYER1_TARGET = 30
    PLAYER2_TARGET = 31
    PLAYER3_TARGET = 32
    PLAYER4_TARGET = 33
    PLAYER_RANDOM = 34
    HOSTILE_SWOON = 35
    HOSTILE_BIND = 36
    PLAYER_RANDOM_INDIRECT = 37
    PLAYER_RANDOM_DIRECT = 38
    HOSTILE_OUT_MARKER_00 = 39
    HOSTILE_OUT_MARKER_01 = 40
    HOSTILE_OUT_MARKER_02 = 41
    SPECIAL_HATE = 42
    HOSTILE_DISTANCE_NO_LIMIT = 43
    REGISTERED_01 = 44
    REGISTERED_02 = 45
    REGISTERED_03 = 46
    REGISTERED_04 = 47
    HOSTILE_DEAD_ALIVE_00 = 48
    HOSTILE_RANDOM_LOCK_ON = 49
    PLAYER2_TARGET_NO_SUB = 50
    PLAYER3_TARGET_NO_SUB = 51
    PLAYER4_TARGET_NO_SUB = 52
    PLAYER2_TARGET_SUB_HOST = 53
    PLAYER3_TARGET_SUB_HOST = 54
    PLAYER4_TARGET_SUB_HOST = 55
    HOSTILE_DEAD_ALIVE_01 = 56


class Turn(ShortEnum):
    none = 0
    target = 1
    warldCenter = 2
    north = 3
    east = 4
    south = 5
    west = 6
    pivot = 7
    anchor = 8
