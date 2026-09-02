# Starward Custom BGM（非公式 / Unofficial）

『星の翼 / Starward』向けのWindows用カスタムBGMツールです。

ゲーム画面の認識と、任意のゲームログ監視を利用してゲーム状態を判定し、

- ロビー
- マッチ成立
- 戦闘
- 覚醒
- 勝利
- 敗北

などのタイミングに合わせて、ユーザーが用意したBGMを自動で再生・切り替えます。

**ゲーム本体のファイルは変更しません。**

ゲーム画像、認識用テンプレートPNG、音楽ファイルは同梱していません。

> 非公式・非商用のファンメイドツールです。

---

# ダウンロード

最新版は GitHub Releases からダウンロードできます。

**Latest Release: v0.2.0**

https://github.com/wonderfulyamada/Starward-Custom-BGM-Unofficial/releases/latest

通常利用では **Pythonのインストールは不要です。**

1. Releases から `Starward-Custom-BGM-Unofficial-vX.X.X.zip` をダウンロード
2. ZIPを任意の場所に展開
3. `StarwardBGM.exe` を起動

これだけでツール自体は起動できます。

---

# クイックスタート

初回利用時は、以下の順番で設定してください。

1. ReleasesからZIPをダウンロードして展開
2. `BGM/Default/` に好きなBGMを入れる
3. 自分のゲーム画面から認識用テンプレートを用意する
4. `StarwardBGM.exe` を起動
5. 『星の翼』のウィンドウを選択
6. 再生モード、グループ、曲などを設定
7. ゲームを開始する

ロビーBGM・マッチ成立BGMを使用する場合のみ、追加で **ゲームログ監視** の設定が必要です。

---

# BGMの入れ方

展開したフォルダー内の `BGM/` に好きなBGMを配置します。

対応形式：

- `.mp3`
- `.ogg`
- `.wav`

例：

```text
BGM/
├─ Default/
│  ├─ battle01.mp3
│  ├─ battle02.mp3
│  └─ battle03.ogg
│
├─ Anime/
│  ├─ song01.mp3
│  └─ song02.mp3
│
└─ GameMusic/
   ├─ bgm01.mp3
   └─ bgm02.wav
```

`BGM/` 直下のフォルダーが、それぞれ **BGMグループ**として認識されます。

たとえば、

```text
BGM/
├─ Lobby/
├─ Match/
└─ Battle/
```

のように分けておけば、GUIからロビー・マッチ・バトルごとに別のグループを指定できます。

---

# 画像テンプレートの作り方

本ツールでは画面認識のために画像テンプレートを使用します。

著作物をツール側で配布しないため、テンプレート画像は **利用者自身のゲーム画面から作成してください。**

必要なファイル：

```text
templates/
├─ battle_start.png
├─ victory.png
└─ defeat.png
```

## battle_start.png

戦闘開始時に表示される **「GO」** を認識するための画像です。

1. 戦闘開始時の画面をスクリーンショット
2. 「GO」が表示されている部分を切り抜く
3. `battle_start.png` という名前で保存
4. `templates/` に配置

## victory.png

勝利時のリザルト画面を認識するための画像です。

1. 勝利画面をスクリーンショット
2. 勝利表示の認識に使う部分を切り抜く
3. `victory.png` という名前で保存
4. `templates/` に配置

## defeat.png

敗北時のリザルト画面を認識するための画像です。

1. 敗北画面をスクリーンショット
2. 敗北表示の認識に使う部分を切り抜く
3. `defeat.png` という名前で保存
4. `templates/` に配置

追加の説明は、

```text
templates/README.txt
```

も参照してください。

---

# 基本的な使い方

## 1. StarwardBGM.exe を起動

```text
StarwardBGM.exe
```

を起動します。

## 2. 星の翼のウィンドウを選択

GUIから、現在起動している『星の翼 / Starward』のウィンドウを選択してください。

本ツールは選択したウィンドウをキャプチャして画面認識を行います。

## 3. バトルBGMを設定

バトルBGMでは以下の再生モードを利用できます。

### 固定

指定した1曲を使用します。

### 均等ランダム

選択したグループ内から、各曲ができるだけ均等に選ばれるように再生します。

### 完全ランダム

選択したグループ内からランダムで1曲を選びます。

戦闘開始時の画面上の **GO** を検出すると、自動でバトルBGMへ切り替わります。

`FightingState: True` や `Battle-9` などのゲームログだけではバトルBGMを開始しません。

**画面上のGO検出がバトルBGM開始の基準です。**

---

# ロビーBGM

ロビーBGMは任意機能です。

有効にすると、ゲームログからロビー状態を検出した際にBGMを再生します。

対応モード：

- 固定
- 均等ランダム
- 完全ランダム

ロビーBGMはループ再生されます。

選択したグループ内から曲を使用し、曲は必ず **0.0秒から再生**されます。

ロビーBGMを使用するには、後述する **ゲームログ監視**を有効にしてください。

---

# マッチ成立BGM

マッチ成立BGMも任意機能です。

マッチング検索を開始した瞬間ではなく、

**マッチが成立したタイミング**

で再生を開始します。

対応モード：

- 固定
- 均等ランダム
- 完全ランダム

選択したグループ内から曲を使用します。

マッチBGMはロード画面中もそのまま再生され、その後ゲーム画面の **GO** を検出するとバトルBGMへ切り替わります。

曲は必ず **0.0秒から再生**されます。

マッチ成立BGMを使用するには、ゲームログ監視を有効にしてください。

---

# 覚醒BGM

覚醒時だけ別のBGMを流すことができます。

覚醒BGMは **固定曲のみ**です。

ランダム再生には対応していません。

これは、

> 「覚醒した瞬間に、この曲のこの部分を流したい」

という使い方を想定しているためです。

## 開始位置

覚醒BGMには曲ごとに開始位置を設定できます。

例：

```text
13.4秒
```

と設定した場合、覚醒時にその曲の13.4秒地点から再生します。

覚醒終了後は、覚醒前に流れていたバトルBGMへ復帰します。

覚醒BGMを使用する場合は、GUIから覚醒用のゲームパッド入力も設定してください。

---

# 勝利BGM / 敗北BGM

勝利時・敗北時にそれぞれ別のBGMを流すことができます。

どちらも **固定曲のみ**です。

## 勝利BGM

勝利画面を検出すると、設定した曲を1回だけ再生します。

曲ごとに開始位置を設定できます。

例：

```text
41.0秒
```

と設定した場合、41秒地点から再生します。

## 敗北BGM

敗北画面を検出すると、設定した曲を1回だけ再生します。

こちらも曲ごとに開始位置を設定できます。

---

# 各BGM機能一覧

| 状態 | 固定 | 均等ランダム | 完全ランダム | ループ | 開始位置指定 |
|---|:---:|:---:|:---:|:---:|:---:|
| バトル | ○ | ○ | ○ | ○ | - |
| ロビー | ○ | ○ | ○ | ○ | - |
| マッチ成立 | ○ | ○ | ○ | ○ | - |
| 覚醒 | ○ | - | - | ○ | ○ |
| 勝利 | ○ | - | - | - | ○ |
| 敗北 | ○ | - | - | - | ○ |

---

# BGMグループと開始位置

BGMはフォルダー単位でグループ分けできます。

例：

```text
BGM/
├─ Default/
├─ Anime/
├─ Gundam/
└─ GameMusic/
```

ロビー・マッチ・バトルのランダム再生では、**選択したグループ内だけ**から曲が選ばれます。

覚醒・勝利・敗北では、曲ごとに開始位置を保存できます。

設定情報は、

```text
bgm_library.json
```

で管理されます。

ロビー・マッチでは保存済み開始位置を使用せず、必ず曲頭から再生します。

---

# 疑似フェード

BGMの切り替え時には、

1. 現在のBGMをフェードアウト
2. 少し待つ
3. 次のBGMを再生

という方式で、できるだけ自然に聞こえるように切り替えます。

同時に2つの音声を再生する本格的なクロスフェードではありません。

主な流れ：

```text
ロビー
  ↓
マッチ成立
  ↓
バトル
  ↓
覚醒
  ↓
バトル復帰
  ↓
勝利 / 敗北
  ↓
ロビー
```

---

# ゲームログ監視

ロビーBGMとマッチ成立BGMを使用する場合は、ゲームログ監視を有効にしてください。

ゲームログ監視は **任意機能**です。

ゲームログ監視を使用しなくても、画面認識を利用する機能は動作します。

## 設定方法

GUIからゲームログ監視を有効化し、Starwardの **Logsフォルダー**を指定してください。

本ツールはログフォルダーを自動検索しません。

必ずユーザー自身で指定してください。

指定されたフォルダー内の最新の、

```text
Log_*.txt
```

を監視します。

起動時点より前のログを再処理せず、基本的に新しく追記された行だけを処理します。

---

# ゲームログで使用する主な状態

ここは内部仕様寄りの説明です。

## ロビー

```text
StateLobby
```

を検出するとロビー状態として扱います。

## マッチ成立

```text
UpdateMatchDataInGamePush State:Confirmed
```

を検出するとマッチ成立として扱います。

以下ではマッチBGMを開始しません。

```text
State:Matching
State:Confirming
```

また、

```text
FightingState: True
Battle-9
```

はバトル開始に関連する補助情報として検出しますが、これらだけではBGMを変更しません。

バトルBGMは **画面上のGO検出**で開始します。

---

# 一時停止 / 再開

```text
Ctrl + F8
```

で本ツールによるBGM再生を一時停止できます。

もう一度押すと再開します。

---

# よくある質問 / トラブルシューティング

## BGMが一覧に表示されない

以下を確認してください。

- BGMファイルが `BGM/` 内のグループフォルダーに入っている
- 拡張子が `.mp3` / `.ogg` / `.wav`
- ファイル追加後にGUI側の一覧が更新されている

例：

```text
BGM/
└─ Default/
   └─ music.mp3
```

---

## 戦闘BGMが始まらない

以下を確認してください。

- 『星の翼』のウィンドウを正しく選択している
- `templates/battle_start.png` が存在する
- GO表示を正しく切り抜いている
- ゲーム画面の解像度やUI状態がテンプレート作成時と大きく異なっていない

---

## 勝利 / 敗北BGMが動かない

以下を確認してください。

```text
templates/victory.png
templates/defeat.png
```

テンプレートが現在のゲーム画面と合っていない場合は、現在の環境でスクリーンショットを撮り直してください。

---

## ロビーBGMが動かない

以下を確認してください。

- ロビーBGMが有効
- ゲームログ監視が有効
- StarwardのLogsフォルダーが正しく指定されている

---

## マッチBGMが動かない

以下を確認してください。

- マッチBGMが有効
- ゲームログ監視が有効
- StarwardのLogsフォルダーが正しく指定されている

マッチBGMは検索開始時ではなく、**マッチ成立時**に開始します。

---

## Pythonは必要？

通常利用では必要ありません。

Releasesから配布されているZIPをダウンロードして、

```text
StarwardBGM.exe
```

を起動してください。

Pythonが必要なのは、ソースコードから直接実行・開発する場合だけです。

---

## ゲームファイルを変更する？

変更しません。

本ツールは、

- 選択したゲームウィンドウの画面キャプチャ
- 画像認識
- 任意のゲームログ監視
- ユーザーPC上の音楽再生

によって動作します。

---

## 場面ごとにプレイリストを分けられる？

バトル・ロビー・マッチでは可能です。

例えば、

```text
BGM/
├─ Lobby/
├─ Match/
└─ Battle/
```

のようなグループを作成し、

GUIから、

- ロビー用グループ
- マッチ用グループ
- バトル用グループ

をそれぞれ選択できます。

各グループでは、固定・均等ランダム・完全ランダムを利用できます。

覚醒・勝利・敗北は固定曲のみです。

---

# 不具合報告

不具合は [GitHub Issues](../../issues) から受け付けます。サポート対象は原則として最新版のみです。旧バージョンで問題がある場合は、まず最新版で再現するか確認してください。過去バージョンは GitHub Releases から利用できますが、最新版が環境上動作しない場合などを除き、旧版固有の問題には対応できないことがあります。

報告時は、内容を確認したうえで `logs/StarwardBGM.log` を添付してください。このログにはゲームログ本文や個人情報を保存しませんが、確認してから共有してください。

---

# 技術概要 / Technical Overview

本ツールはPythonで開発したWindows向けデスクトップアプリケーションです。

主な構成：

- Python
- 選択ウィンドウのリアルタイムキャプチャ
- 画像認識によるゲーム状態検出
- `Log_*.txt` のリアルタイムtail監視
- ゲームパッド入力監視
- 複数の入力・検出結果を統合する状態管理
- pygame-ceによる音楽再生
- フェードアウト＋遅延開始による疑似BGM遷移
- JSONによる設定保存
- BGMライブラリ管理
- 日本語 / 英語ローカライズ
- PyInstallerによるWindows向けポータブル配布
- pytestによる自動回帰テスト

現在の自動回帰テスト：

```text
108 tests
```

---

# 開発者向け

ここから下は通常利用には必要ありません。

## ソースから実行

```powershell
py -m pip install -r requirements.txt
py main.py --gui
```

デバッグ実行：

```powershell
py main.py --gui --debug
```

## ポータブル版ビルド

```powershell
.\build_portable.ps1
```

ビルドにはPython・PyInstallerなどの開発環境が必要です。

---

# 公開配布について

公式サポートへ、本ツールの方式について確認を行っています。

ゲーム本体のファイルを変更せず、利用・配布が非商用であるという説明済みの方式であれば、公開・配布可能との回答を受けています。

確認対象には、

- ゲーム画面のキャプチャ
- 画像認識による状態判定
- `Log_*.txt` のリアルタイム監視によるゲーム状態判定

が含まれています。

ただし、これは、

- 公式推奨
- 公式認証
- 公式との提携
- 将来のあらゆる実装への包括的許可

を意味するものではありません。

本プロジェクトは **非公式・独立・非商用**のファンメイドツールです。

---

# ライセンス

詳細は、

```text
LICENSE
```

を確認してください。

本プロジェクト独自のライセンス条件が適用されます。

---

# English

## About

Starward Custom BGM is an unofficial Windows tool for 『星の翼 / Starward』.

It detects game states using screen recognition and optional game-log monitoring, then automatically plays user-provided BGM for contexts such as:

- Lobby
- Match Confirmed
- Battle
- Awakening
- Victory
- Defeat

The tool **does not modify game files**.

Game images, recognition templates, and music files are not bundled.

This project is unofficial and non-commercial.

---

## Download

Download the latest portable release here:

https://github.com/wonderfulyamada/Starward-Custom-BGM-Unofficial/releases/latest

Normal users do **not** need Python.

Download the ZIP, extract it, and launch:

```text
StarwardBGM.exe
```

---

## Quick Start

1. Download and extract the latest ZIP.
2. Put your music files in `BGM/Default/`.
3. Create your own screen-recognition templates.
4. Put them in `templates/`.
5. Launch `StarwardBGM.exe`.
6. Select the Starward game window.
7. Configure your BGM settings.
8. Start playing.

Supported audio formats:

- `.mp3`
- `.ogg`
- `.wav`

---

## Recognition Templates

Create the following files from screenshots of your own game:

```text
templates/
├─ battle_start.png
├─ victory.png
└─ defeat.png
```

- `battle_start.png`: battle-start GO display
- `victory.png`: victory result
- `defeat.png`: defeat result

See:

```text
templates/README.txt
```

for additional information.

---

## BGM Groups

Each direct child folder under `BGM/` is treated as a group.

Example:

```text
BGM/
├─ Default/
├─ Anime/
└─ GameMusic/
```

Battle, Lobby, and Match support:

- Fixed
- Balanced Random
- True Random

Random playback always stays inside the selected group.

Lobby and Match always start tracks from `0.0`.

Awakening, Victory, and Defeat use fixed tracks and can use saved per-track start offsets.

---

## Context BGM

| Context | Fixed | Balanced Random | True Random | Loop | Start Offset |
|---|:---:|:---:|:---:|:---:|:---:|
| Battle | Yes | Yes | Yes | Yes | - |
| Lobby | Yes | Yes | Yes | Yes | - |
| Match | Yes | Yes | Yes | Yes | - |
| Awakening | Yes | - | - | Yes | Yes |
| Victory | Yes | - | - | - | Yes |
| Defeat | Yes | - | - | - | Yes |

Battle BGM starts only when the on-screen GO is detected.

Match BGM starts when matchmaking is confirmed and continues through loading until GO transitions playback to Battle BGM.

Awakening BGM resumes the previous Battle BGM when Awakening ends.

Victory and Defeat are one-shot cues.

---

## Game Log Monitoring

Game-log monitoring is optional and manually configured.

It is required only for Lobby and Match BGM.

Select the Starward Logs folder in the GUI.

The tool does not automatically guess the log path.

If log monitoring is disabled or invalid, screen-based features continue to work normally.

The newest:

```text
Log_*.txt
```

is monitored for newly appended lines.

---

## Pause / Resume

Use:

```text
Ctrl + F8
```

to pause or resume custom BGM playback.

---

## Troubleshooting

### Battle BGM does not start

Check:

- the correct game window is selected
- `battle_start.png` exists
- the GO template matches your current game screen

### Lobby / Match BGM does not work

Check:

- the feature is enabled
- game-log monitoring is enabled
- the correct Logs folder is selected

### Victory / Defeat is not detected

Recreate:

```text
victory.png
defeat.png
```

from your current game screen.

### Music does not appear

Check that the file is inside a direct `BGM/` group and uses:

- `.mp3`
- `.ogg`
- `.wav`

---

## Bug Reports

Please report bugs through [GitHub Issues](../../issues). Support is generally limited to the latest release; if an issue occurs on an older release, please reproduce it on the latest version first. Older releases remain available from GitHub Releases, but issues specific to an older release may not be supported unless the current release cannot run in the affected environment.

When reporting, review and attach `logs/StarwardBGM.log` if possible. It contains diagnostic events only, not raw game-log lines or personal information, but please check it before sharing.

---

## Technical Overview

- Python Windows desktop application
- selected-window capture and screen recognition
- real-time game-log tail monitoring
- gamepad input
- state-machine-based event handling
- pygame-ce audio playback
- pseudo-fade handoffs
- JSON configuration and BGM library metadata
- Japanese / English localization
- PyInstaller portable distribution
- pytest regression suite

Current automated regression suite:

```text
108 tests
```

---

## Development

```powershell
py -m pip install -r requirements.txt
py main.py --gui
.\build_portable.ps1
```

---

## Public Distribution / Support Confirmation

Official support confirmed public distribution under the described approach provided that:

- game files are not modified
- use and distribution remain non-commercial

The confirmation covered both:

- screen capture / image recognition
- real-time `Log_*.txt` monitoring for game-state detection

This does not represent official endorsement, partnership, certification, or blanket permission for unrelated future implementations.

The project remains unofficial, independent, and non-commercial.
