import os
import argparse
from time import monotonic
from tqdm import tqdm
import json

from loader.AssetExtractor import Extractor
from loader.Database import DBManager

from loader.Master import load_master, load_json
from loader.Actions import load_actions
from loader.Motion import load_character_motion, load_dragon_motion
from loader.Aiscript import load_aiscript
from loader.UISkillDetail import load_ui_skill_detail

JP = "jp"
EN = "en"
CN = "cn"

MASTER = "master"
ACTIONS = "actions"
CHARACTERS_MOTION = "characters_motion"
DRAGON_MOTION = "dragon_motion"

TEXT_LABEL = "TextLabel.json"
LABEL_PATTERNS_EN = {
    r"^master$": "master",
    r"^ui/skilldetail/skilldetail": "skilldetail",
}
LABEL_PATTERNS_CN = {
    r"^master$": "master",
    r"^ui/skilldetail/skilldetail": "skilldetail",
}
LABEL_PATTERNS_JP = {
    r"^master$": "master",
    r"^actions$": "actions",
    r"^aiscript$": "aiscript",
    r"^characters/motion": "characters_motion",
    r"characters/motion/animationclips$": "characters_motion",
    r"^dragon/motion": "dragon_motion",
    r"^assets/_gluonresources/meshes/dragon": "dragon_motion",
    r"^ui/skilldetail/skilldetail": "skilldetail",
}
LABEL_PATTERNS = {
    JP: LABEL_PATTERNS_JP,
    EN: LABEL_PATTERNS_EN,
    CN: LABEL_PATTERNS_CN,
}
IMAGE_PATTERNS = {
    r"^images/icon": "icon",
    r"^images/outgame": "outgame",
}


def extract_story_function_json(ex):
    ex.download_and_extract_by_pattern({"jp": {r"^story/function": None}})
    ex_path = os.path.join(ex.ex_dir, "jp", "story", "function.json")
    with open(ex_path) as func:
        data = json.load(func)["functions"][0]["variables"]
    with open("./out/_storynames.json", "w") as out:
        json.dump(
            {k: v for k, v in zip(data["entriesKey"], data["entriesValue"])},
            out,
            indent=4,
            ensure_ascii=False,
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import data to database.")
    parser.add_argument("--do_prep", help="Download and extract db related assets", action="store_true")
    parser.add_argument("-m_hash", help="Use", action="store_true")
    parser.add_argument("-o", type=str, help="output file", default="dl.sqlite")
    args = parser.parse_args()
    # if args.do_images:
    #     ex = Extractor(MANIFEST_JP, MANIFEST_EN, ex_dir='images', stdout_log=True)
    #     ex.download_and_extract_by_pattern(IMAGE_PATTERNS, region='jp')
    start = monotonic()

    dl_dir = "./_dl_sim"
    in_dir = "_ex_sim"
    if args.do_prep:
        ex = Extractor(dl_dir=dl_dir, ex_dir=in_dir, stdout_log=False, overwrite=True)
        if not os.path.isdir(in_dir):
            ex.download_and_extract_by_pattern(LABEL_PATTERNS)
        else:
            ex.download_and_extract_by_pattern_diff(LABEL_PATTERNS)
        # extract_story_function_json(ex)
    db = DBManager(args.o)
    load_master(db, os.path.join(in_dir, EN, MASTER))
    load_json(db, os.path.join(in_dir, JP, MASTER, TEXT_LABEL), "TextLabelJP")
    load_json(db, os.path.join(in_dir, CN, MASTER, TEXT_LABEL), "TextLabelCN")
    schema_map = load_actions(db, os.path.join(in_dir, JP, ACTIONS))
    os.makedirs("out", exist_ok=True)
    with open("./out/_action_schema.json", "w") as f:
        json.dump(schema_map, f, indent=4, sort_keys=True)
    load_character_motion(db, os.path.join(in_dir, JP, CHARACTERS_MOTION))
    load_dragon_motion(db, os.path.join(in_dir, JP, DRAGON_MOTION))
    load_ui_skill_detail(db, in_dir)
    load_aiscript(os.path.join(ex.ex_dir, "jp", "aiscript"))
    print(f"total: {monotonic()-start:.4f}s")
