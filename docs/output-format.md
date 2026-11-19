# 出力の仕様

1 回の実行で、次のフォルダができる。動画の名前は XML のファイル名（拡張子を除く）になる。

```text
<結果フォルダ>/
├── summary_all_movies.csv          全動画の要約（1 動画 1 行）
├── track_results_all_movies.csv    全動画の track ごとの結果
├── figures/
│   ├── diffusion_strip_plot_log_all_movies.png        動画ごとの D のジッタープロット（対数軸）
│   └── diffusion_cumulative_distribution_all_movies.png  動画ごとの D の累積分布
├── report.html                     すべての結果を 1 ページにまとめたもの（ブラウザで開く）
├── messages.txt                    対応付けの結果、警告、エラー（日本語）
├── metadata.yaml                   再現情報
├── error_log.txt                   予期しないエラーが起きたときだけ。開発者に送る
└── movies/
    └── <動画の名前>/
        ├── summary.csv
        ├── track_results.csv
        ├── msd_points.csv
        ├── squared_displacements.csv
        ├── figures/
        │   ├── diffusion_cumulative_distribution.png
        │   ├── diffusion_strip_plot_log.png
        │   ├── squared_displacements_all_tracks.png
        │   └── squared_displacements_by_track/track_<TRACK_ID>.png
        ├── all_tracks.gif               動画があるときだけ
        └── fitted_tracks_with_d.gif     動画があるときだけ
```

拡散係数を計算できた track が 0 本の動画では、CSV だけを出し、図と GIF は出さない。

ジッタープロットは対数軸なので、D が 0 以下の track は描かない。図の `n=` は描いた track の数で、`fitted_track_count` より少ないことがある。要約の値（平均・中央値など）には、D が 0 以下の track も含む。

`report.html` は、要約の表、全動画の図、動画ごとの GIF と図、お知らせ、解析条件を 1 ページに並べる。画像は相対パスで参照するので、結果のフォルダ（ZIP を展開したもの）の中で開く。

## CSV の列

### summary.csv・summary_all_movies.csv

| 列 | 内容 |
|---|---|
| `movie_name` | 動画の名前 |
| `xml_file` | XML のファイル名 |
| `track_count` | 対象の track の数（標準では TrackMate の filter を通った track） |
| `analyzed_track_count` | spot の座標を読めた track の数 |
| `fitted_track_count` | 拡散係数を計算できた track の数 |
| `immobile_track_count` | そのうち immobile の数 |
| `immobile_fraction` | immobile の割合 |
| `mean_/median_/q1_/q3_diffusion_coefficient_um2_s` | D の平均・中央値・第 1 四分位・第 3 四分位（um²/s） |
| `trackmate_version` | XML を作った TrackMate の版 |
| `trackmate_detector`, `trackmate_spotiflow_model` | 検出器の名前と、Spotiflow の学習済みモデル（`general` など） |
| `trackmate_quality_threshold` | TrackMate の最初の quality のしきい値。Spotiflow が自分で決めたしきい値は XML に残らない |
| `trackmate_spatial_units` | XML の座標の単位（`pixel` か `micron`）。下の 2 つの距離もこの単位 |
| `trackmate_linking_max_distance` | linking の最大距離 |
| `trackmate_gap_closing`, `trackmate_gap_closing_max_distance`, `trackmate_max_frame_gap` | gap closing をするか、その最大距離と最大のフレーム数 |
| `trackmate_spot_count`, `trackmate_track_count` | XML の spot と track の数（track filter の前） |

`trackmate_` で始まる列は XML の `Settings` と `Model` から読んだ値で、記録がないときは空になる。

### track_results.csv・track_results_all_movies.csv

| 列 | 内容 |
|---|---|
| `movie_name`, `track_id`, `track_name` | 動画の名前と TrackMate の track |
| `trackmate_number_spots`, `trackmate_number_gaps`, `trackmate_longest_gap` | TrackMate が記録した値 |
| `start_frame`, `stop_frame`, `n_spots`, `frame_span` | 解析に使った spot の範囲と数 |
| `missing_frame_gap_count`, `max_observed_frame_gap` | frame が抜けた箇所の数と、最大の frame の差 |
| `status` | `fitted`、`too_short`（spot が少ない）、`insufficient_msd_points`（MSD の点が足りない） |
| `fit_points_used`, `slope_um2_per_s`, `intercept_um2`, `fit_r_squared` | fit の結果 |
| `diffusion_coefficient_um2_s` | 拡散係数 D（um²/s） |
| `is_immobile` | immobile の判定 |

### msd_points.csv

`fitted` の track の、frame lag ごとの MSD。列は `movie_name`, `track_id`, `lag`, `dt_s`, `msd_um2`, `n_displacements`, `used_for_fit`。

### squared_displacements.csv

`fitted` の track で、fit に使った lag の個々の二乗変位（平均をとる前の値）。列は `movie_name`, `track_id`, `lag`, `dt_s`, `source_frame`, `target_frame`, `dx_um`, `dy_um`, `squared_displacement_um2`。

## GIF

- `all_tracks.gif`: TrackMate で追跡した全 track。赤の丸が今の位置、黄色の線がそれまでの軌跡、数字が TRACK_ID。
- `fitted_tracks_with_d.gif`: 拡散係数を計算できた track だけ。ラベルは `TRACK_ID D=<値>`。赤が mobile、水色が immobile。

最初に track が現れる frame から、最後の frame までを描く。

## metadata.yaml

実行日時、ツールのバージョンと git のコミット、Python とライブラリのバージョン、使った設定、動画ごとの入力ファイル（名前、大きさ、SHA-256）、XML に記録された校正値と TrackMate の設定（`trackmate`）、警告とエラーを記録する。

`report.html` の最後には、動画ごとの TrackMate の設定（spot と track の数、検出のモデル、linking、gap closing）の表を出す。

## 旧リポジトリからの変更

- 1 回の実行で複数の動画を扱い、全動画のまとめ（`*_all_movies.*`）を足した。
- `track_results.csv` から、segment に関する列（`selected_segment_index` など）と、実行ごとに同じ値になる設定の列（`fit_initial_points`、`include_intercept`、`immobile_threshold_um2_s` など）を外した。設定は `metadata.yaml` に残る。
- `summary.csv` に immobile の割合と四分位を足した。
