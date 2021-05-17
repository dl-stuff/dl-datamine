import os
import re
from tqdm import tqdm

from loader.Database import DBManager, DBTableMetadata

FIELD_TYPE = {
    "_Id": DBTableMetadata.INT + DBTableMetadata.PK,
    "_CharaId": DBTableMetadata.INT,
    "_SkillId": DBTableMetadata.INT,
    "_SkillLv": DBTableMetadata.INT,
    "_Text": DBTableMetadata.TEXT,
    "_TextJP": DBTableMetadata.TEXT,
    "_TextCN": DBTableMetadata.TEXT,
}
SKILLDETAIL_FN_PATTERN = re.compile(r"SkillDetail(\d+)Lv(\d+)")
SKILLDETAIL_PATTERN = re.compile(
    r"<size=0>\[(\d+)\].*<\/size>\n<size=0>\[(\d+)\]\[Lv.(\d+)\].*<\/size>\n((?:.+(?:\n|$))+)",
    flags=re.MULTILINE,
)


def build_skilldetail_row(root, fn):
    with open(os.path.join(root, fn), "r") as fp:
        skilldetail = fp.read()
        # :awauuangery:
        res = SKILLDETAIL_FN_PATTERN.match(fn)
        if res:
            fn_skill_lv = int(res.group(2))
        for res in SKILLDETAIL_PATTERN.finditer(skilldetail):
            chara_id, skill_id, _, text = res.groups()
            yield text, {
                "_Id": int(f"{skill_id}{fn_skill_lv}"),
                "_CharaId": int(chara_id),
                "_SkillId": int(skill_id),
                "_SkillLv": int(fn_skill_lv),
                "_Text": None,
                "_TextJP": None,
                "_TextCN": None,
            }


def load_ui_skill_detail(db, path):
    skilldetails = {}
    for region in ("en", "jp", "cn"):
        for root, _, files in os.walk(os.path.join(path, region, "skilldetail")):
            for fn in tqdm(files, desc="skill detail"):
                for sd_info in build_skilldetail_row(root, fn):
                    sd_text, sd_row = sd_info
                    if sd_row["_Id"] not in skilldetails:
                        skilldetails[sd_row["_Id"]] = sd_row
                    if region == "en":
                        skilldetails[sd_row["_Id"]]["_Text"] = sd_text
                    else:
                        skilldetails[sd_row["_Id"]][f"_Text{region.upper()}"] = sd_text
    tablename = "SkillDetail"
    if not db.check_table("SkillDetail"):
        metadata = DBTableMetadata(tablename, pk="_Id", field_type=FIELD_TYPE)
        db.create_table(metadata)
    db.insert_many(tablename, skilldetails.values(), mode=DBManager.REPLACE)


if __name__ == "__main__":
    db = DBManager()
    load_ui_skill_detail(db, "./_ex_sim")
