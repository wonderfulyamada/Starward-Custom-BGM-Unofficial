# Changelog

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
