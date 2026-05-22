# 代替検出器・前景分離 Phase 2 まとめ

実施日: 2026-05-21

## 目的

Phase 1 Gate（primary 5 枚中 5/5 ≤3×）未達（2/5）を受け、
HoughCircles の失敗原因が「検出器の種類」なのか「背景分離」なのかを切り分ける。

## 実験一覧

| 実験 | 手法 | 結果 |
|------|------|------|
| EXP-06 | SimpleBlobDetector | **部分的に有効**（後述） |
| EXP-07 | LoG blob (skimage) | **棄却** |
| EXP-08 | DoH blob (skimage) | **棄却** |
| EXP-09 | Depth Anything V2 Small + HoughCircles+NMS | **微改善のみ、コスト大** |
| EXP-10 | 虹色（薄膜干渉）マスク + HoughCircles+NMS | **algerian 29×→5.3×、master 1.0× 達成** |

---

## EXP-06: SimpleBlobDetector（circ=0.7）

| 指標 | 値 |
|------|----|
| 速度 | 10〜43 ms/枚 |
| メモリ | 91 MB |
| primary ≤3× | 2/5（algerian 2.7× — ただし HoughCircles と**別の画像**が改善） |

**HoughCircles との得意・不得意の分離が明確:**

| 画像タイプ | HoughCircles+NMS | SimpleBlobDetector |
|-----------|:---:|:---:|
| 多数浮遊（girl, master） | ✅ 1〜2× | ✗ 0.2〜0.6×（検出漏れ） |
| 単泡・屋外複雑背景（grapevine, algerian） | ✗ 29〜164× | ✅ 1〜3× |
| 単泡・クリーン背景（closeup） | ✗ 8× | ✗ 11× |

理由: connectedComponents ベースのため重複票が出ないが、
泡同士が重なると1つの塊に融合して検出漏れが起きる。

---

## EXP-07: LoG blob（棄却）

- 速度: 2〜21 秒/枚
- メモリ: 最大 793 MB
- 精度: どの設定も HoughCircles 以下
- 棄却理由: 葉のテクスチャも十分なスケールで blob として検出される。仮説外れ。

---

## EXP-08: DoH blob（棄却）

- 速度: 300〜430 ms/枚
- メモリ: 417 MB
- 棄却理由: SimpleBlobDetector に対して速度・メモリ・精度のいずれでも優位性なし。

---

## EXP-09: Depth Anything V2 Small による前景マスク

| 指標 | 値 |
|------|----|
| モデルロード | 6.6 秒（初回のみ） |
| 深度マップ生成 | 100〜400 ms/枚（Apple Silicon MPS） |
| メモリ | ~1 GB |
| algerian_grassland | 87 → 76（29× → 25×）微改善 |
| grapevine | 164 → 124（164× → 124×）微改善 |
| primary ≤3× | 2/5（EXP-05 と同等） |

**なぜ効かなかったか — 構造的な限界:**

シャボン玉は**透明**なため、単眼深度推定モデルは泡の向こう側（葉・草）の深度を
泡の領域に割り当てる。結果として深度マスクで背景を除くと泡も一緒に消える。
透明物体の前景分離は静止画の単眼深度推定が想定する問題設定と根本的に相性が悪い。

---

## EXP-10: 虹色（薄膜干渉）マスクによる前景検出

実施日: 2026-05-21

シャボン玉の薄膜干渉（虹色）は草・葉・地面にない泡固有の光学特性。
「局所的に色相が急変する領域（hue gradient）」と「明るいパステル領域（pastel）」の
2 種のマスクを組み合わせて HoughCircles+NMS の前景入力とする。

### アプローチ

| マスク | 手法 |
|--------|------|
| hue_grad | 色相のシクリック差分（折り返し補正）→ Sobel 代替勾配 → 膨張・クローズ |
| pastel | S:[20,160] × V:[80,255] の "明るいパステル" 領域 → 開放・膨張 |
| and | hue_grad ∩ pastel（最も絞り込む） |
| or | hue_grad ∪ pastel（最も広く取る） |

### primary 5 枚の結果

| 画像 | EXP-05 | hue_grad | pastel | **and** | or |
|------|-------:|--------:|-------:|-------:|---:|
| master | 2.0x | 1.9x | 1.2x | **1.0x** | 2.0x |
| girl | 1.2x | 1.2x | 1.3x | **1.1x** | 1.4x |
| algerian | 29x | 18x | 5.7x | **5.3x** | 18x |
| grapevine | 164x | 161x | 32x | **26x** | 171x |
| closeup | 8x | 9x | 8x | 11x | 8x |
| primary ≤3× | 2/5 | 2/5 | 2/5 | **2/5** | 2/5 |

- **algerian**: 29× → 5.3×（82% 削減）— 草原の緑はパステル基準を満たさないため除外に成功
- **master**: 2.0× → 1.0×（ほぼ完璧）
- **grapevine**: 164× → 26×（改善だが依然高い）— つる・葉が虹色条件を一部通過
- **closeup**: 改善なし — 泡自体の虹色が検出できていないか、背景との差が小さい

### メモリ・速度

- 追加メモリ: 190 → 563 MB（マスク計算のバッファ分）
- 速度: hue_grad 計算で master 等大解像度画像が遅い（6 秒）— numpy diff の直線コスト

### 限界

- **grapevine**: 1 泡 → 26× の主原因はつる・葉の境界が "局所色相変化" 基準を満たすこと。
  葉の輪郭は色相変化が大きいため hue_grad が広がる。
- **supermacro**: 両マスクとも 0% → 0 候補。マクロ写真では泡膜全体が均一色相のため
  hue_grad が低く、かつ pastel 条件も通らない（→ スコープ外なので影響なし）。

---

## Phase 2 全体の結論（EXP-10 追加後）

**algerian_grassland が 29× → 5.3× に改善。primary 2/5 ≤3× は変わらないが、残り 3 枚の課題がより明確になった。**

| 手法 | 速度 | メモリ | primary ≤3× | 最大改善 |
|------|-----:|-------:|:---:|---------|
| EXP-05 HoughCircles+NMS | 9〜6500ms | 190MB | 2/5 | — |
| EXP-06 SimpleBlobDetector | 10〜43ms | 91MB | 2/5（別の画像） | algerian 2.7× |
| EXP-09 Depth+HoughCircles | 200ms〜+6.6s | 998MB | 2/5 | algerian 25× |
| **EXP-10 虹色マスク+and** | **7〜6200ms** | **563MB** | **2/5** | **algerian 5.3×、master 1.0×** |

**「grapevine + closeup」の 2 枚が共通の壁**:
- grapevine: つる・葉の色相変化 → hue_grad が広がる
- closeup: 泡膜の虹色・パステル特性は存在するが背景との弁別が弱い

---

## 次のステップ候補

### 1. ハイブリッド検出器（静止画で試せる）

HoughCircles+NMS と SimpleBlobDetector の出力を統合する:
- algerian: EXP-10 and モード (5.3×) が最良
- master/girl: EXP-10 and モード (1.0×, 1.1×)
- grapevine: SimpleBlobDetector が唯一の有効手段

### 2. 動画・時系列アプローチ（根本的な解決）

透明物体の静止画分離は構造的に困難。連続フレームがあれば:
- **背景差分（MOG2）**: 静止した草・葉を背景モデルとして学習
- **時間フィルタ**: N フレーム連続する候補だけ残す
- **Kalman フィルタ追跡**: 個体 ID を付与してカウント精度向上

追加の重いモデルが不要で現スタックに乗せやすい。

### 3. グランドトゥルース整備（EXP-GT-01）

count ratio が EXP-10 and で master 1.0× まで来た。
grapevine の真の P/R を測るために点アノテーション（30 分）→ EXP-GT-02 で P/R 計算。
