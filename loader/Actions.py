import json
import os
import sys
from glob import glob
from tqdm import tqdm
import re

from loader.Database import DBManager, DBTableMetadata
from loader.Enums import CommandType

HIT_LABEL_FIELDS = (
    "_hitLabel",
    "_hitAttrLabel",
    "_hitAttrLabelSubList",
    "_abHitAttrLabel",
)

HASLV_PATTERN = re.compile(r"(S\d{3}_\d{3}.*)_LV\d{2}")
LV_PATTERN = re.compile(r"_LV\d{2}.*")


def build_hitlabel_data(ref, k, hit_labels):
    if not hit_labels:
        return tuple()
    if isinstance(hit_labels, str):
        hit_labels = (hit_labels,)
    processed = []
    for idx, label in enumerate(hit_labels):
        label = label.strip()
        if not label:
            continue
        if "CMN_AVOID" in label:
            label_re = label
        elif LV_PATTERN.search(label):
            label_re = LV_PATTERN.sub(r"(?:_HAS)?_LV[0-9]{2}.*", label)
        else:
            label_re = f"{label}.*"
        processed.append({"_Id": f"{ref}{k}{idx}", "_ref": ref, "_source": k, "_hitLabel": label, "_hitLabelRE": label_re})
    return processed
    # return (
    #     {
    #         "_Id": f"{ref}{k}{idx}",
    #         "_ref": ref,
    #         "_hitLabel": label.strip(),
    #         "_source": k,
    #     }
    #     for idx, label in enumerate(hit_labels)
    #     if label.strip()
    # )


# seen_id = set()
def build_db_data(meta, ref, seq, data):
    db_data = {}
    hitlabel_data = []
    for k in meta.field_type.keys():
        if k in data:
            if ACTION_PART.get_field(k) == DBTableMetadata.BLOB and not any(data[k]):
                db_data[k] = None
            elif isinstance(data[k], str):
                db_data[k] = data[k].strip()
            else:
                db_data[k] = data[k]
        else:
            db_data[k] = None
    db_data["_Id"] = f"{ref}{seq:05}"
    db_data["_ref"] = int(ref)
    db_data["_seq"] = seq
    for k in HIT_LABEL_FIELDS:
        if k in data:
            hitlabel_data.extend(build_hitlabel_data(db_data["_Id"], k, data[k]))
    if loop := data.get("_loopData"):
        db_data["_loopFlag"] = loop["flag"]
        db_data["_loopNum"] = loop["loopNum"]
        db_data["_loopFrame"] = loop["restartFrame"]
        db_data["_loopSec"] = loop["restartSec"]
    # if db_data['_Id'] in seen_id:
    #     print(db_data['_Id'])
    # seen_id.add(db_data['_Id'])
    cond_data = data["_conditionData"]
    if cond_data["_conditionType"]:
        db_data["_conditionType"] = cond_data["_conditionType"]
        db_data["_conditionValue"] = cond_data["_conditionValue"]
    if db_data.get("_hitRecordTargetBuffType") == -1:
        db_data["_hitRecordTargetBuffType"] = None
    return db_data, hitlabel_data


def build_arrange_data(meta, ref, seq, data):
    if not data.get("_abHitAttrLabel"):
        return None, None
    return build_db_data(meta, ref, seq, data)


def build_bullet(meta, ref, seq, data):
    db_data, hitlabel_data = build_db_data(meta, ref, seq, data)
    if ab_label := data["_arrangeBullet"]["_abHitAttrLabel"]:
        hitlabel_data.extend(build_hitlabel_data(db_data["_Id"], "_abHitAttrLabel", ab_label))
    if ab_duration := data["_arrangeBullet"]["_abDuration"]:
        db_data["_abDuration"] = ab_duration
    if ab_interval := data["_arrangeBullet"]["_abHitInterval"]:
        db_data["_abHitInterval"] = ab_interval
    if ab_collision_flag := data["_arrangeBullet"]["_abUseAccurateCollisionHitInterval"]:
        db_data["_abUseAccurateCollisionHitInterval"] = ab_collision_flag
    if db_data["_delayFireSec"] and not any(db_data["_delayFireSec"]):
        db_data["_delayFireSec"] = None
    if data.get("_useMarker"):
        db_data["_bulletMarkerChargeSec"] = data["_marker"]["_chargeSec"]
    return db_data, hitlabel_data


def build_formation_bullet(meta, ref, seq, data):
    bullet_attrs = set()
    for idx in range(data["_childNum"]):
        act = data["_child"][idx]
        try:
            bullet_attrs.add(act["bulletData"]["_hitAttrLabel"])
        except:
            pass
    data["_bulletNum"] = data["_childNum"]
    data["_hitAttrLabelSubList"] = bullet_attrs
    return build_db_data(meta, ref, seq, data)


def build_marker(meta, ref, seq, data):
    db_data, hitlabel_data = build_db_data(meta, ref, seq, data)
    if charge_lvl_sec := db_data.get("_chargeLvSec"):
        if "_nextLevelMarkerCount" in data and data["_nextLevelMarkerCount"]:
            for lvl in data["_nextLevelMarkerData"]:
                charge_lvl_sec.extend(lvl["_chargeLvSec"])
        if not any(charge_lvl_sec):
            db_data["_chargeLvSec"] = None
        else:
            db_data["_chargeLvSec"] = charge_lvl_sec
    if not db_data["_chargeSec"] and not db_data["_chargeLvSec"]:
        return None, None
    if aoci := db_data.get("_activateOnChargeImpact"):
        if not any(aoci):
            db_data["_activateOnChargeImpact"] = None
    return db_data, hitlabel_data


def build_animation(meta, ref, seq, data):
    db_data, hitlabel_data = build_db_data(meta, ref, seq, data)
    if "_name" in data and data["_name"]:
        db_data["_animationName"] = data["_name"]
        return db_data, hitlabel_data
    return None, None


def build_control_data(meta, ref, seq, data):
    db_data, hitlabel_data = build_db_data(meta, ref, seq, data)
    arg_data = {}
    for key, value in data.items():
        if key not in db_data and not isinstance(value, dict):
            if isinstance(value, list):
                if any(value):
                    arg_data[key] = value
            elif value:
                arg_data[key] = value
    if arg_data:
        db_data["_charaCommandArgs"] = arg_data
        return db_data, hitlabel_data
    return None, None


ACTION_PART = DBTableMetadata(
    "ActionParts",
    pk="_Id",
    field_type={
        "_Id": DBTableMetadata.INT + DBTableMetadata.PK,
        "_ref": DBTableMetadata.INT,
        "_seq": DBTableMetadata.INT,
        "_seconds": DBTableMetadata.REAL,
        "_speed": DBTableMetadata.REAL,
        "_duration": DBTableMetadata.REAL,
        "_activateId": DBTableMetadata.INT,
        "commandType": DBTableMetadata.INT,
        # PLAY_MOTION
        "_motionState": DBTableMetadata.TEXT,
        "_motionFrame": DBTableMetadata.INT,
        "_blendDuration": DBTableMetadata.REAL,
        "_isBlend": DBTableMetadata.INT,
        "_isEndSyncMotion": DBTableMetadata.INT,
        "_isIgnoreFinishCondition": DBTableMetadata.INT,
        "_isIdleAfterCancel": DBTableMetadata.INT,
        # MOVEMENT
        # '_position': DBTableMetadata.BLOB,
        # '_pushOut': DBTableMetadata.INT,
        # '_autoDash': DBTableMetadata.INT,
        # '_chargeMarker': DBTableMetadata.INT,
        # '_gravity': DBTableMetadata.REAL,
        # '_moveStyle': DBTableMetadata.INT,
        # '_teleportPosition': DBTableMetadata.INT,
        # '_teleportDirection': DBTableMetadata.INT,
        # '_distance': DBTableMetadata.INT,
        # ROTATION
        # '_rotation': DBTableMetadata.BLOB,
        # MARKER
        "_useForEachChargeTime": DBTableMetadata.INT,
        "_chargeSec": DBTableMetadata.REAL,
        "_chargeLvSec": DBTableMetadata.BLOB,
        "_activateOnChargeImpact": DBTableMetadata.BLOB,
        # '_chargeAfterSec': DBTableMetadata.REAL,
        # '_ignoredByPlayerAI': DBTableMetadata.INT,
        # '_invisibleForPlayerAI': DBTableMetadata.INT,
        # '_playerAIEscapeDir': DBTableMetadata.INT,
        # '_ignoredImpactWaitForPlayerColor': DBTableMetadata.INT,
        # HIT/BULLET
        "_bulletSpeed": DBTableMetadata.REAL,
        "_bulletDuration": DBTableMetadata.REAL,
        "_delayTime": DBTableMetadata.REAL,
        "_isHitDelete": DBTableMetadata.INT,
        "_abHitInterval": DBTableMetadata.REAL,
        "_abDuration": DBTableMetadata.REAL,
        "_bulletNum": DBTableMetadata.INT,
        "_fireMaxCount": DBTableMetadata.INT,
        "_generateNum": DBTableMetadata.INT,
        # "_generateDelay": DBTableMetadata.REAL, # this is unused
        "_generateNumDependOnBuffCount": DBTableMetadata.INT,
        "_buffCountConditionId": DBTableMetadata.INT,
        "_setBulletDelayOneByOne": DBTableMetadata.INT,
        "_useFireStockBulletParam": DBTableMetadata.INT,
        # "_bulletDelayTime": DBTableMetadata.BLOB,
        "_markerDelay": DBTableMetadata.BLOB,
        "_lifetime": DBTableMetadata.REAL,
        "_conditionType": DBTableMetadata.INT,
        "_conditionValue": DBTableMetadata.BLOB,
        "_attenuationRate": DBTableMetadata.REAL,
        "_canBeSameTarget": DBTableMetadata.INT,
        "_addNum": DBTableMetadata.INT,
        "_useAccurateCollisionHitInterval": DBTableMetadata.INT,
        "_abUseAccurateCollisionHitInterval": DBTableMetadata.INT,
        # COLLISION
        "_collision": DBTableMetadata.INT,
        "_collisionPosId": DBTableMetadata.INT,
        "_collisionParams_01": DBTableMetadata.REAL,  # Length
        "_collisionParams_02": DBTableMetadata.REAL,  # Width
        "_collisionParams_03": DBTableMetadata.REAL,  # Height
        "_collisionParams_05": DBTableMetadata.REAL,  # Angle
        "_collisionParams_06": DBTableMetadata.REAL,
        "_collisionHitInterval": DBTableMetadata.REAL,
        # SEND_SIGNAL
        "_signalType": DBTableMetadata.INT,
        "_decoId": DBTableMetadata.INT,
        "_actionId": DBTableMetadata.INT,
        "_keepActionEnd": DBTableMetadata.INT,
        "_keepActionId1": DBTableMetadata.INT,
        "_keepActionId2": DBTableMetadata.INT,
        "_hitRecordTargetBuffType": DBTableMetadata.INT,
        # ACTIVE_CANCEL
        "_actionType": DBTableMetadata.INT,
        "_motionEnd": DBTableMetadata.INT,
        # CONTROL
        "_charaCommand": DBTableMetadata.INT,
        "_charaCommandArgs": DBTableMetadata.BLOB,
        # BULLETS
        "_bulletMarkerChargeSec": DBTableMetadata.REAL,
        "_waitTime": DBTableMetadata.REAL,
        "_delayFireSec": DBTableMetadata.BLOB,
        "_isReserveFireBulletForWaiting": DBTableMetadata.INT,
        "_isDelayAffectedBySpeedFactor": DBTableMetadata.INT,
        "_removeStockBulletOnFinish": DBTableMetadata.INT,
        # ANIMATION
        "_animationName": DBTableMetadata.TEXT,
        "_isVisible": DBTableMetadata.INT,
        "_isActionClear": DBTableMetadata.INT,
        # ACTION_CONDITON
        "_actionConditionId": DBTableMetadata.INT,
        # BUFF_FIELD_ATTACH
        "_isAttachToBuffField": DBTableMetadata.INT,
        "_isAttachToSelfBuffField": DBTableMetadata.INT,
        "_hitDelaySec": DBTableMetadata.REAL,
        # LOOP DATA
        "_loopFlag": DBTableMetadata.INT,
        "_loopNum": DBTableMetadata.INT,
        "_loopFrame": DBTableMetadata.INT,
        "_loopSec": DBTableMetadata.REAL,
        # # TIMESTOP
        # "_stopMotionPositionSec": DBTableMetadata.REAL,
        # "_stopTimeSpanSec": DBTableMetadata.REAL,
        # "_isRepeat": DBTableMetadata.INT,
        # "_isOverridePlaySpeed": DBTableMetadata.INT,
        # "_playSpeed": DBTableMetadata.REAL,
        # # TIMECURVE
        # "_isNormalizeCurve": DBTableMetadata.INT,
        # AUTOFIRE
        "_autoFireInterval": DBTableMetadata.REAL,
        "_autoFireActionId": DBTableMetadata.INT,
        "_autoFireActionIdList": DBTableMetadata.BLOB,
        "_autoFireEffectTrigger": DBTableMetadata.INT,
        "_autoFireEffectTriggerResetTime": DBTableMetadata.REAL,
        "_autoFireAutoSearchEnemyRadius": DBTableMetadata.REAL,
        "_burstAttackActionId": DBTableMetadata.INT,
        # SERVANT
        "_servantActionCommandId": DBTableMetadata.INT,
        # REMOVE_BUFF_TRIGGER_BOMB
        "_targetActionConditionId": DBTableMetadata.INT,
    },
)

ACTION_PART_HIT_LABEL = DBTableMetadata(
    "ActionPartsHitLabel",
    pk="_Id",
    field_type={
        "_Id": DBTableMetadata.TEXT + DBTableMetadata.PK,
        "_ref": DBTableMetadata.INT,
        "_source": DBTableMetadata.TEXT,
        "_hitLabel": DBTableMetadata.TEXT,
        "_hitLabelRE": DBTableMetadata.TEXT,
        # "_hasLV": DBTableMetadata.INT,
        # "_hasCHLV": DBTableMetadata.INT,
    },
)

PROCESSORS = {}
PROCESSORS[CommandType.PLAY_MOTION] = build_db_data
PROCESSORS[CommandType.GEN_MARKER] = build_marker
PROCESSORS[CommandType.GEN_BULLET] = build_bullet
PROCESSORS[CommandType.HIT_ATTRIBUTE] = build_db_data
# PROCESSORS[CommandType.HIT_STOP] = build_db_data
# PROCESSORS[CommandType.MOVE_TIME_CURVE] = build_db_data
PROCESSORS[CommandType.ARRANGE_BULLET] = build_arrange_data
PROCESSORS[CommandType.SEND_SIGNAL] = build_db_data
PROCESSORS[CommandType.ACTIVE_CANCEL] = build_db_data
PROCESSORS[CommandType.MULTI_BULLET] = build_bullet
PROCESSORS[CommandType.PARABOLA_BULLET] = build_bullet
PROCESSORS[CommandType.PIVOT_BULLET] = build_bullet
PROCESSORS[CommandType.STOCK_BULLET_ROUND] = build_bullet
PROCESSORS[CommandType.STOCK_BULLET_FIRE] = build_bullet
PROCESSORS[CommandType.FORMATION_BULLET] = build_formation_bullet
PROCESSORS[CommandType.SETTING_HIT] = build_db_data
PROCESSORS[CommandType.REMOVE_BUFF_TRIGGER_BOMB] = build_db_data
PROCESSORS[CommandType.BUFF_CAPTION] = build_db_data
PROCESSORS[CommandType.BUFFFIELD_ATTACHMENT] = build_db_data
PROCESSORS[CommandType.BUTTERFLY_BULLET] = build_bullet
PROCESSORS[CommandType.STOCK_BULLET_SHIKIGAMI] = build_bullet
PROCESSORS[CommandType.CHARACTER_COMMAND] = build_control_data
PROCESSORS[CommandType.STOCK_BULLET_NEVOPTION] = build_bullet


def log_schema_keys(schema_map, data, command_type):
    schema_map[str(command_type)] = {key: type(value).__name__ for key, value in data.items()}
    for subdata in data.values():
        try:
            if command_type := subdata.get("commandType"):
                log_schema_keys(schema_map, subdata, CommandType(command_type))
        except:
            pass


def load_actions(db, path):
    schema_map = {}
    db.drop_table(ACTION_PART.name)
    db.create_table(ACTION_PART)
    db.drop_table(ACTION_PART_HIT_LABEL.name)
    db.create_table(ACTION_PART_HIT_LABEL)
    sorted_data = []
    sorted_hitlabel_data = []
    for filepath in tqdm(glob(path + "/PlayerAction*"), desc="action"):
        ref = os.path.splitext(filepath.split("_")[-1])[0]
        with open(filepath) as f:
            raw = json.load(f)
            # action = [gameObject['_data'] for gameObject in raw if '_data' in gameObject.keys()]
            action = []
            seq = 0
            for actdata in raw:
                action.append(actdata)
                if (additional := actdata.get("_additionalCollision")) and actdata.get("_addNum"):
                    for idx in range(actdata["_addNum"]):
                        act = additional[idx]
                        act["_seconds"] += actdata["_seconds"]
                        action.append(act)
                # action.extend(((seq+100*(1+i), act) for i, act in enumerate(additional)))
            for seq, data in enumerate(action):
                try:
                    command_type = CommandType(data["commandType"])
                except TypeError:
                    command_type = data["commandType"]
                    print(f"Unknown command type {command_type} in {filepath}")
                log_schema_keys(schema_map, data, command_type)
                if command_type in PROCESSORS:
                    builder = PROCESSORS[command_type]
                    db_data, hitlabel_data = builder(ACTION_PART, ref, seq, data)
                    if db_data is not None:
                        sorted_data.append(db_data)
                    if hitlabel_data:
                        sorted_hitlabel_data.extend(hitlabel_data)
    db.insert_many(ACTION_PART.name, sorted_data)
    db.insert_many(ACTION_PART_HIT_LABEL.name, sorted_hitlabel_data)
    return schema_map


def summarize_raw_action_json(raw, key=""):
    for seq, actdata in enumerate(raw):
        if not actdata:
            continue
        if not isinstance(actdata, dict):
            continue
        if not "commandType" in actdata:
            continue
        cmd = CommandType(actdata["commandType"])
        sec = actdata["_seconds"]
        if key:
            print(f"{key}:", end=" ")
        if cmd in PROCESSORS:
            print(f"{seq:03} {sec:.4f}s: {cmd} [PROCESSED]")
        else:
            print(f"{seq:03} {sec:.4f}s: {cmd} [SKIPPED]")
        for k, v in actdata.items():
            if isinstance(v, list):
                summarize_raw_action_json(v, f"{key}.{k}")
            else:
                summarize_raw_action_json((v,), f"{key}.{k}")


if __name__ == "__main__":
    db = DBManager()
    if len(sys.argv) > 1:
        path = f"./_ex_sim/jp/actions/PlayerAction_{sys.argv[1]:>08}.json"
        print(path)
        with open(path) as f:
            raw = json.load(f)
            summarize_raw_action_json(raw)
    else:
        schema_map = load_actions(db, "./_ex_sim/jp/actions")
        with open("./out/_action_schema.json", "w") as f:
            json.dump(schema_map, f, indent=4, sort_keys=True, default=str)
