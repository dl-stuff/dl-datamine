from collections import defaultdict
import json
import os
from glob import glob
from pprint import pprint
from tqdm import tqdm
from loader.Database import DBManager, DBTableMetadata

MOTION_FIELDS = {
    DBTableMetadata.DBID: DBTableMetadata.INT + DBTableMetadata.PK + DBTableMetadata.AUTO,
    "pathID": DBTableMetadata.INT,
    "name": DBTableMetadata.TEXT,
    "cat": DBTableMetadata.TEXT,
    "ref": DBTableMetadata.TEXT,
    "state": DBTableMetadata.TEXT,
    # "startTime": DBTableMetadata.REAL,
    # "stopTime": DBTableMetadata.REAL,
    "duration": DBTableMetadata.REAL,
}
MOTION_DATA = DBTableMetadata("MotionData", pk="name", field_type=MOTION_FIELDS)


def controller_cat_ref(name):
    if name[0] == "d" and name[1].isdigit():
        return "DRG", name[1:].replace("_", "")
    parts = name.split("_")
    cat = parts[0].upper()
    if len(parts) == 2:
        return cat, parts[1]
    return cat, None


def clip_cat_ref(name):
    if name[0] == "D" and name[1].isdigit():
        return "DRG", name.split("_")[0][1:]
    parts = name.split("_")
    cat = parts[0].upper()
    if len(parts[-1]) == 8:
        return cat, parts[1]
    return cat, None


def load_base_controller(filename, all_controllers):
    with open(filename, "r") as fn:
        try:
            data = json.load(fn)
        except json.decoder.JSONDecodeError:
            return
        path_id = data["pathID"]
        cat, ref = controller_cat_ref(data["m_Name"])
        tos = {int(k): v for k, v in data["m_TOS"]}
        clip_idx_to_pathid = [int(clip["m_PathID"]) for idx, clip in enumerate(data["m_AnimationClips"])]
        clip_pathid_to_state = defaultdict(set)

        controller = data["m_Controller"]
        # ignoring attachment layers
        for layer in controller["m_LayerArray"]:
            smid = layer["data"]["m_StateMachineIndex"]
            for sm_const in controller["m_StateMachineArray"][smid]["data"]["m_StateConstantArray"]:
                sm_name = tos[sm_const["data"]["m_NameID"]]
                for blend_tree in sm_const["data"]["m_BlendTreeConstantArray"]:
                    for node in blend_tree["data"]["m_NodeArray"]:
                        clip_pathid = clip_idx_to_pathid[node["data"]["m_ClipID"]]
                        clip_pathid_to_state[clip_pathid].add((sm_name, cat, ref))
                        # clip_pathid_to_state[clip_pathid].add((sm_name, None))

        all_controllers[path_id] = dict(clip_pathid_to_state)


def load_override_controller(filename, all_controllers):
    with open(filename, "r") as fn:
        try:
            data = json.load(fn)
        except json.decoder.JSONDecodeError:
            return
        path_id = data["pathID"]
        cat, ref = controller_cat_ref(data["m_Name"])
        base_controller = all_controllers[data["m_Controller"]["m_PathID"]]
        original_to_override = {}
        for clip in data["m_Clips"]:
            original_to_override[clip["m_OriginalClip"]["m_PathID"]] = clip["m_OverrideClip"]["m_PathID"]
        clip_pathid_to_state = defaultdict(set)
        for o_pathid, ncr_set in base_controller.items():
            for ncr in ncr_set:
                clip_pathid_to_state[original_to_override.get(o_pathid, o_pathid)].add((ncr[0], cat, ref))

        all_controllers[path_id] = clip_pathid_to_state


def build_motion(data, clip_pathid_to_state):
    states = clip_pathid_to_state.get(data["pathID"])
    if not states:
        states = ((None, *clip_cat_ref(data["m_Name"])),)
    for state, cat, ref in states:
        # db_data["startTime"] = data["m_MuscleClip"]["m_StartTime"]
        # db_data["stopTime"] = data["m_MuscleClip"]["m_StopTime"]
        db_data = {}
        db_data["pathID"] = data["pathID"]
        db_data["name"] = data["m_Name"]
        db_data["cat"] = cat
        db_data["ref"] = ref
        db_data["state"] = state
        db_data["duration"] = data["m_MuscleClip"]["m_StopTime"] - data["m_MuscleClip"]["m_StartTime"]
        yield db_data


def load_motions(db, ex_dir):
    all_controllers = {}
    for anim_ctrl in glob(f"{ex_dir}/motion/AnimatorController.*.json"):
        load_base_controller(anim_ctrl, all_controllers)
    for anim_ctrl_override in glob(f"{ex_dir}/motion/AnimatorOverrideController.*.json"):
        load_override_controller(anim_ctrl_override, all_controllers)
    clip_pathid_to_state = defaultdict(set)
    for ctrl_pathid_to_state in all_controllers.values():
        for key, value in ctrl_pathid_to_state.items():
            clip_pathid_to_state[key].update(value)

    motions = []
    db.drop_table(MOTION_DATA.name)
    db.create_table(MOTION_DATA)
    for anim_clip in tqdm(glob(f"{ex_dir}/motion/AnimationClip.*.json"), desc="motion"):
        try:
            with open(anim_clip) as f:
                data = json.load(f)
                for motion in build_motion(data, clip_pathid_to_state):
                    motions.append(motion)
        except json.decoder.JSONDecodeError:
            pass
    db.insert_many(MOTION_DATA.name, motions)


if __name__ == "__main__":
    db = DBManager()
    ex_dir = "_ex_sim/jp"
    load_motions(db, "_ex_sim/jp")
    # d21015701
    # all_controllers = {}
    # for anim_ctrl in glob(f"{ex_dir}/motion/AnimatorController.d210157_01.json"):
    #     load_base_controller(anim_ctrl, all_controllers)
    # pprint(all_controllers)
