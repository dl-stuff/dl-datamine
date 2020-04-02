import json
import os
import re
from loader.Database import DBManager, DBTableMetadata

MOTION_FIELDS = {
        'name': DBTableMetadata.TEXT+DBTableMetadata.PK,
        'ref': DBTableMetadata.INT,
        'startTime': DBTableMetadata.REAL,
        'stopTime': DBTableMetadata.REAL,
        'duration': DBTableMetadata.REAL,
    }
CHARACTER_MOTION = DBTableMetadata('CharacterMotion', pk='name', field_type=MOTION_FIELDS)
CHARACTER_REF = re.compile(r'[A-Z]{3}_[A-Z]{3}_\d{2}_\d{2}_(\d+)')

DRAGON_MOTION = DBTableMetadata('DragonMotion', pk='name', field_type=MOTION_FIELDS)
DRAGON_REF = re.compile(r'D(\d{8})_\d{3}_\d{2}')

def build_motion(data, ref_pattern):
    db_data = {}
    db_data['name'] = data['name']
    res = ref_pattern.match(data['name'])
    if res:
        db_data['ref'] = res.group(1)
    else:
        db_data['ref'] = None
    db_data['startTime'] = data['m_MuscleClip']['m_StartTime']
    db_data['stopTime'] = data['m_MuscleClip']['m_StopTime']
    db_data['duration'] = data['m_MuscleClip']['m_StopTime'] - data['m_MuscleClip']['m_StartTime']
    return db_data

def load_motion(db, path, meta, ref_pattern):
    motions = []
    db.drop_table(meta.name)
    db.create_table(meta)
    for root, _, files in os.walk(path):
        for file_name in files:
            file_path = os.path.join(root, file_name)
            try:
                with open(file_path) as f:
                    data = json.load(f)
                    motions.append(build_motion(data, ref_pattern))
            except (KeyError, TypeError):
                pass
    db.insert_many(meta.name, motions)

def load_character_motion(db, path):
    load_motion(db, path, CHARACTER_MOTION, CHARACTER_REF)

def load_dragon_motion(db, path):
    load_motion(db, path, DRAGON_MOTION, DRAGON_REF)

if __name__ == '__main__':
    from loader.Database import DBManager
    db = DBManager()
    # load_character_motion(db, './extract/characters_motion')
    load_character_motion(db, './extract/dragon_motion')