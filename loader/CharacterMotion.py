import json
import os
import re
from loader.Database import DBManager, DBTableMetadata

CHARACTER_MOTION = DBTableMetadata(
    'CharacterMotion', pk='name', field_type={
        'name': DBTableMetadata.TEXT+DBTableMetadata.PK,
        'ref': DBTableMetadata.INT,
        'startTime': DBTableMetadata.REAL,
        'stopTime': DBTableMetadata.REAL,
        'duration': DBTableMetadata.REAL,
    }
)

ref_pattern = re.compile(r'[A-Z]{3}_[A-Z]{3}_\d{2}_\d{2}_(\d+)')
def build_character_motion(data):
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

def load_character_motion(db, path):
    character_motion = []
    db.create_table(CHARACTER_MOTION)
    for root, _, files in os.walk(path):
        for file_name in files:
            file_path = os.path.join(root, file_name)
            try:
                with open(file_path) as f:
                    data = json.load(f)
                    character_motion.append(build_character_motion(data))
            except (KeyError, TypeError):
                pass
    db.insert_many(CHARACTER_MOTION.name, character_motion)

if __name__ == '__main__':
    from loader.Database import DBManager
    db = DBManager()
    load_character_motion(db, './extract/characters_motion')