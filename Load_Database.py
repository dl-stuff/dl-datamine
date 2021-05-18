import os
import argparse
from time import monotonic
import json

from loader.AssetExtractor import Extractor
from loader.Database import DBManager

from loader.Master import load_master, load_json
from loader.Actions import load_actions
from loader.Motion import load_motions
from loader.Aiscript import load_aiscript
from loader.UISkillDetail import load_ui_skill_detail

JP = "jp"
EN = "en"
CN = "cn"

MASTER = "master"
ACTIONS = "actions"

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
    r"^characters/motion": "motion",
    r"characters/motion/animationclips$": "motion",
    r"^dragon/motion": "motion",
    r"^assets/_gluonresources/meshes/dragon": "motion",
    r"^ui/skilldetail/skilldetail": "skilldetail",
}
LABEL_PATTERNS = {
    JP: LABEL_PATTERNS_JP,
    EN: LABEL_PATTERNS_EN,
    CN: LABEL_PATTERNS_CN,
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
    start = monotonic()

    dl_dir = "./_dl_sim"
    in_dir = "./_ex_sim"
    if args.do_prep:
        ex = Extractor(dl_dir=dl_dir, ex_dir=in_dir, ex_img_dir=None, overwrite=True)
        if not os.path.isdir(in_dir):
            ex.download_and_extract_by_pattern(LABEL_PATTERNS)
        else:
            ex.download_and_extract_by_pattern_diff(LABEL_PATTERNS)
        load_aiscript(os.path.join(in_dir, "jp", "aiscript"))
        # extract_story_function_json(ex)
    db = DBManager(args.o)
    load_master(db, os.path.join(in_dir, EN, MASTER))
    load_json(db, os.path.join(in_dir, JP, MASTER, TEXT_LABEL), "TextLabelJP")
    load_json(db, os.path.join(in_dir, CN, MASTER, TEXT_LABEL), "TextLabelCN")
    load_motions(db, os.path.join(in_dir, JP))
    load_ui_skill_detail(db, in_dir)

    load_actions(db, os.path.join(in_dir, JP, ACTIONS))
    print(f"total: {monotonic()-start:.4f}s")
