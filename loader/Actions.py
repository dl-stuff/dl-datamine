import json
import os
from tqdm import tqdm
from loader.Database import DBManager, DBTableMetadata
from enum import Enum
import re



class CommandType(Enum):
    UNKNOWN = -1
    PARTS_MOTION = 2
    MOVEMENT = 5
    ROTATION = 7
    MARKER = 8
    BULLET = 9
    HIT = 10
    EFFECT = 11
    SOUND = 12
    CAMERA_MOTION = 13
    SEND_SIGNAL = 14
    ACTIVE_CANCEL = 15
    TARGETING = 17 # spin cancel ?
    ACTION_END = 23
    MULTI_BULLET = 24
    ANIMATION = 25 # or maybe effects ?
    CONTROL = 30 # some kinda control related thing
    COLLISION = 37 # seen in arrange bullet
    PARABOLA_BULLET = 41
    TIMESTOP = 48 # control animation playback ?
    TIMECURVE = 49 # control animation playback ?
    PIVOT_BULLET = 53
    MOVEMENT_IN_SKILL = 54 # only eze s1 uses this
    ROTATION_IN_SKILL = 55
    SATALITE_HIT = 58
    FIRE_STOCK_BULLET = 59
    CONDITION_TEXT = 63 # unsure where text is sourced, not in TextLabel
    SETTING_HIT = 66
    FORMATION_BULLET = 100 # megaman stuff
    EFFECT_MM2 = 101 # megaman stuff
    CHANGE_MODE = 108 # megaman stuff
    SHADER = 101
    ADD_HIT = 105
    ACTION_CONDITON = 111
    BUFF_FIELD_ATTACH = 125
    BUTTERFLY_BULLET = 127

    @classmethod
    def _missing_(cls, value):
        return cls.UNKNOWN

# seen_id = set()
def build_db_data(meta, ref, seq, data):
    db_data = {}
    for k in meta.field_type.keys():
        if k in data:
            if isinstance(data[k], str):
                db_data[k] = data[k].strip()
            elif ACTION_PART.get_field(k) == DBTableMetadata.BLOB and not any(data[k]):
                db_data[k] = None
            else:
                db_data[k] = data[k]
        else:
            db_data[k] = None
    if (loop := data.get('_loopData')):
        db_data['_loopFlag'] = loop['flag']
        db_data['_loopNum'] = loop['loopNum']
        db_data['_loopFrame'] = loop['restartFrame']
        db_data['_loopSec'] = loop['restartSec']
    db_data['_Id'] = f'{ref}{seq:05}'
    # if db_data['_Id'] in seen_id:
    #     print(db_data['_Id'])
    # seen_id.add(db_data['_Id'])
    db_data['_ref'] = int(ref)
    db_data['_seq'] = seq
    return db_data

# def build_collision_data(meta, ref, seq, data):
#     if not data.get('_abHitAttrLabel'):
#         return None
#     return build_db_data(meta, ref, seq, data)

def build_bullet(meta, ref, seq, data):
    db_data = build_db_data(meta, ref, seq, data)
    if (ab_label := data['_arrangeBullet']['_abHitAttrLabel']):
        db_data['_abHitAttrLabel'] = ab_label
    if (ab_duration := data['_arrangeBullet']['_abDuration']):
        db_data['_abDuration'] = ab_duration
    if (ab_interval := data['_arrangeBullet']['_abHitInterval']):
        db_data['_abHitInterval'] = ab_interval
    cond_data = data['_conditionData']
    if cond_data['_conditionType']:
        db_data['_conditionType'] = cond_data['_conditionType']
        db_data['_conditionValue'] = cond_data['_conditionValue']
    return db_data

def build_formation_bullet(meta, ref, seq, data):
    bullet_num = 0
    bullet_data = None
    for c in data['_child']:
        try:
            if c['bulletData']['_hitAttrLabel']:
                bullet_num += 1
                bullet_data = c['bulletData']
        except:
            pass
    if bullet_data:
        db_data = build_db_data(meta, ref, seq, bullet_data)
        db_data['commandType'] = 100
        db_data['_bulletNum'] = bullet_num
        return db_data
    else:
        return None

def build_marker(meta, ref, seq, data):
    db_data = build_db_data(meta, ref, seq, data)
    if charge_lvl_sec := db_data.get('_chargeLvSec'):
        if '_nextLevelMarkerCount' in data and data['_nextLevelMarkerCount']:
            for lvl in data['_nextLevelMarkerData']:
                charge_lvl_sec.extend(lvl['_chargeLvSec'])
        if not any(charge_lvl_sec):
            db_data['_chargeLvSec'] = None
        else:
            db_data['_chargeLvSec'] = charge_lvl_sec
    return db_data

def build_animation(meta, ref, seq, data):
    db_data = build_db_data(meta, ref, seq, data)
    if '_name' in data and data['_name']:
        db_data['_animationName'] = data['_name']
    return db_data

ACTION_PART = DBTableMetadata(
    'ActionParts', pk='_Id', field_type={
        '_Id': DBTableMetadata.INT+DBTableMetadata.PK,
        '_ref': DBTableMetadata.INT,
        '_seq': DBTableMetadata.INT,
        '_seconds': DBTableMetadata.REAL,
        '_speed': DBTableMetadata.REAL,
        '_duration': DBTableMetadata.REAL,
        '_activateId': DBTableMetadata.INT,

        'commandType': DBTableMetadata.INT,

        # PARTS_MOTION
        '_motionState': DBTableMetadata.TEXT,
        '_motionFrame': DBTableMetadata.INT,
        '_blendDuration': DBTableMetadata.REAL,
        '_isBlend': DBTableMetadata.INT,
        '_isEndSyncMotion': DBTableMetadata.INT,
        '_isIgnoreFinishCondition': DBTableMetadata.INT,
        '_isIdleAfterCancel': DBTableMetadata.INT,

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
        '_chargeSec': DBTableMetadata.REAL,
        '_chargeLvSec': DBTableMetadata.BLOB,
        # '_chargeAfterSec': DBTableMetadata.REAL,
        # '_ignoredByPlayerAI': DBTableMetadata.INT,
        # '_invisibleForPlayerAI': DBTableMetadata.INT,
        # '_playerAIEscapeDir': DBTableMetadata.INT,
        # '_ignoredImpactWaitForPlayerColor': DBTableMetadata.INT,

        # HIT/BULLET
        '_bulletSpeed': DBTableMetadata.REAL,
        '_bulletDuration': DBTableMetadata.REAL,
        '_delayTime': DBTableMetadata.REAL,
        '_isHitDelete': DBTableMetadata.INT,
        '_hitLabel': DBTableMetadata.TEXT,
        '_hitAttrLabel': DBTableMetadata.TEXT,
        '_abHitAttrLabel': DBTableMetadata.TEXT,
        '_abHitInterval': DBTableMetadata.REAL,
        '_abDuration': DBTableMetadata.REAL,
        '_bulletNum': DBTableMetadata.INT,
        '_generateNum': DBTableMetadata.INT,
        '_generateDelay': DBTableMetadata.REAL,
        '_generateNumDependOnBuffCount': DBTableMetadata.INT,
        '_buffCountConditionId': DBTableMetadata.INT,
        '_setBulletDelayOneByOne': DBTableMetadata.INT,
        '_bulletDelayTime': DBTableMetadata.BLOB,
        '_lifetime': DBTableMetadata.REAL,
        '_conditionType': DBTableMetadata.INT,
        '_conditionValue': DBTableMetadata.BLOB,
        '_attenuationRate': DBTableMetadata.REAL,

        # COLLISION
        '_collision': DBTableMetadata.INT,
        '_collisionPosId': DBTableMetadata.INT,
        '_collisionParams_01': DBTableMetadata.REAL, # Length
        '_collisionParams_02': DBTableMetadata.REAL, # Width
        '_collisionParams_03': DBTableMetadata.REAL, # Height
        '_collisionParams_05': DBTableMetadata.REAL, # Angle
        '_collisionParams_06': DBTableMetadata.REAL,
        '_collisionHitInterval': DBTableMetadata.REAL,

        # SEND_SIGNAL
        '_signalType': DBTableMetadata.INT,
        '_decoId': DBTableMetadata.INT,
        '_actionId': DBTableMetadata.INT,
        '_keepActionEnd': DBTableMetadata.INT,
        '_keepActionId1': DBTableMetadata.INT,
        '_keepActionId2': DBTableMetadata.INT,

        # ACTIVE_CANCEL
        '_actionType': DBTableMetadata.INT,
        '_motionEnd': DBTableMetadata.INT,

        # BULLETS - contains marker data, unsure if it does anything
        # '_useMarker': DBTableMetadata.INT,
        # '_marker': DBTableMetadata.BOLB (?)

        # ANIMATION
        '_animationName': DBTableMetadata.TEXT, 
        '_isVisible': DBTableMetadata.INT, 
        '_isActionClear': DBTableMetadata.INT,

        # ACTION_CONDITON
        '_actionConditionId': DBTableMetadata.INT,

        # BUFF_FIELD_ATTACH
        '_isAttachToBuffField': DBTableMetadata.INT,
        '_isAttachToSelfBuffField': DBTableMetadata.INT,
        '_hitDelaySec': DBTableMetadata.REAL,

        # LOOP DATA
        '_loopFlag': DBTableMetadata.INT,
        '_loopNum': DBTableMetadata.INT,
        '_loopFrame': DBTableMetadata.INT,
        '_loopSec': DBTableMetadata.REAL,

        # TIMESTOP
        '_stopMotionPositionSec': DBTableMetadata.REAL,
        '_stopTimeSpanSec': DBTableMetadata.REAL,
        '_isRepeat': DBTableMetadata.INT,
        '_isOverridePlaySpeed': DBTableMetadata.INT,
        '_playSpeed': DBTableMetadata.REAL,

        # TIMECURVE
        '_isNormalizeCurve': DBTableMetadata.INT,
    }
)

PROCESSORS = {}
PROCESSORS[CommandType.PARTS_MOTION] = build_db_data
PROCESSORS[CommandType.MARKER] = build_marker
PROCESSORS[CommandType.BULLET] = build_bullet
PROCESSORS[CommandType.HIT] = build_db_data
PROCESSORS[CommandType.TIMESTOP] = build_db_data
PROCESSORS[CommandType.TIMECURVE] = build_db_data
# PROCESSORS[CommandType.COLLISION] = build_collision_data
PROCESSORS[CommandType.SEND_SIGNAL] = build_db_data
PROCESSORS[CommandType.ACTIVE_CANCEL] = build_db_data
PROCESSORS[CommandType.MULTI_BULLET] = build_bullet
PROCESSORS[CommandType.ANIMATION] = build_animation
PROCESSORS[CommandType.PARABOLA_BULLET] = build_bullet
PROCESSORS[CommandType.PIVOT_BULLET] = build_bullet
PROCESSORS[CommandType.FIRE_STOCK_BULLET] = build_bullet
PROCESSORS[CommandType.FORMATION_BULLET] = build_formation_bullet
PROCESSORS[CommandType.SETTING_HIT] = build_db_data
PROCESSORS[CommandType.ADD_HIT] = build_db_data
PROCESSORS[CommandType.ACTION_CONDITON] = build_db_data
PROCESSORS[CommandType.BUFF_FIELD_ATTACH] = build_db_data
PROCESSORS[CommandType.BUTTERFLY_BULLET] = build_bullet

def log_schema_keys(schema_map, data, command_type):
    schema_map[f'{data["commandType"]:03}-{command_type}'] = list(data.keys())
    for subdata in data.values():
        try:
            if (command_type := subdata.get('commandType')):
                log_schema_keys(schema_map, subdata, CommandType(command_type))
        except:
            pass

def load_actions(db, path):
    schema_map = {}
    file_filter = re.compile(r'PlayerAction_([0-9]+)\.json')
    db.drop_table(ACTION_PART.name)
    db.create_table(ACTION_PART)
    sorted_data = []
    for root, _, files in os.walk(path):
        for file_name in tqdm(files, desc='action'):
            if file_name == 'ActionPartsList.json':
                table = 'ActionPartsList'
                db.drop_table(table)
                with open(os.path.join(root, file_name)) as f:
                    raw = json.load(f)
                    for r in raw:
                        resource_fn = os.path.basename(r['_resourcePath'])
                        try:
                            r['_host'], r['_Id'] = resource_fn.split('_')
                            r['_Id'] = int(r['_Id'])
                        except:
                            r['_host'], r['_Id'] = None, 0
                    row = next(iter(raw))
                    pk = '_resourcePath'
                    meta = DBTableMetadata(table, pk=pk)
                    meta.init_from_row(row)
                    db.create_table(meta)
                    db.insert_many(table, raw)
            else:
                res = file_filter.match(file_name)
                if res:
                    ref = res.group(1)
                    with open(os.path.join(root, file_name)) as f:
                        raw = json.load(f)
                        # action = [gameObject['_data'] for gameObject in raw if '_data' in gameObject.keys()]
                        action = []
                        for seq, gameObject in enumerate(raw):
                            actdata = gameObject.get('_data')
                            if not actdata:
                                continue
                            action.append((seq, actdata))
                            # if additional := actdata.get('_additionalCollision'):
                            #     action.extend(((seq+100*(1+i), act) for i, act in enumerate(additional)))
                        for seq, data in action:
                            command_type = CommandType(data['commandType'])
                            log_schema_keys(schema_map, data, command_type)
                            if command_type in PROCESSORS.keys():
                                builder = PROCESSORS[command_type]
                                db_data = builder(ACTION_PART, ref, seq, data)
                                if db_data is not None:
                                    sorted_data.append(db_data)
    db.insert_many(ACTION_PART.name, sorted_data)
    return schema_map

if __name__ == '__main__':
    from loader.Database import DBManager
    db = DBManager()
    schema_map = load_actions(db, './_ex_sim/jp/actions')
