# 解析ルール

拡散係数の計算方法を定める。標準の値は [`configs/default.yaml`](../configs/default.yaml) にあり、画面で変えた値は実行ごとの `metadata.yaml` に残る。

## 単位の換算

| 項目 | 標準の値 |
|---|---|
| Frame interval | 76.0 ms（0.076 s） |
| Pixel size | 166.70 nm（0.16670 um） |

時間は frame の番号から、`dt = frame lag × frame interval` で求める。座標は pixel にそろえてから、pixel size を掛けて um にする。

TrackMate の XML の座標は、元の動画に校正値がなければ pixel、あれば um などの単位で記録される。単位つきの XML の座標は XML に書かれた pixel 幅で割り、pixel に戻してから使う。そのため、どちらの XML でも、解析に使う pixel size と frame interval は設定の値になる。

XML に記録された pixel 幅や frame interval が設定の値と 1% 以上違うときは、警告を出す。顕微鏡や撮影条件が違う動画を、誤った値で計算しないためである。

## Trajectory

TrackMate の `TRACK_ID` が同じ spot を、frame が抜けていても 1 本の trajectory として扱う（gap を許す full track）。標準では TrackMate の track filter を通った track（`FilteredTracks`）だけを使う。

## 最短の track

spot の数が 30 未満の track は、拡散係数を計算しない（`status = too_short`）。初期 4 点の fit に必要な数よりかなり多いが、十分に長い trajectory だけを使うために、この値にしている。

## MSD

MSD は実際の frame の差（frame lag）ごとに求める。frame lag が L の MSD には、frame の差がちょうど L の spot の組だけを使う。

たとえば frame が `1, 2, 4, 5, 6` の track では、lag 2 に使う組は `2 → 4` と `4 → 6` になる。`1 → 4` は frame の差が 3 なので lag 3 に入る。frame が抜けても時間の軸はずれない。

## 拡散係数の fit

MSD-時間の曲線の最初の 4 点（lag が小さい順に 4 つ）を直線で fit する。4 点にしたのは、榎本らの論文と同じ設定にそろえるためである。

```text
MSD(dt) = 4D × dt + b
```

標準では切片 `b` を含めて fit する。設定 `include_intercept: false` にすると、`MSD(dt) = 4D × dt` で fit する。拡散係数は `D = 傾き / 4` で求める。

MSD の点が 4 つ未満の track は、拡散係数を計算しない（`status = insufficient_msd_points`）。

## Immobile の判定

`D < 0.0004 um²/s` の track を immobile とする。

## 旧リポジトリとの関係

旧リポジトリ（spotiflow-diffusion-coefficient）の標準の解析（`trajectory_mode: full_track_with_gaps`、`msd_mode: frame_lag`）だけを移植した。旧リポジトリにあった「frame が連続する最も長い区間だけを使う」モード（longest contiguous segment）は移植していない。合成データで、移植後の拡散係数が旧コードと一致することを確かめている。
