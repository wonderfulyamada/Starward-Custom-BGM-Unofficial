"""GUI display strings; add a language by adding one dictionary."""
LANGUAGES = {"en": "English", "ja": "日本語"}

STRINGS = {
    "en": {
        "window": "Window", "refresh": "Refresh", "language": "Language",
        "playback_mode": "Playback mode", "playback_scope": "Playback scope", "group": "Group",
        "fixed_track": "Fixed track", "volume": "Volume", "fadeout": "Fade-out (ms)",
        "start": "Start", "stop": "Stop", "runtime_status": "Monitoring status:", "detection_state": "Detection state:",
        "new": "New", "rename": "Rename", "delete": "Delete", "add": "Add", "remove": "Remove",
        "fixed": "Fixed", "balanced": "Balanced Random", "true_random": "True Random",
        "all_bgm": "All BGM", "selected_group": "Selected Group",
        "idle": "IDLE", "battle": "BATTLE", "awakening": "AWAKENING", "result": "RESULT",
        "running": "Running", "paused": "Paused", "stopped": "Stopped", "new_group": "New group", "group_name": "Group name:",
        "rename_group": "Rename group", "new_group_name": "New group name:", "group_error": "Group",
        "window_error": "Window", "choose_window": "Choose a visible window.",
        "template_warning": "Templates", "template_missing": "Add battle_start.png, victory.png, and defeat.png to the templates folder.",
    },
    "ja": {
        "window": "ウィンドウ", "refresh": "更新", "language": "言語",
        "playback_mode": "再生モード", "playback_scope": "再生範囲", "group": "グループ",
        "fixed_track": "固定曲", "volume": "音量", "fadeout": "フェードアウト (ms)",
        "start": "開始", "stop": "停止", "runtime_status": "監視状態:", "detection_state": "検出状態:",
        "new": "新規", "rename": "名前変更", "delete": "削除", "add": "追加", "remove": "削除",
        "fixed": "固定", "balanced": "均等ランダム", "true_random": "完全ランダム",
        "all_bgm": "全BGM", "selected_group": "選択グループ",
        "idle": "待機", "battle": "バトル", "awakening": "覚醒", "result": "結果",
        "running": "監視中", "paused": "一時停止", "stopped": "停止中", "new_group": "グループ作成", "group_name": "グループ名:",
        "rename_group": "グループ名変更", "new_group_name": "新しいグループ名:", "group_error": "グループ",
        "window_error": "ウィンドウ", "choose_window": "表示中のウィンドウを選択してください。",
        "template_warning": "テンプレート", "template_missing": "templates フォルダーに battle_start.png、victory.png、defeat.png を追加してください。",
    },
}


def text(language, key):
    return STRINGS.get(language, STRINGS["en"]).get(key, STRINGS["en"][key])
