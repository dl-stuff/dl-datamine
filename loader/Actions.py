import itertools
import json
import re
from glob import glob
from tqdm import tqdm

from loader.Database import DBManager, DBTableMetadata, ShortEnum


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
    RESERVE_71 = 152
    RESERVE_72 = 153
    RESERVE_73 = 154
    RESERVE_74 = 155
    RESERVE_75 = 156
    RESERVE_76 = 157
    RESERVE_77 = 158
    RESERVE_78 = 159
    RESERVE_79 = 160
    RESERVE_80 = 161
    RESERVE_81 = 162
    RESERVE_82 = 163
    RESERVE_83 = 164
    RESERVE_84 = 165
    RESERVE_85 = 166
    RESERVE_86 = 167
    RESERVE_87 = 168
    RESERVE_88 = 169
    RESERVE_89 = 170
    RESERVE_90 = 171
    RESERVE_91 = 172
    RESERVE_92 = 173
    RESERVE_93 = 174
    RESERVE_94 = 175
    RESERVE_95 = 176
    RESERVE_96 = 177
    RESERVE_97 = 178
    RESERVE_98 = 179
    RESERVE_99 = 180
    RESERVE_100 = 181


HIT_LABEL_FIELDS = (
    "_hitLabel",
    "_hitAttrLabel",
    "_hitAttrLabelSubList",
    "_abHitAttrLabel",
)
LV_PATTERN = re.compile(r"_LV\d{2}.*")


PARTS_INDEX = DBTableMetadata(
    "PartsIndex",
    pk="pk",
    field_type={
        "pk": DBTableMetadata.INT + DBTableMetadata.PK,
        "act": DBTableMetadata.INT,
        "seq": DBTableMetadata.INT,
        "part": DBTableMetadata.TEXT,
    },
)

PARTS_HITLABEL = DBTableMetadata(
    "PartsHitLabel",
    pk="pk",
    field_type={
        "pk": DBTableMetadata.INT + DBTableMetadata.PK,
        "act": DBTableMetadata.INT,
        "seq": DBTableMetadata.INT,
        "source": DBTableMetadata.TEXT,
        "hitLabel": DBTableMetadata.TEXT,
        "hitLabelGlob": DBTableMetadata.TEXT,
    },
)


def process_action_part_label(pk, cnt, label, processed, action_id, seq, k, data):
    label_pk = pk + f"{next(cnt):03}"
    if label.startswith("CMN_AVOID"):
        label_glob = label
    elif LV_PATTERN.search(label):
        label_glob = LV_PATTERN.sub("_LV[0-9][0-9]*", label)
    else:
        label_glob = f"{label}*"
    processed[PARTS_HITLABEL.name].append(
        {
            "pk": label_pk,
            "act": action_id,
            "seq": seq,
            "source": k,
            "hitLabel": label,
            "hitLabelGlob": label_glob,
        }
    )
    data[k] = label_pk
    return label_pk


def process_action_part(action_id, seq, data, processed, tablemetas, key=None, cnt=None):
    non_empty = False
    for v in data.values():
        try:
            non_empty = any(v)
        except TypeError:
            non_empty = bool(v)
        if non_empty:
            break
    if not non_empty:
        return None

    try:
        tbl = "Parts_" + CommandType(data["commandType"]).name
    except KeyError:
        tbl = "PartsParam" + "_" + key.strip("_")
    pk = f"{action_id}{seq:03}"
    if key is None:
        processed[PARTS_INDEX.name].append(
            {
                "pk": pk,
                "act": action_id,
                "seq": seq,
                "part": tbl,
            }
        )
    if cnt is None:
        cnt = itertools.count()
    else:
        pk += f"{next(cnt):03}"
    try:
        meta = tablemetas[tbl]
    except KeyError:
        meta = DBTableMetadata(
            tbl,
            pk="pk",
            field_type={
                "pk": DBTableMetadata.INT + DBTableMetadata.PK,
                "act": DBTableMetadata.INT,
                "seq": DBTableMetadata.INT,
            },
        )
        tablemetas[tbl] = meta
        processed[tbl] = []

    for k, v in data.copy().items():
        if k in HIT_LABEL_FIELDS:
            if not v:
                data[k] = None
                continue
            if k == "_hitAttrLabelSubList":
                # if len(tuple(filter(None, v))) == 1:
                #     label = v[0]
                # else:
                #     raise Exception((k, v))
                for idx, label in enumerate(v):
                    new_k = k
                    if idx:
                        new_k = f"_hitAttrLabelSubList{idx}"
                    meta.field_type[new_k] = DBTableMetadata.INT
                    if not label:
                        data[new_k] = None
                        continue
                    data[new_k] = process_action_part_label(pk, cnt, label, processed, action_id, seq, new_k, data)
            else:
                data[k] = process_action_part_label(pk, cnt, v, processed, action_id, seq, k, data)
            meta.field_type[k] = DBTableMetadata.INT
        elif isinstance(v, dict):
            # if v.get("commandType"):
            child_result = process_action_part(action_id, seq, v, processed, tablemetas, key=k, cnt=cnt)
            if child_result:
                child_tbl, child_pk = child_result
                data[k] = child_pk
                meta.foreign_keys[k] = (child_tbl, "pk")
            else:
                data[k] = None
            meta.field_type[k] = DBTableMetadata.INT
            # else:
            #     meta.field_type[k] = DBTableMetadata.BLOB
        elif isinstance(v, list):
            if not v or not any(v):
                data[k] = None
            meta.field_type[k] = DBTableMetadata.BLOB
        elif isinstance(v, int):
            meta.field_type[k] = DBTableMetadata.INT
        elif isinstance(v, float):
            meta.field_type[k] = DBTableMetadata.REAL
        elif isinstance(v, str):
            meta.field_type[k] = DBTableMetadata.TEXT
        else:
            meta.field_type[k] = DBTableMetadata.BLOB

    data["pk"] = pk
    data["act"] = action_id
    data["seq"] = seq

    processed[tbl].append(data)

    return tbl, pk


def load_actions(db, actions_dir):
    processed = {
        PARTS_INDEX.name: [],
        PARTS_HITLABEL.name: [],
    }
    tablemetas = {
        PARTS_INDEX.name: PARTS_INDEX,
        PARTS_HITLABEL.name: PARTS_HITLABEL,
    }
    for filename in tqdm(glob(actions_dir + "/PlayerAction_*.json"), desc="read_actions"):
        action_id = filename.split("_")[-1].replace(".json", "")
        with open(filename, "r") as fn:
            for seq, part in enumerate(json.load(fn)):
                process_action_part(action_id, seq, part, processed, tablemetas)

    for tbl, meta in tqdm(tablemetas.items(), desc="load_actions"):
        db.drop_table(tbl)
        db.create_table(meta)
        db.insert_many(tbl, processed[tbl], mode=DBManager.REPLACE)


if __name__ == "__main__":
    db = DBManager()
    load_actions(db, "./_ex_sim/jp/actions")
