from loader.Database import DBManager, DBView, PartsTable
from exporter.Mappings import (
    PartConditionType,
    PartConditionComparisonType,
    ActionCancelType,
    ActionSignalType,
    CharacterControl,
)


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


# class Parts_HIT_ATTRIBUTE(PartsTable):
#     pass


class PartsIndex(DBView):
    EXCLUDE_FALSY = False

    def __init__(self, index):
        super().__init__(index, "PartsIndex")

    def process_result(self, results):
        full_results = []
        for res in results:
            full_results.append(self.index[res["part"]].get(res["pk"]))
        return full_results

    def get(self, act):
        return super().get(act, by="act", mode=DBManager.EXACT, expand_one=False)
