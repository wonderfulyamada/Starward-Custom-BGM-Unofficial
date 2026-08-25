"""Folder-based BGM storage with a central JSON group membership list."""
from __future__ import annotations

import json
import random
import shutil
import wave
from pathlib import Path

SUPPORTED_EXTENSIONS = {".mp3", ".ogg", ".wav"}
LIBRARY_SCOPE = "All BGM"
DEFAULT_GROUP = "Default"
LEGACY_DEFAULT_GROUP = "デフォルト"


class MusicLibrary:
    def __init__(self, root, index_path=None):
        self.root = Path(root)
        self.index_path = Path(index_path) if index_path else self.root.parent / "bgm_library.json"
        self.groups_data = {}
        self.awakening_offsets = {}
        self.history = []
        self.refresh()

    @staticmethod
    def _valid_name(name):
        return bool(name) and name not in {".", ".."} and "/" not in name and "\\" not in name

    def _group_path(self, name):
        return self.root / name

    def _load(self):
        try:
            data = json.loads(self.index_path.read_text(encoding="utf-8")) if self.index_path.exists() else {"groups": {}}
            groups = data.get("groups", {})
            if not isinstance(groups, dict):
                raise ValueError("groups must be an object of track lists")
            self.groups_data = {
                str(name): [str(track) for track in tracks]
                for name, tracks in groups.items()
                if self._valid_name(str(name)) and isinstance(tracks, list)
            }
            offsets = data.get("awakening_offsets", {})
            self.awakening_offsets = {
                str(track): self._safe_offset(offset)
                for track, offset in offsets.items()
                if isinstance(track, str)
            } if isinstance(offsets, dict) else {}
        except (OSError, ValueError, TypeError) as exc:
            print(f"BGM library JSON error: {exc}")
            self.groups_data = {}
            self.awakening_offsets = {}
        # Keep old Japanese default entries usable, but write the system name.
        legacy = self.groups_data.pop(LEGACY_DEFAULT_GROUP, [])
        self.groups_data.setdefault(DEFAULT_GROUP, legacy)

    def _save(self):
        self.index_path.write_text(
            json.dumps({"version": 2, "groups": self.groups_data, "awakening_offsets": self.awakening_offsets}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def _migrate_flat_tracks(self):
        flat_tracks = [path for path in self.root.iterdir() if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS]
        if not flat_tracks:
            return
        default = self._group_path(DEFAULT_GROUP)
        default.mkdir(exist_ok=True)
        for track in flat_tracks:
            shutil.move(str(track), str(default / track.name))
            if track.name not in self.groups_data[DEFAULT_GROUP]:
                self.groups_data[DEFAULT_GROUP].append(track.name)

    def _synchronize_with_disk(self):
        """Make central membership exactly reflect immediate BGM folders."""
        groups = {}
        existing_references = set()
        for folder in sorted(self.root.iterdir(), key=lambda path: path.name.casefold()):
            if not folder.is_dir() or not self._valid_name(folder.name):
                continue
            tracks = sorted(
                (
                    path.name for path in folder.iterdir()
                    if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
                ),
                key=str.casefold,
            )
            groups[folder.name] = tracks
            existing_references.update(f"{folder.name}/{track}" for track in tracks)
        groups.setdefault(DEFAULT_GROUP, [])
        self.groups_data = groups
        self.awakening_offsets = {
            reference: offset
            for reference, offset in self.awakening_offsets.items()
            if reference in existing_references
        }

    def refresh(self):
        self.root.mkdir(parents=True, exist_ok=True)
        self._load()
        self._group_path(DEFAULT_GROUP).mkdir(exist_ok=True)
        self.groups_data.setdefault(DEFAULT_GROUP, [])
        self._migrate_flat_tracks()
        self._synchronize_with_disk()
        self._save()

    def groups(self):
        names = [name for name in self.groups_data if self._group_path(name).is_dir()]
        return [DEFAULT_GROUP] + sorted(name for name in names if name != DEFAULT_GROUP)

    def normalize_group(self, group):
        group = DEFAULT_GROUP if group == LEGACY_DEFAULT_GROUP else group
        return group if group in self.groups() else DEFAULT_GROUP

    def _track_path(self, group, track):
        candidate = self._group_path(group) / track
        try:
            candidate.relative_to(self._group_path(group))
        except ValueError:
            return None
        return candidate

    def tracks(self, group=None):
        groups = self.groups() if not group or group == LIBRARY_SCOPE else [self.normalize_group(group)]
        tracks = []
        for name in groups:
            for track in self.groups_data.get(name, []):
                path = self._track_path(name, track)
                if path is not None and path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
                    tracks.append(path)
        return tracks

    def track_reference(self, track):
        return Path(track).relative_to(self.root).as_posix()

    @staticmethod
    def _safe_offset(value):
        try:
            return max(0.0, float(value))
        except (TypeError, ValueError):
            return 0.0

    def awakening_offset(self, track):
        reference = self.track_reference(track) if Path(track).is_absolute() else str(track)
        return self._safe_offset(self.awakening_offsets.get(reference, 0.0))

    def set_awakening_offset(self, track, seconds):
        reference = self.track_reference(track) if Path(track).is_absolute() else str(track)
        self.awakening_offsets[reference] = self._safe_offset(seconds)
        self._save()

    @staticmethod
    def track_duration(track):
        """Return duration in seconds when metadata is available, else None."""
        track = Path(track)
        try:
            if track.suffix.lower() == ".wav":
                with wave.open(str(track), "rb") as audio:
                    if audio.getframerate() <= 0:
                        return None
                    return audio.getnframes() / audio.getframerate()
            if track.suffix.lower() in {".mp3", ".ogg"}:
                from mutagen import File
                audio = File(track)
                length = getattr(getattr(audio, "info", None), "length", None)
                return float(length) if length is not None and float(length) >= 0 else None
        except Exception:
            return None
        return None

    def resolve_track(self, reference, group=None):
        if not reference:
            return None
        path = Path(reference)
        if path.is_absolute():
            return path if path.is_file() else None
        if len(path.parts) > 1:
            candidate = self.root / path
            return candidate if candidate.is_file() else None
        matches = [track for track in self.tracks(group) if track.name == reference]
        return matches[0] if len(matches) == 1 else None

    def create_group(self, name):
        name = name.strip()
        if not self._valid_name(name) or name in self.groups_data or self._group_path(name).exists():
            raise ValueError("Group name must be unique and non-empty")
        self._group_path(name).mkdir()
        self.groups_data[name] = []
        self._save()

    def rename_group(self, old_name, new_name):
        old_name, new_name = self.normalize_group(old_name), new_name.strip()
        if old_name == DEFAULT_GROUP:
            raise ValueError("Default cannot be renamed")
        if old_name not in self.groups_data or not self._valid_name(new_name) or new_name in self.groups_data:
            raise ValueError("Group name must be unique and non-empty")
        self._group_path(old_name).rename(self._group_path(new_name))
        self.groups_data[new_name] = self.groups_data.pop(old_name)
        self._save()

    def delete_group(self, name):
        name = self.normalize_group(name)
        if name == DEFAULT_GROUP:
            raise ValueError("Default cannot be deleted")
        if name in self.groups_data:
            shutil.rmtree(self._group_path(name), ignore_errors=True)
            del self.groups_data[name]
            self._save()

    def set_membership(self, group, track_name, included):
        group = self.normalize_group(group)
        track_name = Path(track_name).name
        path = self._track_path(group, track_name)
        if path is None or not path.is_file():
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
            selected = self.resolve_track(fixed_track, group)
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
