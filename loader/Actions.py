import json
import os
import sys
from glob import glob
from tqdm import tqdm
from loader.Database import DBManager, DBTableMetadata, ShortEnum
import re


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
# KAT_CHR_07_H01_LV01_CHLV02

# HIT_LABEL_LV_CHLV = re.compile(r".*(_LV\d{2})(_CHLV\d{2})?.*")
LV_PATTERN = re.compile(r"_LV\d{2}.*")


def build_hitlabel_data(ref, k, hit_labels):
    if not hit_labels:
        return tuple()
    if isinstance(hit_labels, str):
        hit_labels = (hit_labels,)
    processed = []
    for idx, label in enumerate(hit_labels):
        label = label.strip()
        if not label:
            continue
        # has_lv = False
        # has_chlv = False
        # if lv_chlv := HIT_LABEL_LV_CHLV.match(label):
        #     if lv_group := lv_chlv.group(1):
        #         has_lv = True
        #         label = label.replace(lv_group, "_LV{lv}")
        #     if chlv_group := lv_chlv.group(2):
        #         has_chlv = True
        #         label = label.replace(chlv_group, "_CHLV{chlv}")
        if label.startswith("CMN_AVOID"):
            label_glob = label
        elif LV_PATTERN.search(label):
            label_glob = LV_PATTERN.sub("_LV[0-9][0-9]*", label)
        else:
            label_glob = f"{label}*"
        processed.append(
            {
                "_Id": f"{ref}{k}{idx}",
                "_ref": ref,
                "_source": k,
                "_hitLabel": label,
                "_hitLabelGlob": label_glob,
                # "_hasCHLV": has_chlv,
            }
        )
    return processed
    # return (
    #     {
    #         "_Id": f"{ref}{k}{idx}",
    #         "_ref": ref,
    #         "_hitLabel": label.strip(),
    #         "_source": k,
    #     }
    #     for idx, label in enumerate(hit_labels)
    #     if label.strip()
    # )


# seen_id = set()
def build_db_data(meta, ref, seq, data):
    db_data = {}
    hitlabel_data = []
    for k in meta.field_type.keys():
        if k in data:
            if ACTION_PART.get_field(k) == DBTableMetadata.BLOB and not any(data[k]):
                db_data[k] = None
            elif isinstance(data[k], str):
                db_data[k] = data[k].strip()
            else:
                db_data[k] = data[k]
        else:
            db_data[k] = None
    db_data["_Id"] = f"{ref}{seq:05}"
    db_data["_ref"] = int(ref)
    db_data["_seq"] = seq
    for k in HIT_LABEL_FIELDS:
        if k in data:
            hitlabel_data.extend(build_hitlabel_data(db_data["_Id"], k, data[k]))
    if loop := data.get("_loopData"):
        db_data["_loopFlag"] = loop["flag"]
        db_data["_loopNum"] = loop["loopNum"]
        db_data["_loopFrame"] = loop["restartFrame"]
        db_data["_loopSec"] = loop["restartSec"]
    # if db_data['_Id'] in seen_id:
    #     print(db_data['_Id'])
    # seen_id.add(db_data['_Id'])
    cond_data = data["_conditionData"]
    if cond_data["_conditionType"] and any(cond_data["_conditionValue"]):
        db_data["_conditionType"] = cond_data["_conditionType"]
        db_data["_conditionValue"] = cond_data["_conditionValue"]
    return db_data, hitlabel_data


def build_arrange_data(meta, ref, seq, data):
    if not data.get("_abHitAttrLabel"):
        return None, None
    return build_db_data(meta, ref, seq, data)


def build_bullet(meta, ref, seq, data):
    db_data, hitlabel_data = build_db_data(meta, ref, seq, data)
    if ab_label := data["_arrangeBullet"]["_abHitAttrLabel"]:
        hitlabel_data.extend(build_hitlabel_data(db_data["_Id"], "_abHitAttrLabel", ab_label))
    if ab_duration := data["_arrangeBullet"]["_abDuration"]:
        db_data["_abDuration"] = ab_duration
    if ab_interval := data["_arrangeBullet"]["_abHitInterval"]:
        db_data["_abHitInterval"] = ab_interval
    return db_data, hitlabel_data


def build_formation_bullet(meta, ref, seq, data):
    bullet_num = 0
    bullet_data = None
    for c in data["_child"]:
        try:
            if c["bulletData"]["_hitAttrLabel"]:
                bullet_num += 1
                bullet_data = c["bulletData"]
        except:
            pass
    if bullet_data:
        db_data, hitlabel_data = build_db_data(meta, ref, seq, bullet_data)
        db_data["commandType"] = 100
        db_data["_bulletNum"] = bullet_num
        return db_data, hitlabel_data
    else:
        return None, None


def build_marker(meta, ref, seq, data):
    db_data, hitlabel_data = build_db_data(meta, ref, seq, data)
    if charge_lvl_sec := db_data.get("_chargeLvSec"):
        if "_nextLevelMarkerCount" in data and data["_nextLevelMarkerCount"]:
            for lvl in data["_nextLevelMarkerData"]:
                charge_lvl_sec.extend(lvl["_chargeLvSec"])
        if not any(charge_lvl_sec):
            db_data["_chargeLvSec"] = None
        else:
            db_data["_chargeLvSec"] = charge_lvl_sec
    if not db_data["_chargeSec"] and not db_data["_chargeLvSec"]:
        return None, None
    return db_data, hitlabel_data


def build_animation(meta, ref, seq, data):
    db_data, hitlabel_data = build_db_data(meta, ref, seq, data)
    if "_name" in data and data["_name"]:
        db_data["_animationName"] = data["_name"]
        return db_data, hitlabel_data
    return None, None


def build_control_data(meta, ref, seq, data):
    db_data, hitlabel_data = build_db_data(meta, ref, seq, data)
    arg_data = {}
    for key, value in data.items():
        if key not in db_data and not isinstance(value, dict):
            if isinstance(value, list):
                if any(value):
                    arg_data[key] = value
            elif value:
                arg_data[key] = value
    if arg_data:
        db_data["_charaCommandArgs"] = arg_data
        return db_data, hitlabel_data
    return None, None


ACTION_PART = DBTableMetadata(
    "ActionParts",
    pk="_Id",
    field_type={
        "_Id": DBTableMetadata.INT + DBTableMetadata.PK,
        "_ref": DBTableMetadata.INT,
        "_seq": DBTableMetadata.INT,
        "_seconds": DBTableMetadata.REAL,
        "_speed": DBTableMetadata.REAL,
        "_duration": DBTableMetadata.REAL,
        "_activateId": DBTableMetadata.INT,
        "commandType": DBTableMetadata.INT,
        # PLAY_MOTION
        "_motionState": DBTableMetadata.TEXT,
        "_motionFrame": DBTableMetadata.INT,
        "_blendDuration": DBTableMetadata.REAL,
        "_isBlend": DBTableMetadata.INT,
        "_isEndSyncMotion": DBTableMetadata.INT,
        "_isIgnoreFinishCondition": DBTableMetadata.INT,
        "_isIdleAfterCancel": DBTableMetadata.INT,
        # MOVEMENT
        # '_position': DBTableMetadata.BLOB,
        # '_pushOut': DBTableMetadata.INT,
        # '_autoDash': DBTableMetadata.INT,
        # '_chargeMarker': DBTableMetadata.INT,
        # '_gravity': DBTableMetadata.REAL,
        # '_moveStyle': DBTableMetadata.INT,
        # '_teleportPosition': DBTableMetadata.INT,
        # '_teleportDirection': DBTableMetadata.INT,
        # '_distance': DBTableMetadata.INT,
        # ROTATION
        # '_rotation': DBTableMetadata.BLOB,
        # MARKER
        "_chargeSec": DBTableMetadata.REAL,
        "_chargeLvSec": DBTableMetadata.BLOB,
        # '_chargeAfterSec': DBTableMetadata.REAL,
        # '_ignoredByPlayerAI': DBTableMetadata.INT,
        # '_invisibleForPlayerAI': DBTableMetadata.INT,
        # '_playerAIEscapeDir': DBTableMetadata.INT,
        # '_ignoredImpactWaitForPlayerColor': DBTableMetadata.INT,
        # HIT/BULLET
        "_bulletSpeed": DBTableMetadata.REAL,
        "_bulletDuration": DBTableMetadata.REAL,
        "_delayTime": DBTableMetadata.REAL,
        "_isHitDelete": DBTableMetadata.INT,
        "_abHitInterval": DBTableMetadata.REAL,
        "_abDuration": DBTableMetadata.REAL,
        "_bulletNum": DBTableMetadata.INT,
        "_fireMaxCount": DBTableMetadata.INT,
        "_generateNum": DBTableMetadata.INT,
        "_generateDelay": DBTableMetadata.REAL,
        "_generateNumDependOnBuffCount": DBTableMetadata.INT,
        "_buffCountConditionId": DBTableMetadata.INT,
        "_setBulletDelayOneByOne": DBTableMetadata.INT,
        "_bulletDelayTime": DBTableMetadata.BLOB,
        "_lifetime": DBTableMetadata.REAL,
        "_conditionType": DBTableMetadata.INT,
        "_conditionValue": DBTableMetadata.BLOB,
        "_attenuationRate": DBTableMetadata.REAL,
        # COLLISION
        "_collision": DBTableMetadata.INT,
        "_collisionPosId": DBTableMetadata.INT,
        "_collisionParams_01": DBTableMetadata.REAL,  # Length
        "_collisionParams_02": DBTableMetadata.REAL,  # Width
        "_collisionParams_03": DBTableMetadata.REAL,  # Height
        "_collisionParams_05": DBTableMetadata.REAL,  # Angle
        "_collisionParams_06": DBTableMetadata.REAL,
        "_collisionHitInterval": DBTableMetadata.REAL,
        # SEND_SIGNAL
        "_signalType": DBTableMetadata.INT,
        "_decoId": DBTableMetadata.INT,
        "_actionId": DBTableMetadata.INT,
        "_keepActionEnd": DBTableMetadata.INT,
        "_keepActionId1": DBTableMetadata.INT,
        "_keepActionId2": DBTableMetadata.INT,
        # ACTIVE_CANCEL
        "_actionType": DBTableMetadata.INT,
        "_motionEnd": DBTableMetadata.INT,
        # CONTROL
        "_charaCommand": DBTableMetadata.INT,
        "_charaCommandArgs": DBTableMetadata.BLOB,
        # BULLETS - contains marker data, unsure if it does anything
        # '_useMarker': DBTableMetadata.INT,
        # '_marker': DBTableMetadata.BOLB (?)
        "_isDelayAffectedBySpeedFactor": DBTableMetadata.INT,
        # ANIMATION
        "_animationName": DBTableMetadata.TEXT,
        "_isVisible": DBTableMetadata.INT,
        "_isActionClear": DBTableMetadata.INT,
        # ACTION_CONDITON
        "_actionConditionId": DBTableMetadata.INT,
        # BUFF_FIELD_ATTACH
        "_isAttachToBuffField": DBTableMetadata.INT,
        "_isAttachToSelfBuffField": DBTableMetadata.INT,
        "_hitDelaySec": DBTableMetadata.REAL,
        # LOOP DATA
        "_loopFlag": DBTableMetadata.INT,
        "_loopNum": DBTableMetadata.INT,
        "_loopFrame": DBTableMetadata.INT,
        "_loopSec": DBTableMetadata.REAL,
        # TIMESTOP
        "_stopMotionPositionSec": DBTableMetadata.REAL,
        "_stopTimeSpanSec": DBTableMetadata.REAL,
        "_isRepeat": DBTableMetadata.INT,
        "_isOverridePlaySpeed": DBTableMetadata.INT,
        "_playSpeed": DBTableMetadata.REAL,
        # TIMECURVE
        "_isNormalizeCurve": DBTableMetadata.INT,
        # AUTOFIRE
        "_autoFireInterval": DBTableMetadata.REAL,
        "_autoFireActionId": DBTableMetadata.INT,
        "_autoFireActionIdList": DBTableMetadata.BLOB,
        "_autoFireEffectTrigger": DBTableMetadata.INT,
        "_autoFireEffectTriggerResetTime": DBTableMetadata.REAL,
        "_autoFireAutoSearchEnemyRadius": DBTableMetadata.REAL,
        # servant
        "_servantActionCommandId": DBTableMetadata.INT,
    },
)

ACTION_PART_HIT_LABEL = DBTableMetadata(
    "ActionPartsHitLabel",
    pk="_Id",
    field_type={
        "_Id": DBTableMetadata.TEXT + DBTableMetadata.PK,
        "_ref": DBTableMetadata.INT,
        "_source": DBTableMetadata.TEXT,
        "_hitLabel": DBTableMetadata.TEXT,
        "_hitLabelGlob": DBTableMetadata.TEXT,
        # "_hasLV": DBTableMetadata.INT,
        # "_hasCHLV": DBTableMetadata.INT,
    },
)

PROCESSORS = {}
PROCESSORS[CommandType.PLAY_MOTION] = build_db_data
PROCESSORS[CommandType.GEN_MARKER] = build_marker
PROCESSORS[CommandType.GEN_BULLET] = build_bullet
PROCESSORS[CommandType.HIT_ATTRIBUTE] = build_db_data
PROCESSORS[CommandType.HIT_STOP] = build_db_data
PROCESSORS[CommandType.MOVE_TIME_CURVE] = build_db_data
PROCESSORS[CommandType.ARRANGE_BULLET] = build_arrange_data
PROCESSORS[CommandType.SEND_SIGNAL] = build_db_data
PROCESSORS[CommandType.ACTIVE_CANCEL] = build_db_data
PROCESSORS[CommandType.MULTI_BULLET] = build_bullet
PROCESSORS[CommandType.PARABOLA_BULLET] = build_bullet
PROCESSORS[CommandType.PIVOT_BULLET] = build_bullet
PROCESSORS[CommandType.STOCK_BULLET_ROUND] = build_bullet
PROCESSORS[CommandType.STOCK_BULLET_FIRE] = build_bullet
PROCESSORS[CommandType.FORMATION_BULLET] = build_formation_bullet
PROCESSORS[CommandType.SETTING_HIT] = build_db_data
PROCESSORS[CommandType.REMOVE_BUFF_TRIGGER_BOMB] = build_db_data
PROCESSORS[CommandType.BUFF_CAPTION] = build_db_data
PROCESSORS[CommandType.BUFFFIELD_ATTACHMENT] = build_db_data
PROCESSORS[CommandType.BUTTERFLY_BULLET] = build_bullet
PROCESSORS[CommandType.STOCK_BULLET_SHIKIGAMI] = build_bullet
PROCESSORS[CommandType.CHARACTER_COMMAND] = build_control_data


def log_schema_keys(schema_map, data, command_type):
    schema_map[f'{data["commandType"]:03}-{command_type}'] = {key: type(value).__name__ for key, value in data.items()}
    for subdata in data.values():
        try:
            if command_type := subdata.get("commandType"):
                log_schema_keys(schema_map, subdata, CommandType(command_type))
        except:
            pass


def load_actions(db, path):
    schema_map = {}
    db.drop_table(ACTION_PART.name)
    db.create_table(ACTION_PART)
    db.drop_table(ACTION_PART_HIT_LABEL.name)
    db.create_table(ACTION_PART_HIT_LABEL)
    sorted_data = []
    sorted_hitlabel_data = []
    for filepath in tqdm(glob(path + "/PlayerAction*"), desc="action"):
        ref = os.path.splitext(filepath.split("_")[-1])[0]
        with open(filepath) as f:
            raw = json.load(f)
            # action = [gameObject['_data'] for gameObject in raw if '_data' in gameObject.keys()]
            action = []
            seq = 0
            for actdata in raw:
                action.append(actdata)
                if (additional := actdata.get("_additionalCollision")) and actdata.get("_addNum"):
                    for i, act in enumerate(additional):
                        if i >= actdata["_addNum"]:
                            break
                        act["_seconds"] += actdata["_seconds"]
                        action.append(act)
                    # action.extend(((seq+100*(1+i), act) for i, act in enumerate(additional)))
            for seq, data in enumerate(action):
                try:
                    command_type = CommandType(data["commandType"])
                except TypeError:
                    command_type = data["commandType"]
                    print(f"Unknown command type {command_type} in {filepath}")
                log_schema_keys(schema_map, data, command_type)
                if command_type in PROCESSORS.keys():
                    builder = PROCESSORS[command_type]
                    db_data, hitlabel_data = builder(ACTION_PART, ref, seq, data)
                    if db_data is not None:
                        sorted_data.append(db_data)
                    if hitlabel_data:
                        sorted_hitlabel_data.extend(hitlabel_data)
    db.insert_many(ACTION_PART.name, sorted_data)
    db.insert_many(ACTION_PART_HIT_LABEL.name, sorted_hitlabel_data)
    return schema_map


def summarize_raw_action_json(raw, key=""):
    for seq, actdata in enumerate(raw):
        if not actdata:
            continue
        if not isinstance(actdata, dict):
            continue
        if not "commandType" in actdata:
            continue
        cmd = CommandType(actdata["commandType"])
        sec = actdata["_seconds"]
        if key:
            print(f"{key}:")
        if cmd in PROCESSORS:
            print(f"{seq:03} {sec:.4f}s: {cmd.value:03}-{cmd} [PROCESSED]")
        else:
            print(f"{seq:03} {sec:.4f}s: {cmd.value:03}-{cmd} [SKIPPED]")
        for k, v in actdata.items():
            if isinstance(v, list):
                summarize_raw_action_json(v, f"{key}.{k}")
            else:
                summarize_raw_action_json((v,), f"{key}.{k}")


if __name__ == "__main__":
    db = DBManager()
    if len(sys.argv) > 1:
        path = f"./_ex_sim/jp/actions/PlayerAction_{sys.argv[1]:>08}.json"
        print(path)
        with open(path) as f:
            raw = json.load(f)
            summarize_raw_action_json((item.get("_data") for item in raw))
    else:
        schema_map = load_actions(db, "./_ex_sim/jp/actions")
        with open("./out/_action_schema.json", "w") as f:
            json.dump(schema_map, f, indent=4, sort_keys=True, default=str)
