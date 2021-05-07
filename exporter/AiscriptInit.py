from enum import Enum
from functools import wraps


class Move(Enum):
    none = 0
    approch = 1
    escape = 2
    escapeTL = 3
    pivot = 4
    anchor = 5


class Turn(Enum):
    none = 0
    target = 1
    worldCenter = 2
    north = 3
    east = 4
    south = 5
    west = 6
    pivot = 7
    anchor = 8


class Target(Enum):
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


class Order(Enum):
    Closer = 1
    AliveFarther = 2


INDENT = "    "


LOGFMT_DEFAULT = "{indent}{func}({args}, {kwargs}) = {retval}".format


def log_call(logfmt=LOGFMT_DEFAULT, indent=False):
    def real_decorator(function):
        @wraps(function)
        def wrapper(*args, **kwargs):
            # ai_runner._logs.append((function, args[1:], kwargs))
            runner = args[0]
            idt = INDENT * runner._m.depth
            if indent:
                runner._m.depth += 1
            retval = function(*args, **kwargs)
            if runner._m.verbose == 2 or (runner._m.verbose == 1 and logfmt != LOGFMT_DEFAULT):
                runner._m.logs.append(logfmt(indent=idt, func=function.__name__, args=args, kwargs=kwargs, retval=retval))
            if indent:
                runner._m.depth += 1
            return retval

        return wrapper

    return real_decorator


def logfmt_funcdef(indent="", func=None, args=None, kwargs=None, retval=None):
    return f"{indent}Begin {func}:"


def logfmt_target(indent="", func=None, args=None, kwargs=None, retval=None):
    return f"{indent}Set target to {args[1].name}"


def logfmt_move(indent="", func=None, args=None, kwargs=None, retval=None):
    return f"{indent}Move to position {args[1].name}"


def logfmt_turn(indent="", func=None, args=None, kwargs=None, retval=None):
    return f"{indent}Turn towards {args[1].name}"


def logfmt_action(indent="", func=None, args=None, kwargs=None, retval=None):
    return f"{indent}Do action {args[1]}"


class AiRunnerMeta:
    def __init__(self, params):
        self.depth = 0
        self.logs = []
        self.verbose = 2  # 0 no log, 1, log non-default, 2, log all
        self.params = params
        self.action_set = {}
        for boost, act_set in ((False, params.get("_ActionSet")), (True, params.get("_ActionSetBoost"))):
            if not isinstance(act_set, dict):
                continue
            for act, act_data in act_set.items():
                if not isinstance(act_data, dict):
                    continue
                act = act[1:].lower()
                self.action_set[(boost, act)] = act_data
        self.action_reg = {}


class AiRunner:
    def __init__(self, params):
        self._m = AiRunnerMeta(params)

    def init(self):
        pass

    def init_runtime_var(self, name, values):
        pass

    def init_action(self, act, name, boost=False):
        act_data = self._m.action_set.get((boost, act))
        self._m.action_reg[name] = act_data
        if act_data:
            setattr(self, name, act_data["_Id"])
        else:
            setattr(self, name, -1)

    @log_call(logfmt_target)
    def target(self, target):
        self.TargetType = int(target.value)

    @log_call(logfmt_move)
    def move(self, target):
        pass

    @log_call(logfmt_turn)
    def turn(self, target):
        pass

    @log_call(logfmt_action)
    def action(seklf, name):
        pass

    @log_call()
    def wake():
        pass

    @log_call()
    def recHPRate():
        pass

    @log_call()
    def alive(limit):
        return limit

    @log_call()
    def rec_timer(status):
        pass

    @log_call()
    def unusual_posture(status):
        pass

    @log_call()
    def turn_event(value=None):
        pass

    @log_call()
    def sudden_event(value):
        pass

    @log_call()
    def bandit_event(value):
        pass


if __name__ == "__main__":
    test = AiRunner({})
    test.target(Target.ALL_RANDOM_00)
    print(test._logs)