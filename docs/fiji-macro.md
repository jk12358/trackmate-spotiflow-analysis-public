# Fiji で TrackMate-Spotiflow を実行するマクロ

[`scripts/fiji/spotiflow_trackmate.groovy`](../scripts/fiji/spotiflow_trackmate.groovy) は、Fiji の TrackMate を Spotiflow の検出器で動かし、XML を保存する Groovy のマクロです。GUI で毎回同じ設定を選ぶ代わりに使います。保存した XML は、そのままこのツールのアプリに入れられます。

## 使い方

1. 最初の 1 回だけ、次の準備をします。
   - Fiji の Help > Update... > Manage update sites で、`TrackMate-Spotiflow` にチェックを入れて更新し、Fiji を再起動します。
   - conda で Spotiflow の環境を作ります。環境の名前は、マクロの初期値に合わせて `spotiflow` にしておくと、設定画面で変えずに済みます。Spotiflow の入れ方は [Spotiflow のページ](https://github.com/weigertlab/spotiflow) にあります。
2. Fiji の File > New > Script を開き、言語を Groovy にして、マクロのファイルを開きます。
3. Run を押すと、設定の画面が出ます。次の項目を入れて OK を押します。
   - 入力動画ファイル（AVI、TIFF、STK）と、XML の出力先フォルダ
   - Spotiflow モデルと、Spotiflow の conda 環境名
   - Tracker、Linking max distance、Gap-closing max distance、Max frame gap（距離の単位は下の「距離の単位」を見てください）
   - 並列スレッド数、軌跡付き AVI を保存するか、AVI 再生 FPS（並列スレッド数と FPS は、ふつうは初期値のままで構いません）
4. 出力先のフォルダの中に `trackmate_<日時>` のフォルダができ、次のファイルが入ります。

| ファイル | 中身 |
|---|---|
| `<動画名>.xml` | TrackMate の結果。アプリに入れるのはこのファイル |
| `<動画名>_tracks.avi` | 軌跡を描き込んだ動画（「軌跡付きAVIを保存」を選んだときだけ） |
| `batch_log.txt` | マクロの版と、spot と track の数 |

軌跡付きの AVI は Fiji の画面を使って描くので、画面のない環境（サーバーなど）では作れません。その場合は「軌跡付きAVIを保存」を外してください。

## 距離の単位

Linking max distance と Gap-closing max distance は、動画の空間の単位で読まれます。

- 動画に校正がない（pixel の大きさが記録されていない）ときは、pixel です。
- 校正がある（例: 1 pixel = 0.1667 µm）ときは、µm などの単位です。このとき 5 を入れると、5 pixel ではなく 5 µm（約 30 pixel）になります。

マクロは、実行したときの単位を、Fiji の Log には `距離の単位: pixel`、XML の Log には `distanceUnit=pixel` のように書きます。初めての種類の動画で使うときは、この単位を確かめてください。アプリの「XML に記録された TrackMate の設定」の表にも、単位つきで出ます。

## GUI との違い

研究室の動画 2 本（どちらも校正なし）を、GUI と同じ設定（general、linking 5 pixel、gap closing 10 pixel / 5 フレーム）で実行しました。spot、link、track、拡散係数は、2 本ともすべて GUI と一致しました（v0.0.1 の前の版で確認）。

違いは次の 2 点です。

- **initial filter（quality の下限）:** マクロは 0（TrackMate の初期値）にします。GUI は、前回 GUI で使った値（`~/.trackmate/lastusedsettings.xml` に保存されたもの）を引き継ぎます。quality は Spotiflow が出す確率で、Spotiflow はモデルごとのしきい値より低い点を出しません。上の 2 本の動画では、general でも fluo_live でも、quality の最小は 0.5 でした。この場合、下限が 0.5 未満なら結果は同じです。GUI で実行するときは、Initial thresholding の画面で `Selected spots: N out of N` の 2 つの数が同じかを確かめてください。
- **spot filter と track filter:** マクロは何もかけません。GUI でフィルタをかけた場合は、結果が違います。

マクロは `lastusedsettings.xml` を読み書きしません。マクロを実行しても、GUI の前回の値は変わりません。

## 版

マクロの版は、ファイルの中の `MACRO_VERSION` に書いてあります。XML の Log、`batch_log.txt`、Fiji の Log の画面に、`spotiflow_trackmate.groovy v0.0.2` のように記録されます。XML をテキストエディタで開き、先頭近くの `<Log>` を見れば、どの版で出したかが分かります。

結果が変わりうる変更（設定の値、使う検出器や tracker、出力の形）をしたときは版を上げ、下の履歴に書きます。

| 版 | 日付 | 変更 |
|---|---|---|
| 0.0.1 | 2026-11-18 | 研究室で使っていたマクロ（`Spotiflow_Single_with_AVI_14fps.groovy`）をもとに作った最初の版。initial filter の下限を 0.4347727… から 0 に変え、版を XML の Log と `batch_log.txt` に記録するようにした。2D では使えない 3D 用のモデル（synth_3d、smfish_3d）を選択肢から外した |
| 0.0.2 | 2026-11-19 | 距離の単位を設定画面と Log に出すようにした。入力ファイルや出力先が空のときに日本語の案内を出し、失敗したときはエラーの詳細を Log に出すようにした。拡張子を確かめてから結果フォルダを作るようにした。spot と track の結果は 0.0.1 と変わらない見込み |
