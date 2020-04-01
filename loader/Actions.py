import json
import os
from loader.Database import DBManager, DBTableMetadata
from enum import Enum
import re

class CommandType(Enum):
    UNKNOWN = -1
    PARTS_MOTION_DATA = 2
    BULLET_DATA = 9
    HIT_DATA = 10
    EFFECT_DATA = 11
    SOUND_DATA = 12
    CAMERA_MOTION_DATA = 13
    SEND_SIGNAL_DATA = 14
    ACTIVE_CANCEL_DATA = 15
    MULTI_BULLET_DATA = 24
    PARABOLA_BULLET_DATA = 41
    PIVOT_BULLET_DATA = 53
    FIRE_STOCK_BULLET_DATA = 59
    SETTING_HIT_DATA = 66

    @classmethod
    def _missing_(cls, value):
        return cls.UNKNOWN


def build_db_data(meta, ref, seq, data, override={}):
    db_data = {}
    for k in meta.field_type.keys():
        key = k if k not in override else override[k]
        if key in data:
            db_data[k] = data[key]
        else:
            db_data[k] = None
    db_data['_Id'] = f'{ref}{seq:03}'
    db_data['_ref'] = int(ref)
    db_data['_seq'] = seq
    return db_data


def build_hit_attr_label(meta, ref, seq, data):
    return build_db_data(meta, ref, seq, data, {'_hitLabel': '_hitAttrLabel'})


def build_bullet(meta, ref, seq, data):
    db_data = build_db_data(meta, ref, seq, data, {'_hitLabel': '_hitAttrLabel'})
    ab_label = data['_arrangeBullet']['_abHitAttrLabel']
    if ab_label:
        db_data['_hitLabel'] = ab_label
    return db_data

ACTION_PART = DBTableMetadata(
    'ActionParts', pk='_Id', field_type={
        '_Id': DBTableMetadata.INT+DBTableMetadata.PK,
        '_ref': DBTableMetadata.INT,
        '_seq': DBTableMetadata.INT,
        '_seconds': DBTableMetadata.REAL,
        '_speed': DBTableMetadata.REAL,
        '_duration': DBTableMetadata.REAL,

        'commandType': DBTableMetadata.INT,
        # PARTS_MOTION_DATA
        '_activateId': DBTableMetadata.INT,
        '_motionFrame': DBTableMetadata.INT,
        '_blendDuration': DBTableMetadata.REAL,
        '_isBlend': DBTableMetadata.INT,
        '_isEndSyncMotion': DBTableMetadata.INT,
        '_isIgnoreFinishCondition': DBTableMetadata.INT,
        '_isIdleAfterCancel': DBTableMetadata.INT,

        # HIT
        '_delayTime': DBTableMetadata.REAL,
        '_collisionHitInterval': DBTableMetadata.REAL,
        '_isHitDelete': DBTableMetadata.INT,
        '_hitLabel': DBTableMetadata.TEXT,
        '_generateNum': DBTableMetadata.INT,
        '_generateDelay': DBTableMetadata.REAL,

        # SEND_SIGNAL
        '_actionId': DBTableMetadata.INT,
        '_decoId': DBTableMetadata.INT,

        # ACTIVE_CANCEL
        '_actionType': DBTableMetadata.INT,
        '_motionEnd': DBTableMetadata.INT
    }
)

PROCESSORS = {}
PROCESSORS[CommandType.PARTS_MOTION_DATA] = build_db_data
PROCESSORS[CommandType.BULLET_DATA] = build_bullet
PROCESSORS[CommandType.HIT_DATA] = build_db_data
# PROCESSORS[CommandType.EFFECT_DATA] = DBTableMetadata('EffectData')
# PROCESSORS[CommandType.SOUND_DATA] = DBTableMetadata('SoundData')
# PROCESSORS[CommandType.CAMERA_MOTION_DATA] = DBTableMetadata('CameraMotionData')
PROCESSORS[CommandType.SEND_SIGNAL_DATA] = build_db_data
PROCESSORS[CommandType.ACTIVE_CANCEL_DATA] = build_db_data
PROCESSORS[CommandType.MULTI_BULLET_DATA] = build_bullet
PROCESSORS[CommandType.PARABOLA_BULLET_DATA] = build_bullet
PROCESSORS[CommandType.PIVOT_BULLET_DATA] = build_bullet
PROCESSORS[CommandType.FIRE_STOCK_BULLET_DATA] = build_bullet
PROCESSORS[CommandType.SETTING_HIT_DATA] = build_hit_attr_label

def load_actions(db, path):
    file_filter = re.compile(r'PlayerAction_([0-9]+)\.json')
    db.create_table(ACTION_PART)
    sorted_data = []
    for root, _, files in os.walk(path):
        for file_name in files:
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