# Starward Custom BGM（非公式 / Unofficial）

『星の翼 / Starward』の選択したウィンドウをキャプチャし、画面認識と任意のゲームログ監視から状態を検出して、ユーザーが用意したBGMを再生するWindows向けツールです。ゲーム画像、テンプレートPNG、音楽ファイルは同梱していません。

This unofficial Windows tool captures a selected Starward window and plays user-provided BGM using screen recognition and optional game-log monitoring. Game images, template PNGs, and music are not bundled.

## 日本語

### 機能

- ウィンドウ選択／画面キャプチャ。バトルBGMは画面上の **GO** 検出だけで開始します。
- バトルBGM: 固定、均等ランダム、完全ランダム。音量調整に対応します。
- ロビーBGM（任意）: `StateLobby` で開始してループ再生。選択グループ内の固定／均等ランダム／完全ランダムに対応し、常に `0.0` 秒から開始します。
- マッチ成立BGM（任意）: `UpdateMatchDataInGamePush State:Confirmed` だけで開始してループ再生。`Matching` / `Confirming` では開始しません。`FightingState: True` / `Battle-9` は音声を変更しないヒントです。ロード中も継続し、画面GOでバトルBGMへ移ります。選択グループ内の3モードに対応し、常に `0.0` 秒から開始します。
- 覚醒BGM（任意）: 固定曲のみ。曲ごとの開始位置を使用し、終了後は保存した位置からバトルBGMへ復帰します。
- 勝利／敗北BGM（任意）: 固定曲のみ。曲ごとの開始位置からワンショット再生します。
- 疑似フェード: 現在曲をフェードアウトし、次の曲を遅延開始します（同時2ストリーム再生ではありません）。
- `Ctrl+F8` 一時停止／再開、日本語／英語UI、ポータブル実行形式。

### BGMグループとメタデータ

`BGM/Default/` のような `BGM/` 直下のグループへ `.mp3`、`.ogg`、`.wav` を配置します。ロビー／マッチのランダム選曲は必ず選択グループ内です。中央の `bgm_library.json` が所属、履歴、曲ごとの開始位置を管理します。ロビー／マッチは保存済み開始位置を使わず、覚醒／勝利／敗北は固定曲の保存済み開始位置を使います。

### ゲームログ監視

ログ監視は任意かつ手動設定です。GUIで有効化し、Starward Logsフォルダーを指定します。自動検索はしません。ロビー／マッチ機能にのみ必要で、無効またはパス不正でもGOを含む画面認識機能は通常どおり動作します。最新の `Log_*.txt` に末尾から接続し、新しい追記行だけを処理します。

### テンプレート・実行・ビルド

利用者自身の画面から `battle_start.png`、`victory.png`、`defeat.png` を作成し `templates/` に置いてください。詳細は `templates/README.txt` を参照してください。

```powershell
py -m pip install -r requirements.txt
py main.py --gui
.\build_portable.ps1
```

### 公開配布について

公式サポートから、ゲームファイルを変更せず、利用・配布が非商用であるという説明済みの方式であれば公開配布可能との回答を受けています。この条件下で、画面キャプチャ／画像認識と、ゲーム状態検出のための `Log_*.txt` リアルタイム監視の両方が確認対象です。

これは公式推奨、提携、認証、または無関係な将来実装への包括的許可ではありません。本プロジェクトは非公式・独立のツールです。

## English

### Features

- Select a visible window for capture. Battle BGM starts **only** on screen GO detection.
- Battle BGM supports Fixed, Balanced Random, and True Random, plus volume control.
- Optional Lobby BGM starts on `StateLobby`, loops, supports all three modes within its selected group, and always starts at `0.0`.
- Optional Match Confirmed BGM starts only on `UpdateMatchDataInGamePush State:Confirmed` and loops. `Matching` / `Confirming` do not start it; `FightingState: True` / `Battle-9` are non-audio hints. It continues through loading until screen GO transitions to Battle BGM. Its three modes stay within the selected group and start at `0.0`.
- Optional Awakening BGM is fixed-track only, uses a per-track offset, and resumes the saved Battle BGM afterward.
- Optional Victory/Defeat BGM are fixed-track, one-shot cues using per-track offsets.
- Pseudo fades use fadeout plus a delayed handoff, without dual-stream mixing.
- `Ctrl+F8` pause/resume, JA/EN UI, and portable builds.

### Groups, metadata, and logs

Place `.mp3`, `.ogg`, or `.wav` files in direct groups such as `BGM/Default/`. Lobby/Match random modes never leave their selected group. Central `bgm_library.json` stores membership, history, and per-track offsets. Lobby/Match ignore stored offsets; Awakening/Victory/Defeat use them.

Game-log monitoring is optional and manually configured in the GUI; no path is guessed. It is required only for Lobby/Match. A disabled monitor or invalid path does not disable screen-based features. The newest `Log_*.txt` is attached at EOF and only appended lines are processed.

Create `battle_start.png`, `victory.png`, and `defeat.png` from your own game screen under `templates/`.

```powershell
py -m pip install -r requirements.txt
py main.py --gui
.\build_portable.ps1
```

### Public distribution and support confirmation

Official support confirmed public distribution under the described approach provided game files are not modified and use/distribution is non-commercial. The confirmation covered screen capture/image recognition and real-time `Log_*.txt` monitoring for game-state detection.

This is not an official endorsement, partnership, certification, or blanket permission for unrelated future implementations. The project remains unofficial and independent.
