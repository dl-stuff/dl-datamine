import re

from loader.Database import DBManager, DBView, PartsTable, DBDict
from exporter.Mappings import (
    # PartConditionType,
    # PartConditionComparisonType,
    ActionCancelType,
    ActionSignalType,
    # CharacterControl,
)


class PartsHitLabel(DBView):
    LV_PATTERN = re.compile(r"_LV\d{2}.*")
    LV_CHLV_PATTERN = re.compile(r"_CHLV\d{2}")

    def __init__(self, index):
        super().__init__(index, "PartsHitLabel", override_view=True)

    def open(self):
        self.name = f"View_{self.base_table}"
        self.database.conn.execute(f"DROP VIEW IF EXISTS {self.name}")
        self.database.conn.execute(
            f"CREATE VIEW {self.name} AS SELECT PartsHitLabel.pk, PlayerActionHitAttribute.* FROM PartsHitLabel LEFT JOIN PlayerActionHitAttribute WHERE PlayerActionHitAttribute._Id GLOB PartsHitLabel.hitLabelGlob"
        )
        self.database.conn.commit()

    def process_result(self, res):
        for r in res:
            del r["pk"]
        return self.index["PlayerActionHitAttribute"].process_result(res)

    def get(self, pk, **kwargs):
        kwargs["expand_one"] = False
        return super().get(pk, **kwargs)


class Parts_PLAY_MOTION(PartsTable):
    def __init__(self, index):
        super().__init__(index)
        self.anim_ref = None

    def process_result(self, res):
        res = super().process_result(res)
        if self.anim_ref is not None and (motion_state := res.get("_motionState")):
            animation = self.index["MotionData"].get_by_state_ref(motion_state, self.anim_ref)
            if animation:
                for anim in animation:
                    del anim["pathID"]
                    del anim["ref"]
                res["_animation"] = animation
        return res


class Parts_ACTIVE_CANCEL(PartsTable):
    def process_result(self, res):
        res = super().process_result(res)
        if res.get("_actionType"):
            res["_actionType"] = ActionCancelType(res["_actionType"])
        return res


class Parts_SEND_SIGNAL(PartsTable):
    @staticmethod
    def remove_falsy_fields(res):
        return DBDict(filter(lambda x: x[0] in ("seq", "_seconds", "_signalType") or bool(x[1]), res.items()))

    def process_result(self, res):
        res = super().process_result(res)
        res["_signalType"] = ActionSignalType(res["_signalType"])
        if res["_signalType"] == ActionSignalType.ChangePartsMesh:
            self.expand_fk(res, "_changeParts")
        else:
            del res["_changeParts"]
        if res["_signalType"] == ActionSignalType.EnableAction:
            self.expand_fk(res, "_enableAction")
        else:
            del res["_enableAction"]
        if res.get("_actionType"):
            res["_actionType"] = ActionCancelType(res["_actionType"])
        return res


class PartsIndex(DBView):
    EXCLUDE_FALSY = False

    def __init__(self, index):
        super().__init__(index, "PartsIndex")

    def process_result(self, results):
        full_results = []
        for res in results:
            full_results.append(self.index[res["part"]].get(res["pk"]))
        return sorted(full_results, key=lambda res: res.get("_seconds"))

    def get(self, act):
        return super().get(act, by="act", mode=DBManager.EXACT, expand_one=False)
