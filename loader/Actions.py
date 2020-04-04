import json
import os
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
    FIRE_STOCK_BULLET = 59
    CONDITION_TEXT = 63 # unsure where text is sourced, not in TextLabel
    SETTING_HIT = 66

    @classmethod
    def _missing_(cls, value):
        return cls.UNKNOWN


def build_db_data(meta, ref, seq, data):
    db_data = {}
    for k in meta.field_type.keys():
        if k in data:
            if isinstance(data[k], str):
                db_data[k] = data[k].strip()
            else:
                db_data[k] = data[k]
        else:
            db_data[k] = None
    db_data['_Id'] = f'{ref}{seq:03}'
    db_data['_ref'] = int(ref)
    db_data['_seq'] = seq
    return db_data


def build_bullet(meta, ref, seq, data):
    db_data = build_db_data(meta, ref, seq, data)
    ab_label = data['_arrangeBullet']['_abHitAttrLabel']
    if ab_label:
        db_data['_abHitAttrLabel'] = ab_label
    return db_data


def build_marker(meta, ref, seq, data):
    db_data = build_db_data(meta, ref, seq, data)
    charge_lvl_sec = db_data['_chargeLvSec']
    if not any(charge_lvl_sec):
        db_data['_chargeLvSec'] = None
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
        '_delayTime': DBTableMetadata.REAL,
        '_collisionHitInterval': DBTableMetadata.REAL,
        '_isHitDelete': DBTableMetadata.INT,
        '_hitLabel': DBTableMetadata.TEXT,
        '_hitAttrLabel': DBTableMetadata.TEXT,
        '_abHitAttrLabel': DBTableMetadata.TEXT,
        '_generateNum': DBTableMetadata.INT,
        '_generateDelay': DBTableMetadata.REAL,

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
        '_isVisible': DBTableMetadata.TEXT, 
        '_isActionClear': DBTableMetadata.TEXT,
    }
)

PROCESSORS = {}
PROCESSORS[CommandType.PARTS_MOTION] = build_db_data
PROCESSORS[CommandType.MARKER] = build_marker
PROCESSORS[CommandType.BULLET] = build_bullet
PROCESSORS[CommandType.HIT] = build_db_data
PROCESSORS[CommandType.SEND_SIGNAL] = build_db_data
PROCESSORS[CommandType.ACTIVE_CANCEL] = build_db_data
PROCESSORS[CommandType.MULTI_BULLET] = build_bullet
PROCESSORS[CommandType.ANIMATION] = build_animation
PROCESSORS[CommandType.PARABOLA_BULLET] = build_bullet
PROCESSORS[CommandType.PIVOT_BULLET] = build_bullet
PROCESSORS[CommandType.FIRE_STOCK_BULLET] = build_bullet
PROCESSORS[CommandType.SETTING_HIT] = build_db_data

def load_actions(db, path):
    file_filter = re.compile(r'PlayerAction_([0-9]+)\.json')
    db.drop_table(ACTION_PART.name)
    db.create_table(ACTION_PART)
    sorted_data = []
    for root, _, files in os.walk(path):
        for file_name in files:
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
                    pk = '_Id'
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
                        action = [gameObject['_data'] for gameObject in raw if '_data' in gameObject.keys()]
                        for seq, data in enumerate(action):
                            command_type = CommandType(data['commandType'])
                            if command_type in PROCESSORS.keys():
                                builder = PROCESSORS[command_type]
                                db_data = builder(ACTION_PART, ref, seq, data)
                                sorted_data.append(db_data)
    db.insert_many(ACTION_PART.name, sorted_data)

if __name__ == '__main__':
    from loader.Database import DBManager
    db = DBManager()
    load_actions(db, './extract/actions')