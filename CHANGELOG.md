# Changelog

## v0.2.2 - 2026-09-04

- 非アクティブ時を含むゲームパッド入力処理を見直し、pygame / SDL の入力監視を単一スレッドへ集約。
- 複数ゲームパッドの入力処理、コントローラー差し替え検知、device add/remove 時の再列挙を改善。
- 一時的な pygame / SDL エラーから、100ms バックオフ後に監視を自動復旧するよう改善。
- pygame event queue を監視スレッドで一元取得・排出し、入力元コントローラー情報を診断ログへ追加。
- 覚醒ボタン登録時、短いボタン入力を取りこぼす問題を修正。
- 登録開始前から押されているボタンを誤登録しないよう改善。
- 低解像度 / 高DPI環境向けにGUI縦スクロールを追加。
- マウスホイールで設定画面をスクロール可能に改善。

## v0.2.1 - 2026-09-02

- 複数ゲームパッド接続時の入力処理を改善。
- Detectorが非アクティブでもゲームパッド入力を取得できるよう改善。
- 診断ログ `logs/StarwardBGM.log` を追加。
- `battle_start` / `victory` / `defeat` の個別しきい値調整を追加。
- 画像認識の現在一致率表示を追加。
- 不具合調査用の診断情報を追加。
- READMEの不具合報告・サポート案内を改善。

## v0.2.0 - 2026-08-25

- Added optional Lobby and Match Confirmed BGM using manually configured game-log monitoring.
- Added Fixed, Balanced Random, and True Random modes within selected Lobby/Match groups.
- Added contextual groups for Battle, Lobby, Match, Awakening, Victory, and Defeat.
- Added Awakening and one-shot Victory/Defeat cues with per-track fixed-cue offsets.
- Added cancelable pseudo-fade handoffs and JA/EN UI updates.
- Improved Result audio lifecycle, GO-only battle timing, log rotation/truncation handling, and Awakening HUD/glow stability.
