import json
import tempfile
import sys
import types
import unittest
import wave
from unittest.mock import patch
from pathlib import Path

from music_library import DEFAULT_GROUP, LIBRARY_SCOPE, MusicLibrary


class FolderGroupLibraryTests(unittest.TestCase):
    def make_library(self, groups=None):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        (root / "bgm_library.json").write_text(json.dumps({"version": 2, "groups": groups or {}}), encoding="utf-8")
        return root, MusicLibrary(root / "BGM")

    def test_default_folder_and_library_entry_are_recreated(self):
        root, library = self.make_library({"A": []})
        self.assertTrue((root / "BGM" / "Default").is_dir())
        self.assertIn(DEFAULT_GROUP, library.groups())
        saved = json.loads((root / "bgm_library.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["groups"][DEFAULT_GROUP], [])

    def test_startup_scan_discovers_new_group_and_tracks(self):
        root, library = self.make_library({})
        folder = root / "BGM" / "Awakening"
        folder.mkdir()
        (folder / "one.ogg").write_bytes(b"audio")
        (folder / "two.wav").write_bytes(b"audio")
        library.refresh()
        self.assertEqual(library.groups(), [DEFAULT_GROUP, "Awakening"])
        self.assertEqual([track.name for track in library.tracks("Awakening")], ["one.ogg", "two.wav"])

    def test_startup_scan_discovers_new_track_in_existing_group(self):
        root, library = self.make_library({})
        folder = root / "BGM" / "Default"
        (folder / "added.mp3").write_bytes(b"audio")
        library.refresh()
        self.assertEqual([track.name for track in library.tracks(DEFAULT_GROUP)], ["added.mp3"])

    def test_startup_scan_removes_deleted_track_and_its_metadata(self):
        root, library = self.make_library({})
        track = root / "BGM" / "Default" / "gone.ogg"
        track.write_bytes(b"audio")
        library.refresh()
        library.set_awakening_offset(track, 12.5)
        track.unlink()
        library.refresh()
        self.assertEqual(library.tracks(DEFAULT_GROUP), [])
        self.assertNotIn("Default/gone.ogg", library.awakening_offsets)

    def test_startup_scan_removes_deleted_non_default_group(self):
        root, library = self.make_library({})
        folder = root / "BGM" / "Temporary"
        folder.mkdir()
        library.refresh()
        folder.rmdir()
        library.refresh()
        self.assertNotIn("Temporary", library.groups())

    def test_startup_scan_preserves_existing_track_metadata(self):
        root, library = self.make_library({})
        track = root / "BGM" / "Default" / "kept.ogg"
        track.write_bytes(b"audio")
        library.refresh()
        library.set_awakening_offset(track, 8.75)
        library.refresh()
        self.assertEqual(library.awakening_offset(track), 8.75)

    def test_multiple_group_folders_resolve_central_membership(self):
        root, _ = self.make_library({"Default": [], "A": ["a.ogg"], "B": ["b.wav"]})
        for group, track in (("A", "a.ogg"), ("B", "b.wav")):
            folder = root / "BGM" / group
            folder.mkdir(exist_ok=True)
            (folder / track).write_bytes(b"audio")
        library = MusicLibrary(root / "BGM")
        self.assertEqual(library.tracks("A"), [root / "BGM" / "A" / "a.ogg"])
        self.assertEqual(library.tracks("B"), [root / "BGM" / "B" / "b.wav"])
        self.assertEqual(library.choose("Fixed", "A", "A/a.ogg"), root / "BGM" / "A" / "a.ogg")

    def test_default_cannot_be_deleted_and_invalid_group_falls_back(self):
        _, library = self.make_library({})
        with self.assertRaises(ValueError):
            library.delete_group(DEFAULT_GROUP)
        self.assertEqual(library.normalize_group("missing"), DEFAULT_GROUP)
        self.assertEqual(library.tracks("missing"), [])

    def test_existing_playback_modes_work_with_folder_tracks(self):
        root, _ = self.make_library({"Default": ["one.mp3", "two.mp3"]})
        folder = root / "BGM" / "Default"
        for track in ("one.mp3", "two.mp3"):
            (folder / track).write_bytes(b"audio")
        library = MusicLibrary(root / "BGM")
        self.assertEqual(library.choose("Fixed", DEFAULT_GROUP, "one.mp3"), folder / "one.mp3")
        self.assertIn(library.choose("Balanced Random", LIBRARY_SCOPE), library.tracks())
        self.assertIn(library.choose("True Random", LIBRARY_SCOPE), library.tracks())

    def test_flat_tracks_migrate_to_default_and_keep_legacy_membership(self):
        root, _ = self.make_library({"デフォルト": ["legacy.mp3"]})
        bgm = root / "BGM"
        (bgm / "legacy.mp3").write_bytes(b"audio")
        library = MusicLibrary(bgm)
        self.assertTrue((bgm / "Default" / "legacy.mp3").is_file())
        self.assertEqual(library.resolve_track("legacy.mp3"), bgm / "Default" / "legacy.mp3")

    def test_awakening_offsets_default_and_negative_values_are_safe(self):
        root, _ = self.make_library({"Default": ["track.ogg"]})
        track = root / "BGM" / "Default" / "track.ogg"
        track.write_bytes(b"audio")
        library = MusicLibrary(root / "BGM")
        self.assertEqual(library.awakening_offset(track), 0.0)
        library.set_awakening_offset(track, -4.5)
        self.assertEqual(library.awakening_offset(track), 0.0)
        library.set_awakening_offset(track, "3.25")
        self.assertEqual(library.awakening_offset(track), 3.25)

    def test_wav_track_duration_is_available_and_other_formats_are_safe(self):
        root, _ = self.make_library({"Default": ["short.wav", "unknown.ogg"]})
        folder = root / "BGM" / "Default"
        with wave.open(str(folder / "short.wav"), "wb") as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(10)
            audio.writeframes(b"\0\0" * 25)
        (folder / "unknown.ogg").write_bytes(b"not an ogg file")
        library = MusicLibrary(root / "BGM")
        self.assertEqual(library.track_duration(folder / "short.wav"), 2.5)
        self.assertIsNone(library.track_duration(folder / "unknown.ogg"))

    def test_mp3_and_ogg_duration_use_optional_metadata_reader_safely(self):
        metadata = types.ModuleType("mutagen")
        metadata.File = lambda path: types.SimpleNamespace(info=types.SimpleNamespace(length=12.5))
        with patch.dict(sys.modules, {"mutagen": metadata}):
            self.assertEqual(MusicLibrary.track_duration("track.mp3"), 12.5)
            self.assertEqual(MusicLibrary.track_duration("track.ogg"), 12.5)

        corrupt = types.ModuleType("mutagen")
        corrupt.File = lambda path: (_ for _ in ()).throw(ValueError("corrupt"))
        with patch.dict(sys.modules, {"mutagen": corrupt}):
            self.assertIsNone(MusicLibrary.track_duration("corrupt.mp3"))
