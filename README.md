# Starward BGM Detector

Windows用のデスクトップツールです。選択したゲームウィンドウを監視し、戦闘開始・覚醒・リザルトなどの画面状態を検出します。現在のリリースでは、戦闘開始時に設定したBGMを再生します。

This Windows desktop tool monitors a selected game window and detects events such as battle start, awakening, and results. In the current release, it plays your configured BGM at battle start.

ゲーム画像、テンプレートPNG、音楽ファイルは同梱していません。利用者自身が用意してください。

No game images, template PNGs, or music files are bundled. You must provide your own.

## 日本語

### 対応環境とポータブル版

Windowsで使用できます。配布されたポータブル版は展開後、`StarwardBGM.exe` を起動してください。インストールは不要です。

起動後、`更新` を押して表示中のゲームウィンドウを一覧に出し、対象ウィンドウを選択して `開始` を押します。監視状態は「停止中」「監視中」「一時停止」として表示され、検出状態（`IDLE` / `BATTLE` / `AWAKENING` / `RESULT`）とは別に表示されます。`Ctrl+F8` で一時停止・再開できます。

### BGMの設定

自分で用意した `.mp3`、`.ogg`、または `.wav` ファイルを、ポータブル版の `BGM/` フォルダーに置いてください。

- **Fixed**: 指定した1曲を戦闘開始時に再生します。
- **Balanced Random**: 再生履歴を考慮して曲を選びます。
- **True Random**: 候補から完全にランダムに曲を選びます。

グループと曲の所属は `bgm_library.json` で管理されます。GUIから全BGMまたは選択グループを指定でき、音量とリザルト時のフェードアウト時間も調整できます。監視中の再生設定変更は現在の曲を止めず、次の `BATTLE_START` から反映されます。

### 今後の予定

覚醒状態の検出は内部的に行われますが、現在のリリースでは覚醒専用BGMへの切り替えは利用できません。覚醒BGMの切り替えは今後の機能です。

### テンプレートPNG

検出を開始するには、利用者自身のゲーム画面から作成した次のPNGを `templates/` に配置してください。

- `battle_start.png`
- `victory.png`
- `defeat.png`

テンプレートはゲームアセットとして同梱されません。詳しくは `templates/README.txt` を参照してください。

### ソースから実行・ビルド

Python 3.13以降を用意してから、依存関係をインストールしてGUIを起動します。

```powershell
py -m pip install -r requirements.txt
py main.py --gui
```

ポータブル版を作るには、Tkが利用できるPythonを指定して次を実行します。

```powershell
.\build_portable.ps1
```

## English

### Platform and portable release

The tool supports Windows. For a portable release, extract it and run `StarwardBGM.exe`; no installation is required.

Click **Refresh**, choose a visible game window, then click **Start**. Monitoring status—**Stopped**, **Running**, or **Paused**—is shown separately from the detection state: `IDLE`, `BATTLE`, `AWAKENING`, or `RESULT`. Press `Ctrl+F8` to pause or resume monitoring.

### BGM setup

Put your own `.mp3`, `.ogg`, or `.wav` files in the portable `BGM/` folder.

- **Fixed** plays the selected track at battle start.
- **Balanced Random** selects tracks using playback history.
- **True Random** selects uniformly at random from the available tracks.

Groups and membership are stored in `bgm_library.json`. Use the GUI to select all BGM or one group, and to adjust volume and result fade-out time. Playback-setting changes while monitoring take effect at the next `BATTLE_START` without interrupting the current track.

### Planned / Future

Awakening state detection exists internally, but awakening-specific music switching is not available in the current release. Awakening BGM switching is planned for a future release.

### Template PNG files

Before detection can start, provide your own game-screen PNG files in `templates/` with these names:

- `battle_start.png`
- `victory.png`
- `defeat.png`

These templates are not bundled as game assets. See `templates/README.txt` for details.

### Run and build from source

Install Python 3.13 or later and the dependencies, then launch the GUI:

```powershell
py -m pip install -r requirements.txt
py main.py --gui
```

Build the portable release with a Tk-capable Python installation:

```powershell
.\build_portable.ps1
```
