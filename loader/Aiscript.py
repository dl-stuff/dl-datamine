import json
import os
from enum import Enum
from tqdm import tqdm
import subprocess

from loader.Database import check_target_path, DBViewIndex
from exporter.Shared import snakey
from exporter.Enemy import EnemyAction
from exporter.AiscriptInit import Target, Move, Turn, Order

OUTPUT = "out/_aiscript"


class Command(Enum):
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
    OrderAliveFarther = 31
    FromActionSetBoost = 32
    UnitNumInCircle = 33
    Reserve08 = 34
    Reserve09 = 35
    Reserve10 = 36


class Compare(Enum):
    largeEqual = 0
    smallEqual = 1
    repudiation = 2
    equal = 3
    large = 4
    small = 5
    none = 6


def s(v, prefix="self."):
    if isinstance(v, str):
        if v == "true":
            return "True"
        elif v == "false":
            return "False"
        elif v == "_m":
            return "var_m"
        snek = snakey(v)
        if snek[0].isdigit():
            snek = "_" + snek
        return f"{prefix}{snek}"
    else:
        return v


FMT_COMPARE = {
    Compare.largeEqual: "<=",
    Compare.smallEqual: ">=",
    Compare.repudiation: "!=",
    Compare.equal: "==",
    Compare.large: "<",
    Compare.small: ">",
}


def fmt_binary_opt(opt, v):
    var_name = v[0]
    var_value = v[1]
    if isinstance(var_name, str) and var_name[0] == "_":
        Root.add_rt_var(var_name, var_value, opt)
    else:
        var_name, var_value = var_value, var_name
        if isinstance(var_name, str) and var_name[0] == "_":
            Root.add_rt_var(var_name, var_value, opt)
    return f"{s(var_name)} {FMT_COMPARE[opt]} {s(var_value)}"


INDENT = "    "


def fmt_null(inst):
    return f"{INDENT*inst.depth}pass"


def fmt_def(inst):
    name = inst.params[0].values[0]
    name = snakey(name)
    if name[0].isdigit():
        name = "_" + name
    return f"{INDENT*inst.depth}@log_call(logfmt=logfmt_funcdef, indent=True)\n{INDENT*inst.depth}def {name}(self):"


def fmt_set(inst):
    name = inst.params[0].values[0]
    value = inst.params[1].values[0]
    Root.SET_VALUES[name] = value
    return f"{INDENT*inst.depth}{s(name)} = {s(value)}"


def fmt_actionset(inst, boost=False):
    key = inst.params[0].values[0]
    name = inst.params[1].values[0]
    # return f"{INDENT*inst.depth}self._act[{key!r}] = self.actionset[{key!r}]"
    if boost:
        return f"{INDENT*inst.depth}self.init_action({key!r}, {name!r}, boost={boost!r})"
    else:
        return f"{INDENT*inst.depth}self.init_action({key!r}, {name!r})"


def fmt_actionsetboost(inst):
    return fmt_actionset(inst, boost=True)


def fmt_rand(inst):
    name = inst.params[0].values[0]
    try:
        lower = inst.params[1].values[0]
        upper = inst.params[2].values[0]
        return f"{INDENT*inst.depth}{s(name)} = random.randint({lower}, {upper})"
    except:
        return f"{INDENT*inst.depth}{s(name)} = random.randint(0, 100)"


def get_condition(inst):
    condition = []
    for param in inst.params:
        try:
            condition.append(fmt_binary_opt(param.compare, param.values))
        except IndexError:
            cond = inst.params[0].values[0]
            if isinstance(cond, str) and cond[0] == "_":
                Root.add_rt_var(cond)
            condition.append(s(cond))
    return " and ".join(condition)


def fmt_if(inst):
    return f"{INDENT*inst.depth}if {get_condition(inst)}:"


def fmt_elif(inst):
    return f"{INDENT*inst.depth}elif {get_condition(inst)}:"


def fmt_else(inst):
    return f"{INDENT*inst.depth}else:"


def fmt_end(inst):
    return f"{INDENT*inst.depth}return"


def fmt_func(inst):
    name = inst.params[0].values[0]
    # fn_params = ', '.join(map(lambda fp: fp.py_str(comment=False), inst.function_params))
    return f"{INDENT*inst.depth}{s(name)}()"


def fmt_jump(inst):
    depth = inst.depth - inst.jump_target.depth
    return f"{INDENT*depth}{inst.jump_target.py_str()}"


def fmt_settarget(inst):
    target = Target(inst.params[0].values[0])
    return f"{INDENT*inst.depth}self.target({target})"


def fmt_add(inst):
    name = inst.params[0].values[0]
    value = inst.params[1].values[0]
    return f"{INDENT*inst.depth}{s(name)} += {s(value)}"


def fmt_sub(inst):
    name = inst.params[0].values[0]
    value = inst.params[1].values[0]
    return f"{INDENT*inst.depth}{s(name)} -= {s(value)}"


def fmt_timer(inst):
    value = inst.params[0].values[0]
    return f"{INDENT*inst.depth}self.rec_timer({s(value)})"


def fmt_alivenum(inst):
    value = inst.params[0].values[0]
    name = inst.params[1].values[0]
    return f"{INDENT*inst.depth}self.alive_num({s(name, prefix='')!r}, {value!r})"


def fmt_move(inst):
    action = Move(inst.params[0].values[0])
    return f"{INDENT*inst.depth}self.move({action})"


def fmt_turn(inst):
    action = Turn(inst.params[0].values[0])
    return f"{INDENT*inst.depth}self.turn({action})"


def fmt_action(inst):
    name = inst.params[0].values[0]
    Root.ACTION_LITERALS[name] = None
    return f"{INDENT*inst.depth}self.action({name!r})"


def fmt_cleardmgcnt(inst):
    s("_indirectDmgCnt")
    return f"{INDENT*inst.depth}self._indirectDmgCnt = 0"


def fmt_wake(inst):
    return f"{INDENT*inst.depth}self.wake()"


def fmt_orderalivefarther(inst):
    return f"{INDENT*inst.depth}self.next_order = {Order.AliveFarther}"


def fmt_ordercloser(inst):
    return f"{INDENT*inst.depth}self.next_order = {Order.Closer}"


def fmt_unusualposture(inst):
    value = inst.params[0].values[0]
    return f"{INDENT*inst.depth}self.unusual_posture({s(value)})"


def fmt_gmsetturn(inst):
    value = inst.params[0].values[0]
    return f"{INDENT*inst.depth}self.turn_count = {s(value)}"


def fmt_gmsetturnevent(inst):
    value = inst.params[0].values[0]
    return f"{INDENT*inst.depth}self.turn_event({s(value)})"


def fmt_gmcompleteturnevent(inst):
    return f"{INDENT*inst.depth}self.turn_event('complete')"


def fmt_gmsetsuddenevent(inst):
    value = inst.params[0].values[0]
    return f"{INDENT*inst.depth}self.sudden_event({s(value)})"


def fmt_gmsetbanditevent(inst):
    value = inst.params[0].values[0]
    return f"{INDENT*inst.depth}self.bandit_event({s(value)})"


def fmt_rechprate(inst):
    return f"{INDENT*inst.depth}self._recHpRate = 1"


def fmt_unitnumincircle(inst):
    variable = s(inst.params[0].values[0])
    minimum = s(inst.params[1].values[0])
    maximum = s(inst.params[2].values[0])
    return f"{INDENT*inst.depth}if not ({minimum} <= {variable} <= {maximum}):\n{INDENT*(inst.depth+1)}return"


def fmt_multiply(inst):
    name = inst.params[0].values[0]
    value = inst.params[1].values[0]
    return f"{INDENT*inst.depth}{s(name)} *= {s(value)}"


FMT_PYTHON = {
    Command.Def: fmt_def,
    Command.Set: fmt_set,
    Command.FromActionSet: fmt_actionset,
    Command.EndDef: fmt_null,
    Command.Random: fmt_rand,
    Command.If: fmt_if,
    Command.EndIf: fmt_null,
    Command.ElseIF: fmt_elif,
    Command.Else: fmt_else,
    Command.EndScript: fmt_end,
    Command.Function: fmt_func,
    Command.Jump: fmt_jump,
    Command.SetTarget: fmt_settarget,
    Command.Add: fmt_add,
    Command.Sub: fmt_sub,
    Command.RecTimer: fmt_timer,
    Command.AliveNum: fmt_alivenum,
    Command.MoveAction: fmt_move,
    Command.TurnAction: fmt_turn,
    Command.Action: fmt_action,
    Command.ClearDmgCnt: fmt_cleardmgcnt,
    Command.Wake: fmt_wake,
    Command.OrderAliveFarther: fmt_orderalivefarther,
    Command.OrderCloser: fmt_ordercloser,
    Command.UnusualPosture: fmt_unusualposture,
    Command.GM_SetTurnMax: fmt_gmsetturn,
    Command.GM_SetTurnEvent: fmt_gmsetturnevent,
    Command.GM_CompleteTurnEvent: fmt_gmcompleteturnevent,
    Command.GM_SetSuddenEvent: fmt_gmsetsuddenevent,
    Command.GM_SetBanditEvent: fmt_gmsetbanditevent,
    Command.RecHpRate: fmt_rechprate,
    Command.FromActionSetBoost: fmt_actionsetboost,
    Command.UnitNumInCircle: fmt_unitnumincircle,
    Command.Mul: fmt_multiply,
}


class Root:
    HEADER = """import random
from functools import partial
from .. import *

"""
    CLASSDEF = """

class Runner(AiRunner):
    AI_NAME = {!r}
"""
    PYINIT = f"""
    def __init__(self, params):
        super().__init__(params)
        {s('init')}()
"""
    NAME = None
    RT_VAR = {}
    RT_PATTERN = "        self.init_runtime_var({name!r}, {values!r})"
    SET_VALUES = {}
    ACTION_LITERALS = {}

    def __init__(self, name):
        self.NAME = name
        self.depth = 0
        self.idx = 0
        self.children = []
        Root.RT_VAR = {}
        Root.SET_VALUES = {}
        Root.ACTION_LITERALS = {}

    # class Compare(Enum):
    #     largeEqual = 0
    #     smallEqual = 1
    #     repudiation = 2
    #     equal = 3
    #     large = 4
    #     small = 5
    #     none = 6

    @staticmethod
    def add_rt_var(v, value=None, opt=None):
        if v not in Root.RT_VAR:
            Root.RT_VAR[v] = set()
        if value is None and opt is None:
            Root.RT_VAR[v].add(True)
            Root.RT_VAR[v].add(False)
        try:
            value = float(value)
            if opt in (Compare.largeEqual, Compare.small):
                Root.RT_VAR[v].add(value - 0.0001)
            elif opt in (Compare.smallEqual, Compare.large):
                Root.RT_VAR[v].add(value + 0.0001)
            elif opt in (Compare.repudiation, Compare.equal):
                if value == 0:
                    Root.RT_VAR[v].add(1)
                else:
                    Root.RT_VAR[v].add(-value)
        except (TypeError, ValueError):
            pass
        Root.RT_VAR[v].add(value)

    def add_child(self, child):
        self.children.append(child)

    def __repr__(self):
        return "\n".join(map(str, self.children))

    def py_str(self, enemy_actions=None):
        children = "\n".join(map(lambda c: c.py_str(), self.children))

        act_literal_str = ""
        if enemy_actions:
            literals = {}
            for act in Root.ACTION_LITERALS.keys():
                try:
                    literals[act] = enemy_actions.get(int(Root.SET_VALUES[act]))
                except (KeyError, ValueError):
                    pass
            if literals:
                act_literal_str = f"    _ACTION_LITERALS = {literals!r}\n"

        rt_var_str = []
        for name, values in sorted(Root.RT_VAR.items()):
            # converted_values = set()
            # for v in values:
            #     try:
            #         float(v)
            #         converted_values.add(str(v))
            #     except ValueError:
            #         converted_values.add(f"partial(getattr, self, {v!r})")
            try:
                values = tuple(sorted(values))
            except TypeError:
                values = tuple(values)
            rt_var_str.append(Root.RT_PATTERN.format(name=s(name, prefix=""), values=values))
        rt_var_str = "\n".join(rt_var_str)
        # rt_list_str = "" if not rt_var_str else f"    RUNTIME_VARS = {tuple(Root.RT_VAR.keys())}\n"

        return f"{Root.HEADER}{Root.CLASSDEF.format(self.NAME)}{act_literal_str}{Root.PYINIT}{rt_var_str}\n\n{children}"


class Param:
    VALUE_TYPE = {0: "valString", 1: "valInt", 2: "valFloat"}

    @staticmethod
    def truthy(x):
        if not bool(x):
            return False
        elif x == "0":
            return False
        elif isinstance(x, list) and x == ["0"]:
            return False
        return True

    def __init__(self, values, compare, depth=1):
        self.depth = depth
        # self.values = map(lambda res: dict(filter(lambda x: Param.falsy(x[1]), res.items())), values)
        self.values = list(map(lambda v: v[Param.VALUE_TYPE[v["valType"]]], values))
        self.compare = Compare(compare)

    def __repr__(self):
        value_str = ", ".join(map(str, self.values))
        return f"{INDENT*self.depth}{self.compare}({value_str})"

    def short_repr(self):
        value_str = ",".join(map(str, self.values))
        if self.compare == Compare.none:
            return f"{value_str}"
        else:
            return f"{self.compare}({value_str})"


class Instruction:
    def __init__(self, idx, container, depth=0):
        self.depth = depth
        self.idx = idx
        self.command = Command(container["_command"])
        self.jump = container["_jumpStep"]
        self.jump_target = None
        self.params = []
        for param in container["_params"]:
            for col in param["columns"]:
                self.params.append(Param(col["values"], col["compare"], depth=self.depth + 1))
        self.children = []
        self.function_params = []

    def update_depth(self, depth):
        self.depth = depth
        for param in self.params:
            param.depth = depth + 1

    def add_child(self, child):
        child.update_depth(self.depth + 1)
        self.children.append(child)

    def __repr__(self):
        repr_str = f"{INDENT*self.depth}IDX: {self.idx}, {self.command}, JMP: {self.jump}\n"
        if self.params:
            param_str = "\n".join(map(str, self.params))
            repr_str += f"{INDENT*self.depth}PARAMETERS:\n{param_str}\n"
        if self.jump_target:
            repr_str += f"{INDENT*self.depth}TARGET: [IDX: {self.jump_target.idx}, {self.jump_target.command}]\n"
        if self.children:
            child_Str = "".join(map(str, self.children))
            repr_str += f"{INDENT*self.depth}CHILDREN:\n{child_Str}"
        return repr_str

    def py_str(self, comment=True):
        try:
            out = FMT_PYTHON[self.command](self)
            if comment:
                out += f" # [{self.idx}] {self.command}"
                param_str = ", ".join(map(lambda p: p.short_repr(), self.params))
                if param_str:
                    out += f"({param_str})"
                if self.jump > 1:
                    out += f", JMP: {self.jump}"
            if self.children:
                out += "\n" + "\n".join(map(lambda c: c.py_str(), self.children))
            return out
        except KeyError:
            return str(self)


def link_instructions(instructions, root, offset=0, limit=None):
    while offset < len(instructions):
        inst = instructions[offset]
        inst.update_depth(root.depth + 1)
        root.add_child(inst)
        if inst.command == Command.Jump:
            inst.jump_target = instructions[offset + inst.jump]

        offset += 1
        if inst.command == Command.EndDef or (limit and offset >= limit):
            return offset
        elif inst.command == Command.Def:
            offset = link_instructions(instructions, inst, offset=offset)
        elif inst.command in (Command.If, Command.ElseIF, Command.Else):
            offset = link_instructions(instructions, inst, offset=offset, limit=offset + inst.jump - 1)
        # elif inst.command == Command.Function:
        #     next_jump = offset
        #     while next_jump < len(instructions) and instructions[next_jump].command not in (Command.Jump, Command.Function, Command.If, Command.ElseIF, Command.Else, Command.EndIf):
        #         next_jump += 1
        #     if next_jump > offset:
        #         inst.function_params = instructions[offset:next_jump]
        #         offset = next_jump
    return offset


def load_aiscript_file(file_path, enemy_actions=None):
    name = None
    instructions = []
    depth = 0
    with open(file_path, "r") as f:
        try:
            raw = json.load(f)
        except json.decoder.JSONDecodeError:
            return
        name = raw["name"]
        for idx, container in enumerate(raw["_containers"]):
            inst = Instruction(idx, container, depth=depth)
            instructions.append(inst)
    root = Root(name)
    link_instructions(instructions, root)
    with open(os.path.join(OUTPUT, f"{name}.py"), "w") as fn:
        fn.write(root.py_str(enemy_actions=enemy_actions))


def load_aiscript(path, reformat=True):
    check_target_path(OUTPUT)
    enemy_actions = None
    # enemy_actions = EnemyAction(DBViewIndex())
    for root, _, files in os.walk(path):
        for file_name in tqdm(files, desc="aiscript"):
            load_aiscript_file(os.path.join(root, file_name))
    if reformat:
        print("\nReformatting...", flush=True)
        try:
            subprocess.call(["black", "--quiet", "--line-length", "200", OUTPUT])
        except subprocess.CalledProcessError:
            print("Python black not installed", flush=True)
        print("Done", flush=True)


if __name__ == "__main__":
    # check_target_path(OUTPUT)
    # load_aiscript_file('./_extract/jp/aiscript/HBS_0020301_01.json')
    load_aiscript("./_ex_sim/jp/aiscript")
