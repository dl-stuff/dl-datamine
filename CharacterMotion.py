import json
import os
from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class AnimationClipData:
    name: str
    startTime: float
    stopTime: float
    id: Optional[int] = field(init=False)
    duration: float = field(init=False)

    def __post_init__(self):
        self.duration = self.stopTime - self.startTime
        try:
            self.id = int(self.name.split('_')[-1])
        except (IndexError, ValueError):
            self.id = None


def load_animation_clip_data(in_path: str) -> Optional[AnimationClipData]:
    with open(in_path) as f:
        data = json.load(f)
        return AnimationClipData(
            name=data['name'],
            startTime=data['m_MuscleClip']['m_StartTime'],
            stopTime=data['m_MuscleClip']['m_StopTime']
        )


def get_animation_clip_data(in_dir: str) -> Dict[str, AnimationClipData]:
    clips = {}
    for root, _, files in os.walk(in_dir):
        for file_name in files:
            file_path = os.path.join(root, file_name)
            try:
                clip = load_animation_clip_data(file_path)
                clips[clip.name] = clip
            except (KeyError, TypeError):
                pass
    return clips


def get_animation_clip_data_by_id(in_dir: str) -> Dict[Optional[int], Dict[str, AnimationClipData]]:
    clips = {}
    data = get_animation_clip_data(in_dir)
    for clip in data.values():
        if clip.id not in clips:
            clips[clip.id] = {}
        clips[clip.id][clip.name] = clip
    return clips
