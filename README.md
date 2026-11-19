# trackmate-spotiflow-analysis

TrackMate（Spotiflow で検出）の XML と元の動画から、track ごとの MSD と拡散係数を計算し、動画に軌跡を重ねた GIF を作るツールです。XML と動画をブラウザの画面に入れるだけで、結果が出ます。

## TrackMate の XML を作る

XML は、Fiji の TrackMate の GUI で作っても、このリポジトリのマクロ [`scripts/fiji/spotiflow_trackmate.groovy`](scripts/fiji/spotiflow_trackmate.groovy) で作っても構いません。マクロを使うと、毎回同じ設定で TrackMate を実行できます。

1. Fiji に TrackMate 8 と TrackMate-Spotiflow（update site `TrackMate-Spotiflow`）を入れ、Spotiflow の conda 環境を用意しておきます。
2. **[マクロをダウンロード（spotiflow_trackmate.groovy）](https://github.com/jk12358/trackmate-spotiflow-analysis-public/releases/latest/download/spotiflow_trackmate.groovy)** をクリックすると、最新版のファイルが保存されます。保存したファイルを Fiji のウィンドウにドラッグ＆ドロップすると、Script Editor で開きます。前の版は [Releases](https://github.com/jk12358/trackmate-spotiflow-analysis-public/releases) にあります。
3. Run を押し、動画、出力先のフォルダ、Spotiflow のモデル、Linking max distance、Gap-closing max distance、Max frame gap を入れて OK を押します。距離は動画の空間の単位で読まれます（校正がなければ pixel、あれば µm など）。
4. 出力先にできた `trackmate_<日時>` のフォルダの `<動画名>.xml` を、下のアプリに入れます。

マクロの版は XML の Log と `batch_log.txt` に記録されます。詳しい使い方と、GUI との違いは [`docs/fiji-macro.md`](docs/fiji-macro.md) にあります。

## アプリの使い方

### 1. アプリを開く

次のどちらかで開きます。

- 研究室で共有している URL をブラウザで開きます。インストールは要りません。
- 自分の PC（Windows）で使うときは、このリポジトリを ZIP でダウンロードして展開し、`launchers` フォルダの `解析アプリを起動.bat` をダブルクリックします（中で同じフォルダの `start_app.ps1` を動かします）。初回は準備に数分かかり、そのあとブラウザでアプリが開きます。使い終わったら黒い画面を閉じます。大きな動画を扱うときや、ネットにつながらないときはこちらを使ってください。

### 2. ファイルを入れる

TrackMate で保存した XML と、元の動画（AVI、TIFF、STK など）を、画面の枠にまとめてドラッグ＆ドロップします。何組でも入れられます。

- XML には、TrackMate で開いた元の動画の名前が記録されています。その名前の動画があれば、それと組にします。
- 記録された名前の動画がないときは、ファイル名（拡張子を除く）が XML と同じ動画と組にします。例: `cell01.xml` と `cell01.avi`。このとき、記録された名前と違うことをお知らせで伝えます。
- どちらの動画もないときは、記録された元の動画の名前をお知らせで伝えます。TrackMate の capture の動画（track を描き込んだ動画）は元の動画ではないので、組にしません。
- 動画がなくても解析できます。そのときは GIF を作らず、拡散係数と図だけを出します。

入れると、XML と動画の組み合わせの一覧が出ます。組み合わせが合っているかを確かめてください。一覧には、XML に記録された TrackMate の設定（spot と track の数、Spotiflow のモデル、linking と gap closing の距離）も出ます。XML によって設定が違うときは、お知らせが出ます。

### 3. 解析する

「解析を始める」を押します。終わると、要約の表、全動画を並べた図、動画ごとの GIF と図が画面に出ます。

解析条件（frame interval、pixel size など）には、研究室の標準の値が入っています。撮影条件が違う動画のときだけ、画面の左の「解析条件」で変えてください。XML に記録された値が設定と違うときは、お知らせが出ます。

### 4. 結果を保存する

「結果をまとめてダウンロード（ZIP）」で保存します。ZIP を展開して `report.html` を開くと、画面と同じ内容をあとから見られます。CSV は Excel で開けます。

別のデータを解析するときは、結果の下の「新しい解析を始める」を押します。入れたファイルと結果が消えて、最初の画面に戻ります。左の解析条件はそのまま残ります。

出力されるファイルの一覧と列の意味は [`docs/output-format.md`](docs/output-format.md)、計算の方法は [`docs/analysis-rules.md`](docs/analysis-rules.md) にあります。

## 困ったとき

- 「対応する動画が見つかりません」と出たときは、XML と動画のファイル名を同じにしてから入れ直してください。
- 「拡散係数を計算できた track が 0 本でした」と出たときは、track が短すぎる可能性があります。標準では 30 spot 未満の track は計算しません。結果の `track_results.csv` の `status` を見てください。
- 「予期しないエラー」と出たときは、入れたファイルと一緒に開発者に知らせてください。
