import json
import os
from enum import Enum
from tqdm import tqdm
from loader.Database import check_target_path

OUTPUT = 'out/_aiscript'

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
	Reserve06 = 32
	Reserve07 = 33
	Reserve08 = 34
	Reserve09 = 35
	Reserve10 = 36


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
    # assumed names
	ARENA_CENTER = 48


class Compare(Enum):
	largeEqual = 0
	smallEqual = 1
	repudiation = 2
	equal = 3
	large = 4
	small = 5
	none = 6

def s(v):
    if isinstance(v, str):
        if v[0] == '_':
            Root.GLOBAL_VAR.add(v)
            return v
        else:
            return f'self.var_{v}'
    else:
        return v
FMT_COMPARE = {
    Compare.largeEqual: lambda v: f'{s(v[0])} <= {s(v[1])}',
    Compare.smallEqual: lambda v: f'{s(v[0])} >= {s(v[1])}',
    Compare.repudiation: lambda v: f'{s(v[0])} != {s(v[1])}',
    Compare.equal: lambda v: f'{s(v[0])} == {s(v[1])}',
    Compare.large: lambda v: f'{s(v[0])} < {s(v[1])}',
    Compare.small: lambda v: f'{s(v[0])} > {s(v[1])}',
}

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

class Order(Enum):
    Closer = 1
    AliveFarther = 2

INDENT = '    '

def fmt_null(inst):
    return f'{INDENT*inst.depth}pass'

def fmt_def(inst):
    name = inst.params[0].values[0]
    return f'\n{INDENT*inst.depth}def {name}(self):'

def fmt_set(inst):
    name = inst.params[0].values[0]
    value = inst.params[1].values[0]
    return f'{INDENT*inst.depth}{s(name)} = {s(value)}'

def fmt_actionset(inst):
    key = inst.params[0].values[0]
    name = inst.params[1].values[0]
    return f'{INDENT*inst.depth}{s(name)} = _action_set[\'{key}\']'

def fmt_rand(inst):
    name = inst.params[0].values[0]
    try:
        lower = inst.params[1].values[0]
        upper = inst.params[2].values[0]
        return f'{INDENT*inst.depth}{s(name)} = random.randint({lower}, {upper})'
    except:
        return f'{INDENT*inst.depth}{s(name)} = random.randint(0, 100)'

def get_condition(inst):
    condition = []
    for param in inst.params:
        try:
            condition.append(FMT_COMPARE[param.compare](param.values))
        except KeyError:
            condition.append(s(inst.params[0].values[0]))
    return ' and '.join(condition)

def fmt_if(inst):
    return f'{INDENT*inst.depth}if {get_condition(inst)}:'

def fmt_elif(inst):
    return f'{INDENT*inst.depth}elif {get_condition(inst)}:'

def fmt_else(inst):
    return f'{INDENT*inst.depth}else:'

def fmt_end(inst):
    return f'{INDENT*inst.depth}return'

def fmt_func(inst):
    name = inst.params[0].values[0]
    # fn_params = ', '.join(map(lambda fp: fp.py_str(comment=False), inst.function_params))
    return f'{INDENT*inst.depth}self.{name}()'

def fmt_jump(inst):
    depth = inst.depth - inst.jump_target.depth
    return f'{INDENT*depth}{inst.jump_target.py_str()}'

def fmt_settarget(inst):
    target = Target(inst.params[0].values[0])
    return f'{INDENT*inst.depth}self.next_target = {target}'

def fmt_add(inst):
    name = inst.params[0].values[0]
    value = inst.params[1].values[0]
    return f'{INDENT*inst.depth}{s(name)} += {s(value)}'

def fmt_sub(inst):
    name = inst.params[0].values[0]
    value = inst.params[1].values[0]
    return f'{INDENT*inst.depth}{s(name)} -= {s(value)}'

def fmt_timer(inst):
    value = inst.params[0].values[0]
    if value == 'true':
        return f'{INDENT*inst.depth}RecTimer.on()'
    else:
        return f'{INDENT*inst.depth}RecTimer.off()'

def fmt_alivenum(inst):
    value = inst.params[0].values[0]
    name = inst.params[1].values[0]
    return f'{INDENT*inst.depth}{s(name)} = alive({value})'

def fmt_move(inst):
    action = Move(inst.params[0].values[0])
    return f'{INDENT*inst.depth}move({action})'

def fmt_turn(inst):
    action = Turn(inst.params[0].values[0])
    return f'{INDENT*inst.depth}turn({action})'

def fmt_action(inst):
    name = inst.params[0].values[0]
    return f'{INDENT*inst.depth}action({s(name)})'

def fmt_cleardmgcnt(inst):
    s('_indirectDmgCnt')
    return f'{INDENT*inst.depth}self._indirectDmgCnt = 0'

def fmt_wake(inst):
    return f'{INDENT*inst.depth}wake()'

def fmt_orderalivefarther(inst):
    return f'{INDENT*inst.depth}self.next_order = {Order.AliveFarther}'

def fmt_ordercloser(inst):
    return f'{INDENT*inst.depth}self.next_order = {Order.Closer}'

def fmt_unusualposture(inst):
    value = inst.params[0].values[0]
    if value == 'true':
        return f'{INDENT*inst.depth}UnusualPosture.on()'
    else:
        return f'{INDENT*inst.depth}UnusualPosture.off()'

def fmt_gmsetturn(inst):
    value = inst.params[0].values[0]
    return f'{INDENT*inst.depth}self.Turn = {s(value)}'

def fmt_gmsetturnevent(inst):
    value = inst.params[0].values[0]
    return f'{INDENT*inst.depth}self.turn_event = _event[\'{value}\']'

def fmt_gmcompleteturnevent(inst):
    return f'{INDENT*inst.depth}self.turn_event = None'

def fmt_gmsetsuddenevent(inst):
    value = inst.params[0].values[0]
    return f'{INDENT*inst.depth}self.sudden_event = _event[\'{value}\']'

def fmt_gmsetbanditevent(inst):
    value = inst.params[0].values[0]
    return f'{INDENT*inst.depth}self.bandit_event = _event[\'{value}\']'

def fmt_rechprate(inst):
    return f'{INDENT*inst.depth}recHPRate()'

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
}


class Root:
    HEADER = """import random
from enum import Enum
from .._aiscript import *

_action_set = {}
_event = {}
"""
    NAME = None
    GLOBAL_VAR = set()
    def __init__(self, name):
        self.NAME = name
        self.depth = 0
        self.idx = 0
        self.children = []
        Root.GLOBAL_VAR = set()

    def add_child(self, child):
        self.children.append(child)

    def __repr__(self):
        return '\n'.join(map(str, self.children))

    def py_str(self, comment=False):
        children = '\n'.join(map(lambda c: c.py_str(), self.children))
        global_str = ' = None\n'.join(sorted(list(Root.GLOBAL_VAR)))
        # return f'{Root.HEADER}\nclass {self.NAME}:\n{children}\n{Root.FOOTER}{global_str} = None\n'
        return f'{Root.HEADER}{global_str} = None\n\nclass {self.NAME}:\n{children}'

class Param:
    VALUE_TYPE = {
        0: 'valString',
        1: 'valInt',
        2: 'valFloat'
    }
    @staticmethod
    def truthy(x):
        if not bool(x):
            return False
        elif x == '0':
            return False
        elif isinstance(x, list) and x == ['0']:
            return False
        return True
        
    def __init__(self, values, compare, depth=1):
        self.depth = depth
        # self.values = map(lambda res: dict(filter(lambda x: Param.falsy(x[1]), res.items())), values)
        self.values = list(map(lambda v: v[Param.VALUE_TYPE[v['valType']]], values))
        self.compare = Compare(compare)

    def __repr__(self):
        value_str = ', '.join(map(str, self.values))
        return f'{INDENT*self.depth}{self.compare}({value_str})'

    def short_repr(self):
        value_str = ','.join(map(str, self.values))
        if self.compare == Compare.none:
            return f'{value_str}'
        else:
            return f'{self.compare}({value_str})'


class Instruction:
    def __init__(self, idx, container, depth=0):
        self.depth = depth
        self.idx = idx
        self.command = Command(container['_command'])
        self.jump = container['_jumpStep']
        self.jump_target = None
        self.params = []
        for param in container['_params']:
            for col in param['columns']:
                self.params.append(Param(col['values'], col['compare'], depth=self.depth+1))
        self.children = []
        self.function_params = []

    def update_depth(self, depth):
        self.depth = depth
        for param in self.params:
            param.depth = depth + 1

    def add_child(self, child):
        child.update_depth(self.depth+1)
        self.children.append(child)

    def __repr__(self):
        repr_str = f'{INDENT*self.depth}IDX: {self.idx}, {self.command}, JMP: {self.jump}\n'
        if self.params:
            param_str = '\n'.join(map(str, self.params))
            repr_str += f'{INDENT*self.depth}PARAMETERS:\n{param_str}\n'
        if self.jump_target:
            repr_str += f'{INDENT*self.depth}TARGET: [IDX: {self.jump_target.idx}, {self.jump_target.command}]\n'
        if self.children:
            child_Str = ''.join(map(str, self.children))
            repr_str += f'{INDENT*self.depth}CHILDREN:\n{child_Str}'
        return repr_str

    def py_str(self, comment=True):
        try:
            out = FMT_PYTHON[self.command](self)
            if comment:
                out += f' # [{self.idx}] {self.command}'
                param_str = ', '.join(map(lambda p: p.short_repr(), self.params))
                if param_str:
                    out += f'({param_str})'
                if self.jump > 1:
                    out += f', JMP: {self.jump}'
            if self.children:
                out += '\n' + '\n'.join(map(lambda c: c.py_str(), self.children))
            return out
        except KeyError:
            return str(self)
        


def link_instructions(instructions, root, offset=0, limit=None):
    while offset < len(instructions):
        inst = instructions[offset]
        inst.update_depth(root.depth+1)
        root.add_child(inst)
        if inst.command == Command.Jump:
            inst.jump_target = instructions[offset+inst.jump]

        offset += 1
        if inst.command == Command.EndDef or (limit and offset >= limit):
            return offset
        elif inst.command == Command.Def:
            offset = link_instructions(instructions, inst, offset=offset)
        elif inst.command in (Command.If, Command.ElseIF, Command.Else):
            offset = link_instructions(instructions, inst, offset=offset, limit=offset+inst.jump-1)
        # elif inst.command == Command.Function:
        #     next_jump = offset
        #     while next_jump < len(instructions) and instructions[next_jump].command not in (Command.Jump, Command.Function, Command.If, Command.ElseIF, Command.Else, Command.EndIf):
        #         next_jump += 1
        #     if next_jump > offset:
        #         inst.function_params = instructions[offset:next_jump]
        #         offset = next_jump
    return offset

def load_aiscript_file(file_path):
    name = None
    instructions = []
    depth = 0
    with open(file_path, 'r') as f:
        raw = json.load(f)
        name = raw['name']
        for idx, container in enumerate(raw['_containers']):
            inst = Instruction(idx, container, depth=depth)
            instructions.append(inst)
    root = Root(name)
    link_instructions(instructions, root)
    with open(os.path.join(OUTPUT, f'{name}.py'), 'w') as bolb:
        bolb.write(root.py_str())

def load_aiscript(path):
    check_target_path(path)
    for root, _, files in os.walk(path):
        for file_name in tqdm(files, desc='aiscript'):
            load_aiscript_file(os.path.join(root, file_name))
    
if __name__ == '__main__':
    # check_target_path(OUTPUT)
    # load_aiscript_file('./_extract/jp/aiscript/HBS_0020301_01.json')
    load_aiscript('./_ex_sim/jp/aiscript')