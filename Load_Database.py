import os
import argparse

from loader.Database import DBManager

from loader.Master import load_master
from loader.Actions import load_actions
from loader.CharacterMotion import load_character_motion

MASTER = 'master'
ACTIONS = 'actions'
CHARACTERS_MOTION = 'characters_motion'

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Import data to database.')
    parser.add_argument('-i', type=str, help='input dir', default='./extract')
    parser.add_argument('-o', type=str, help='output file', default='./dl.sqlite')
    args = parser.parse_args()

    in_dir = args.i
    out_file = args.o

    db = DBManager(out_file)
    load_master(db, os.path.join(in_dir, MASTER))
    load_actions(db, os.path.join(in_dir, ACTIONS))
    load_character_motion(db, os.path.join(in_dir, CHARACTERS_MOTION))