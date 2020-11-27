import json
import os
import re
from tqdm import tqdm
from loader.Database import DBManager, DBTableMetadata

MOTION_FIELDS = {
        'name': DBTableMetadata.TEXT+DBTableMetadata.PK,
        'state': DBTableMetadata.TEXT,
        'ref': DBTableMetadata.INT,
        'startTime': DBTableMetadata.REAL,
        'stopTime': DBTableMetadata.REAL,
        'duration': DBTableMetadata.REAL,
    }
CHARACTER_MOTION = DBTableMetadata('CharacterMotion', pk='name', field_type=MOTION_FIELDS)
CHARACTER_REF = re.compile(r'[A-Za-z]{3}_(.*)_(\d{8})', flags=re.IGNORECASE)

DRAGON_MOTION = DBTableMetadata('DragonMotion', pk='name', field_type=MOTION_FIELDS)
DRAGON_REF = re.compile(r'd(\d{8})_(\d{3})_\d{2}', flags=re.IGNORECASE)

def chara_state_ref(res):
    state = res.group(1) if len(res.group(1)) > 1 else None
    ref = res.group(2)
    if '_' not in state:
        return state, ref
    s1, sn = state.split('_', 1)
    if s1 == 'SKL':
        state = f'skill_unique_{sn}'
    elif s1 == 'CMB':
        state = f'combo_{sn.lower().replace("0", "")}'
    return state, ref

# 000 idle
# 002 walk
# 003 dash
# 004 stop dash
# 020 roll
# 030 transform
# 04x combo
# 060 skill

DRAGON_STATE = {
    '000': 'idle',
    '002': 'walk',
    '003': 'dash',
    '004': 'stop',
    '020': 'roll',
    '030': 'transform',
    '060': 'skill_01'
}

def dragon_state_ref(res):
    state = res.group(2)
    ref = res.group(1)
    if state in DRAGON_STATE:
        state = DRAGON_STATE[state]
    elif state[1] == '4':
        state = f'combo_{int(state[2])+1}'
    return state, ref

def build_motion(data, ref_pattern, state_ref):
    db_data = {}
    db_data['name'] = data['name']
    res = ref_pattern.match(data['name'])
    if res:
        db_data['state'], db_data['ref'] = state_ref(res)
    else:
        db_data['state'], db_data['ref'] = None, None
    db_data['startTime'] = data['m_MuscleClip']['m_StartTime']
    db_data['stopTime'] = data['m_MuscleClip']['m_StopTime']
    db_data['duration'] = data['m_MuscleClip']['m_StopTime'] - data['m_MuscleClip']['m_StartTime']
    return db_data

def load_motion(db, path, meta, ref_pattern, state_ref):
    motions = []
    db.drop_table(meta.name)
    db.create_table(meta)
    for root, _, files in os.walk(path):
        for file_name in tqdm(files, desc='motion'):
            file_path = os.path.join(root, file_name)
            try:
                with open(file_path) as f:
                    data = json.load(f)
                    motions.append(build_motion(data, ref_pattern, state_ref))
            except (KeyError, TypeError, json.decoder.JSONDecodeError):
                pass
    db.insert_many(meta.name, motions)

def load_character_motion(db, path):
    load_motion(db, path, CHARACTER_MOTION, CHARACTER_REF, chara_state_ref)

def load_dragon_motion(db, path):
    load_motion(db, path, DRAGON_MOTION, DRAGON_REF, dragon_state_ref)

if __name__ == '__main__':
    from loader.Database import DBManager
    db = DBManager()
    load_character_motion(db, './_ex_sim/jp/characters_motion')
    load_dragon_motion(db, './_ex_sim/jp/dragon_motion')