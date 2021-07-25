from enum import Enum
from functools import wraps
from pprint import pprint
from collections import Counter


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
    HOSTILE_DEAD_ALIVE_01 = 56


class Order(Enum):
    Closer = 1
    AliveFarther = 2


INDENT = ""


def logfmt_funcdef_call(indent="", func=None, args=None, kwargs=None, retval=None):
    return f"{indent}Begin {func}:"


def logfmt_funcdef(indent="", func=None, args=None, kwargs=None, retval=None):
    if retval is None:
        return f"{indent}Returned from {func}"
    else:
        return f"{indent}Returned from {func}: {retval}"


def logfmt_target(indent="", func=None, args=None, kwargs=None, retval=None):
    return f"{indent}Set target to {args[1].name}"


def logfmt_move(indent="", func=None, args=None, kwargs=None, retval=None):
    return f"{indent}Move to position {args[1].name}"


def logfmt_turn(indent="", func=None, args=None, kwargs=None, retval=None):
    return f"{indent}Turn towards {args[1].name}"


def fmt_hitattr_simple(hitattr, sep=": "):
    if not isinstance(hitattr, dict):
        return None
    hitattr_lines = []
    for key, value in hitattr.items():
        if isinstance(value, dict):
            value = ", ".join(fmt_hitattr_simple(value, sep="="))
        hitattr_lines.append(f"{key}{sep}{value}")
    return hitattr_lines


FMT_HITATTR = {
    "_DamageAdjustment": "deal {value:.0%} damage",
    "_HpDrainRate2": "recover {value}x of dealt damage as HP",
}


def fmt_hitattr_actcond(actcond):
    if aff := actcond.get("_Type"):
        duration = actcond.get("_DurationSec")
        rate = actcond.get("_Rate", 0)
        if min_duration := actcond.get("_MinDurationSec"):
            return f"inflict {aff} for {min_duration}-{duration}s with {rate/100:.0%} chance"
        else:
            dot_rate = actcond.get("_SlipDamageRatio")
            return f"inflict {aff} for {duration}s with {rate/100:.0%} chance, dealing {dot_rate:.2%} of HP every second"


def fmt_hitattr_for_hoomans(hitattr):
    if not isinstance(hitattr, dict):
        return None
    hitattr_lines = []
    for key, fmt in FMT_HITATTR.items():
        if (value := hitattr.get(key)) :
            hitattr_lines.append(fmt.format(value=value))
    if (actcond := hitattr.get("_ActionCondition")) :
        if (actcond_str := fmt_hitattr_actcond(actcond)) :
            hitattr_lines.append(actcond_str)
    if len(hitattr_lines) > 1:
        return ", ".join(hitattr_lines[:-1]) + " and " + hitattr_lines[-1]
    if len(hitattr_lines) == 1:
        return hitattr_lines
    return None


def logfmt_action(indent="", func=None, args=None, kwargs=None, retval=None):
    if retval:
        action_lines = [f"{indent}Do action {args[1]}"]
        for key, value in retval.items():
            if key.startswith("_Name") and value != "ENEMY_SKILL_0":
                action_lines.append(f"{key}: {value}")
        # action_group = retval.get("_ActionGroupName")
        # if isinstance(action_group, dict):
        #     for key, value in action_group.items():
        #         if key.startswith("_HitAttrId"):
        #             difficulty = key.replace("_HitAttrId", "")
        #             if fmt_hitattr_line := fmt_hitattr_for_hoomans(value):
        #                 action_lines.append(f"Hit {difficulty}:")
        #                 action_lines.append(fmt_hitattr_line)
        #             else:
        #                 action_lines.extend(f"Hit {difficulty}: {value}")
        return f"\n{indent}".join(action_lines)
    else:
        return f"{indent}Do action {args[1]}"


def logfmt_init_runtime_var(indent="", func=None, args=None, kwargs=None, retval=None):
    return f"{indent}Set runtime variable self.{args[1]} to {args[2][0]}"


LOGFMT_DEFAULT = "{indent}{func}({args}, {kwargs}) = {retval}".format


def log_call(logfmt=LOGFMT_DEFAULT, indent=False):
    def real_decorator(function):
        @wraps(function)
        def wrapper(*args, **kwargs):
            # ai_runner._logs.append((function, args[1:], kwargs))
            runner = args[0]
            do_logging = runner._m.verbose == 2 or (runner._m.verbose == 1 and logfmt == logfmt_action)
            idt = INDENT * runner._m.depth
            if do_logging and logfmt == logfmt_funcdef:
                runner._m.logs.append(logfmt_funcdef_call(indent=idt, func=function.__name__, args=args, kwargs=kwargs))
            if indent:
                runner._m.depth += 1
            retval = function(*args, **kwargs)
            if indent:
                runner._m.depth -= 1
            if do_logging:
                runner._m.logs.append(logfmt(indent=idt, func=function.__name__, args=args, kwargs=kwargs, retval=retval))
            return retval

        return wrapper

    return real_decorator


class AiRunnerMeta:
    def __init__(self, params):
        self.reset_logs()
        self.action_seq = []
        self.verbose = 1  # 0 no log, 1, log actions only, 2, log all
        self.params = params
        self.action_set = {}
        self.value_seq = {}
        for boost, act_set in ((False, params.get("_ActionSet")), (True, params.get("_ActionSetBoost"))):
            if not isinstance(act_set, dict):
                continue
            for act, act_data in act_set.items():
                if not isinstance(act_data, dict):
                    continue
                act = act[1:].lower()
                self.action_set[(boost, act)] = act_data
        self.action_reg = {}

    def print_logs(self):
        for line in self.logs:
            print(line)

    def reset_logs(self):
        self.depth = 0
        self.logs = []

    def action_cycle_check(self):
        start = 0
        maxlen = len(self.action_seq)
        bestest = self.action_seq, 1, 0
        for start in range(0, maxlen):
            accumulator = Counter()
            length = 1
            c_slice = tuple(self.action_seq[start : start + length])
            while start + length * (accumulator[c_slice] + 1) <= maxlen:
                n_slice = tuple(self.action_seq[start + length * accumulator[c_slice] : start + length * (accumulator[c_slice] + 1)])
                if n_slice == c_slice:
                    accumulator[c_slice] += 1
                else:
                    length += 1
                    c_slice = tuple(self.action_seq[start : start + length])
                    accumulator[c_slice] = 1
            c_best = accumulator.most_common(1)
            if len(c_best) > 0 and c_best[0][1] > bestest[1]:
                bestest = (*c_best[0], start)
        seq, freq, start = bestest
        pprint(self.action_seq)


class AiRunner:
    def __init__(self, params):
        self._m = AiRunnerMeta(params)

    def init(self):
        pass

    @log_call(logfmt_init_runtime_var)
    def init_runtime_var(self, name, values):
        self._m.value_seq[name] = 0

        def cycling_value_getter(self):
            next_value = values[self._m.value_seq[name]]
            # self._m.value_seq[name] += 1
            # if self._m.value_seq[name] >= len(values):
            #     self._m.value_seq[name] = 0
            if isinstance(next_value, str):
                next_value = getattr(self, next_value, next_value)
            return next_value

        setattr(self.__class__, name, property(cycling_value_getter))

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
    def action(self, name):
        act_data = self._m.action_reg.get(name)
        self._m.action_seq.append(name)
        return act_data or None

    @log_call()
    def wake(self):
        pass

    def alive_num(self, kind, limit):
        setattr(self, kind, limit)

    def rec_timer(self, status):
        pass

    def unusual_posture(self, status):
        pass

    def turn_event(self, value=None):
        pass

    def sudden_event(self, value):
        pass

    def bandit_event(self, value):
        pass


if __name__ == "__main__":
    test = AiRunner({})
    test.target(Target.ALL_RANDOM_00)
    print(test._logs)