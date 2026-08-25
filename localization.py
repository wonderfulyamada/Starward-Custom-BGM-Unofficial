"""GUI display strings; add a language by adding one dictionary."""
LANGUAGES = {"en": "English", "ja": "日本語"}

STRINGS = {
    "en": {
        "window": "Window", "refresh": "Refresh", "language": "Language",
        "playback_mode": "Playback mode", "playback_scope": "Playback scope", "group": "Group",
        "fixed_track": "Fixed track", "volume": "Volume", "fadeout": "Fade-out (ms)",
        "result_bgm_enabled": "Enable Result BGM (experimental)", "victory_bgm_group": "Victory BGM group", "victory_bgm_track": "Victory BGM track", "defeat_bgm_group": "Defeat BGM group", "defeat_bgm_track": "Defeat BGM track",
        "awakening_bgm_enabled": "Enable Awakening BGM (experimental)", "awakening_bgm_group": "Awakening BGM group (experimental)",
        "awakening_bgm_track": "Awakening track", "awakening_start_offset": "Awakening start offset (seconds)", "preview": "Preview", "stop_preview": "Stop Preview",
        "awakening_crossfade": "Awakening crossfade (ms)",
        "victory_start_offset": "Victory start offset (seconds)", "defeat_start_offset": "Defeat start offset (seconds)",
        "lobby_bgm": "Lobby BGM", "match_bgm": "Match Confirmed BGM", "lobby_bgm_group": "Lobby BGM group", "lobby_bgm_track": "Lobby BGM track", "match_bgm_group": "Match BGM group", "match_bgm_track": "Match BGM track",
        "gamepad_input_assist_enabled": "Enable gamepad Awakening input assist", "gamepad_binding": "Awakening gamepad buttons", "register_gamepad": "Add Button", "remove_gamepad": "Remove", "clear_gamepad": "Clear All", "gamepad_unbound": "Not registered", "gamepad_registering": "Press one button now…", "gamepad_preview": "Input preview",
        "game_log_monitor_enabled": "Enable game log monitoring",
        "game_log_folder": "Game log folder", "browse": "Browse",
        "game_log_folder_error": "Game log monitoring", "game_log_folder_invalid": "Game log monitoring is enabled, but the selected log folder is empty or invalid. Screen recognition will continue without log monitoring.",
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
        "result_bgm_enabled": "リザルトBGMを有効化（実験的機能）", "victory_bgm_group": "勝利BGMグループ", "victory_bgm_track": "勝利BGM曲", "defeat_bgm_group": "敗北BGMグループ", "defeat_bgm_track": "敗北BGM曲",
        "awakening_bgm_enabled": "覚醒BGMを有効化（実験的機能）", "awakening_bgm_group": "覚醒BGMグループ（実験的機能）",
        "awakening_bgm_track": "覚醒曲", "awakening_start_offset": "覚醒開始位置（秒）", "preview": "試聴", "stop_preview": "試聴を停止",
        "awakening_crossfade": "覚醒クロスフェード（ms）",
        "victory_start_offset": "勝利開始位置（秒）", "defeat_start_offset": "敗北開始位置（秒）",
        "lobby_bgm": "ロビーBGM", "match_bgm": "マッチ成立BGM", "lobby_bgm_group": "ロビーBGMグループ", "lobby_bgm_track": "ロビーBGM曲", "match_bgm_group": "マッチ成立BGMグループ", "match_bgm_track": "マッチ成立BGM曲",
        "gamepad_input_assist_enabled": "ゲームパッド覚醒入力補助を有効化", "gamepad_binding": "覚醒ゲームパッドボタン", "register_gamepad": "ボタン追加", "remove_gamepad": "削除", "clear_gamepad": "全クリア", "gamepad_unbound": "未登録", "gamepad_registering": "登録するボタンを1つ押してください…", "gamepad_preview": "入力プレビュー",
        "game_log_monitor_enabled": "ゲームログ監視を有効化",
        "game_log_folder": "ゲームログフォルダー", "browse": "参照",
        "game_log_folder_error": "ゲームログ監視", "game_log_folder_invalid": "ゲームログ監視は有効ですが、ログフォルダーが空か無効です。ログ監視なしで画面認識を継続します。",
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
