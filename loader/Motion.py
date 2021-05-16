import json
import os
from glob import glob
from tqdm import tqdm
from loader.Database import DBManager, DBTableMetadata

MOTION_FIELDS = {
    "pathID": DBTableMetadata.INT + DBTableMetadata.PK,
    "name": DBTableMetadata.TEXT,
    "ref": DBTableMetadata.TEXT,
    "state": DBTableMetadata.TEXT,
    # "startTime": DBTableMetadata.REAL,
    # "stopTime": DBTableMetadata.REAL,
    "duration": DBTableMetadata.REAL,
}
MOTION_DATA = DBTableMetadata("MotionData", pk="name", field_type=MOTION_FIELDS)


def get_ref(name):
    if name[0] == "D":
        return name.split("_")[0].lower()
    last_part = name.split("_")[-1]
    if len(last_part) == 8:
        return last_part
    return None


def load_base_controller(filename, all_controllers):
    with open(filename, "r") as fn:
        try:
            data = json.load(fn)
        except json.decoder.JSONDecodeError:
            return
        path_id = data["pathID"]
        tos = {int(k): v for k, v in data["m_TOS"].items()}
        clip_idx_to_pathid = [int(clip["m_PathID"]) for idx, clip in enumerate(data["m_AnimationClips"])]
        clip_pathid_to_state = {}

        controller = data["m_Controller"]
        # ignoring attachment layers
        for layer in controller["m_LayerArray"]:
            smid = layer["data"]["m_StateMachineIndex"]
            for sm_const in controller["m_StateMachineArray"][smid]["data"]["m_StateConstantArray"]:
                sm_name = tos[sm_const["data"]["m_NameID"]]
                for blend_tree in sm_const["data"]["m_BlendTreeConstantArray"]:
                    for node in blend_tree["data"]["m_NodeArray"]:
                        clip_pathid = clip_idx_to_pathid[node["data"]["m_ClipID"]]
                        if not clip_pathid in clip_pathid_to_state:
                            clip_pathid_to_state[clip_pathid] = sm_name

        all_controllers[path_id] = clip_pathid_to_state


def load_override_controller(filename, all_controllers):
    with open(filename, "r") as fn:
        try:
            data = json.load(fn)
        except json.decoder.JSONDecodeError:
            return
        path_id = data["pathID"]
        controller_path_id = data["m_Controller"]["m_PathID"]
        clip_pathid_to_state = {}
        for clip in data["m_Clips"]:
            original_pathid = clip["m_OriginalClip"]["m_PathID"]
            override_pathid = clip["m_OverrideClip"]["m_PathID"]
            if original_pathid != override_pathid:
                try:
                    clip_pathid_to_state[override_pathid] = all_controllers[controller_path_id][original_pathid]
                except Exception as e:
                    print(filename)
                    raise e

        all_controllers[path_id] = clip_pathid_to_state


def build_motion(data, clip_pathid_to_state):
    db_data = {}
    db_data["pathID"] = data["pathID"]
    db_data["name"] = data["name"]
    db_data["ref"] = data["ref"]
    db_data["state"] = clip_pathid_to_state.get(data["pathID"], None)
    # db_data["startTime"] = data["m_MuscleClip"]["m_StartTime"]
    # db_data["stopTime"] = data["m_MuscleClip"]["m_StopTime"]
    db_data["duration"] = data["m_MuscleClip"]["m_StopTime"] - data["m_MuscleClip"]["m_StartTime"]
    return db_data


def load_motions(db, ex_dir):
    all_controllers = {}
    for anim_ctrl in glob(f"{ex_dir}/motion/AnimatorController.*.json"):
        load_base_controller(anim_ctrl, all_controllers)
    for anim_ctrl_override in glob(f"{ex_dir}/motion/AnimatorOverrideController.*.json"):
        load_override_controller(anim_ctrl_override, all_controllers)
    clip_pathid_to_state = {}
    for value in all_controllers.values():
        clip_pathid_to_state.update(value)

    motions = []
    db.drop_table(MOTION_DATA.name)
    db.create_table(MOTION_DATA)
    for anim_clip in tqdm(glob(f"{ex_dir}/motion/AnimationClip.*.json"), desc="motion"):
        try:
            with open(anim_clip) as f:
                data = json.load(f)
                motions.append(build_motion(data, clip_pathid_to_state))
        except json.decoder.JSONDecodeError:
            pass
    db.insert_many(MOTION_DATA.name, motions)


if __name__ == "__main__":
    db = DBManager()
    all_controllers = {}
    load_motions(db, "_ex_sim/jp")
