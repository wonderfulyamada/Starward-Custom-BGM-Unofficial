"""Flat BGM library with JSON-managed group membership."""
from __future__ import annotations

import json
import random
from pathlib import Path

SUPPORTED_EXTENSIONS = {".mp3", ".ogg", ".wav"}
LIBRARY_SCOPE = "All BGM"
DEFAULT_GROUP = "デフォルト"
REQUIRED_GROUPS = (DEFAULT_GROUP,)
LEGACY_AUTO_GROUPS = {"ロック", "ネタ", "お気に入り"}


class MusicLibrary:
    def __init__(self, root, index_path=None):
        self.root = Path(root)
        self.index_path = Path(index_path) if index_path else self.root.parent / "bgm_library.json"
        self.history = []
        self.groups_data = {name: [] for name in REQUIRED_GROUPS}
        self._valid_index = True
        self._legacy_index = False
        self.refresh()

    def _default_groups(self):
        return {name: [] for name in REQUIRED_GROUPS}

    def _load(self):
        if not self.index_path.exists():
            self.groups_data = self._default_groups()
            self._save()
            return
        try:
            data = json.loads(self.index_path.read_text(encoding="utf-8"))
            groups = data["groups"]
            if not isinstance(groups, dict) or any(not isinstance(items, list) for items in groups.values()):
                raise ValueError("groups must be an object of track lists")
            self.groups_data = {str(name): [str(item) for item in items] for name, items in groups.items()}
            self._legacy_index = data.get("version") != 2
            for name in REQUIRED_GROUPS:
                self.groups_data.setdefault(name, [])
        except (OSError, ValueError, KeyError, TypeError) as exc:
            print(f"BGM library JSON error: {exc}")
            self.groups_data = self._default_groups()
            self._valid_index = False

    def _save(self):
        if self._valid_index:
            self.index_path.write_text(json.dumps({"version": 2, "groups": self.groups_data}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def refresh(self):
        self.root.mkdir(parents=True, exist_ok=True)
        self._valid_index = True
        self._load()
        available = {path.name for path in self.root.iterdir() if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS}
        for name, members in self.groups_data.items():
            self.groups_data[name] = [track for track in members if track in available]
        if self._legacy_index:
            for name in LEGACY_AUTO_GROUPS:
                if not self.groups_data.get(name):
                    self.groups_data.pop(name, None)
        default = self.groups_data[DEFAULT_GROUP]
        default.extend(track for track in sorted(available) if track not in default)
        self._save()

    def groups(self):
        return list(self.groups_data)

    def tracks(self, group=None):
        if not group or group == LIBRARY_SCOPE:
            names = sorted(path.name for path in self.root.iterdir() if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS)
        else:
            names = self.groups_data.get(group, [])
        return [self.root / name for name in names if (self.root / name).is_file()]

    def create_group(self, name):
        name = name.strip()
        if not name or name in self.groups_data:
            raise ValueError("Group name must be unique and non-empty")
        self.groups_data[name] = []
        self._save()

    def rename_group(self, old_name, new_name):
        new_name = new_name.strip()
        if old_name == DEFAULT_GROUP:
            raise ValueError("デフォルト cannot be renamed")
        if old_name not in self.groups_data or not new_name or new_name in self.groups_data:
            raise ValueError("Group name must be unique and non-empty")
        self.groups_data[new_name] = self.groups_data.pop(old_name)
        self._save()

    def delete_group(self, name):
        if name == DEFAULT_GROUP:
            raise ValueError("デフォルト cannot be deleted")
        if name in self.groups_data:
            del self.groups_data[name]
            self._save()

    def set_membership(self, group, track_name, included):
        if group not in self.groups_data or not (self.root / track_name).is_file():
            return
        members = self.groups_data[group]
        if included and track_name not in members:
            members.append(track_name)
        elif not included and track_name in members:
            members.remove(track_name)
        self._save()

    def choose(self, mode, group=LIBRARY_SCOPE, fixed_track=""):
        tracks = self.tracks(group)
        if not tracks:
            return None
        if mode == "Fixed":
            selected = self.root / fixed_track
            return selected if selected in tracks else None
        if mode == "True Random":
            selected = random.choice(tracks)
        else:
            recent = list(reversed(self.history))
            rank = {track: index for index, track in enumerate(recent)}
            weights = [1 + rank.get(track, len(recent)) for track in tracks]
            selected = random.choices(tracks, weights=weights, k=1)[0]
        self.history.append(selected)
        if len(self.history) > max(1, len(tracks) * 2):
            del self.history[:-len(tracks) * 2]
        return selected
