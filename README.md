# ComfyUI-Anima-2.9B-loraPatch

日本語 / English (English follows Japanese)

---

## 日本語

### これは何？

anima-base-v1.0 / anima-preview（28 ブロック）用に学習された LoRA を、Anima-2.9B（40 ブロック）に **正しいレイヤー対応で** 適用するための起動時パッチです。ワークフローノードは追加しません。

### なぜ必要か

Anima-2.9B は anima-base-v1.0 の block expansion（深さ拡張）モデルで、元の 28 ブロックの **間に** 新規 12 ブロックが挿入されています。そのため base のブロック j は 2.9B ではインデックス j に存在しません:

| base | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2.9B | 0 | 1 | 3 | 4 | 6 | 7 | 9 | 10 | 12 | 13 | 15 | 16 | 18 | 19 |

| base | 14 | 15 | 16 | 17 | 18 | 19 | 20 | 21 | 22 | 23 | 24 | 25 | 26 | 27 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2.9B | 20 | 22 | 23 | 25 | 26 | 28 | 29 | 31 | 32 | 34 | 35 | 37 | 38 | 39 |

（重み比較で実測。対応先 28 ブロックはビット完全一致）

パッチなしで 28 ブロック LoRA を 2.9B に適用すると、`blocks.2`〜`blocks.27` は 40 ブロックモデルにも存在するため **警告ゼロで別のレイヤーに誤適用** されます。正しく当たるのはブロック 0, 1 の 2 つだけです。「LoRA が効かない」「強度を上げると絵が壊れる」症状の原因になります。

### 動作

`comfy.lora.load_lora` をラップし、key_map（LoRA キー → モデルキーの対応表）の値のブロック番号を上表で張り替えます。kohya 形式（`lora_unet_blocks_5_...`）と peft 形式（`diffusion_model.blocks.5....`）は同じ key_map を参照するため、両形式が同時に直ります。

リマップが適用されるのは以下 **すべて** を満たすときだけです:

- モデルが Anima（key_map に `diffusion_model.llm_adapter.*` が含まれる）
- モデルがちょうどブロック 0〜39 を持つ（このマッピングを実測した構成）
- LoRA がちょうどブロック 0〜27 をカバーする

それ以外（28 ブロックモデル、ネイティブ 40 ブロック LoRA、非 Anima、未知レイアウト）は無変更で素通しします。テキストエンコーダ側のキー（`lora_te_*`）には触れません。

### 注意

- レイヤー対応は正しくなりますが、残差ストリームに未学習の新規 12 ブロックと再学習済み llm_adapter が挟まるため、**効き方は base での学習時と同一にはなりません**。強度 0.5〜0.7 から試すことを推奨します
- 2.9B ネイティブに学習された LoRA が将来「下位 28 ブロックのみ」を学習対象にした場合、誤検知します（通常やらない構成ですが、その場合は下記の環境変数で無効化してください）

### インストール / 使い方

1. このフォルダを `ComfyUI/custom_nodes/` に置く（ZIP ならそのまま展開）
2. ComfyUI を再起動
3. あとは通常どおり LoRA Loader（標準ノード）で LoRA を適用するだけ。条件に合致したときだけ自動でリマップされます

追加の pip インストールは不要、ワークフローの変更も不要です。

**注意: ノード一覧（Add Node メニュー）には何も追加されません。** これは起動時に自動で効くパッチであり、動作確認は下記のログのみで行います。

アンインストールはフォルダを削除するか、フォルダ名の末尾に `.disabled` を付けてください。

### 環境変数

| 変数 | 既定 | 意味 |
|---|---|---|
| `ANIMA_LORA_REMAP` | `1` | `0` にするとリマップを無効化 |

### 確認方法

起動ログ:

```
[Anima 2.9B LoRA Patch] installed (base block j -> 2.9B block [0, 1, 3, 4, 6, 7]...). Set ANIMA_LORA_REMAP=0 to disable.
```

2.9B に 28 ブロック LoRA を適用したとき:

```
[Anima 2.9B LoRA Patch] 28-block LoRA on 40-block Anima-2.9B: remapped 1040 target keys to the expanded block layout.
```

（件数は LoRA により変動）

### 他ノードとの関係

`ComfyUI-Anima-2.9B`（オフィシャルパッチ）や `ComfyUI-Anima-2.9B-blocksPatch` とはフック先が異なり、依存も競合もありません。ただし 2.9B を 40 ブロックでロードするためにどちらか一方（blocksPatch 推奨）が必要です — 28 ブロックに切り詰められたモデルに対しては本パッチは動作しません。

---

## English

### What is this?

A load-time patch that applies LoRAs trained on anima-base-v1.0 / anima-preview (28 blocks) to Anima-2.9B (40 blocks) **with the correct layer correspondence**. No workflow nodes are added.

### Why it is needed

Anima-2.9B is a block expansion (depth upscale) of anima-base-v1.0: 12 new blocks were inserted **between** the original 28. So base block j no longer lives at index j:

| base | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2.9B | 0 | 1 | 3 | 4 | 6 | 7 | 9 | 10 | 12 | 13 | 15 | 16 | 18 | 19 |

| base | 14 | 15 | 16 | 17 | 18 | 19 | 20 | 21 | 22 | 23 | 24 | 25 | 26 | 27 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2.9B | 20 | 22 | 23 | 25 | 26 | 28 | 29 | 31 | 32 | 34 | 35 | 37 | 38 | 39 |

(Measured by direct weight comparison; the 28 mapped blocks are bit-identical to the base model.)

Without this patch, a 28-block LoRA applied to 2.9B hits the **wrong layers silently** — `blocks.2` through `blocks.27` all exist in the 40-block model, so no "lora key not loaded" warning is ever emitted. Only blocks 0 and 1 land correctly. This manifests as "the LoRA doesn't work" or "raising strength degrades the image instead".

### How it works

Wraps `comfy.lora.load_lora` and rewrites the block indices in the key_map values (the LoRA-key → model-key table). Both the kohya format (`lora_unet_blocks_5_...`) and the peft format (`diffusion_model.blocks.5....`) resolve through the same key_map, so one rewrite fixes both.

Remapping is applied only when **all** of the following hold:

- the model is Anima (its key_map references `diffusion_model.llm_adapter.*`)
- the model has exactly blocks 0..39 (the layout this mapping was measured on)
- the LoRA covers exactly blocks 0..27

Anything else — a 28-block model, a native 40-block LoRA, a non-Anima model, an unknown layout — passes through unchanged. Text-encoder keys (`lora_te_*`) are never touched.

### Caveats

- Layer correspondence becomes correct, but the residual stream now passes through 12 new blocks and a retrained llm_adapter, so **the LoRA will not behave identically** to how it does on the base model. Start around strength 0.5–0.7
- A future LoRA trained natively on 2.9B that deliberately targets only the lower 28 blocks would be misdetected (an unusual configuration; disable via the environment variable below if it ever happens)

### Installation / Usage

1. Put this folder into `ComfyUI/custom_nodes/` (just extract the ZIP as-is)
2. Restart ComfyUI
3. Apply LoRAs with the standard LoRA Loader nodes as usual; remapping happens automatically only when the conditions above are met

No extra pip installs, no workflow changes.

**Note: nothing appears in the node list (Add Node menu).** This patch takes effect automatically at startup; the log lines below are the only way to confirm it is active.

To uninstall, delete the folder or append `.disabled` to its name.

### Environment variables

| Variable | Default | Meaning |
|---|---|---|
| `ANIMA_LORA_REMAP` | `1` | Set to `0` to disable remapping |

### Verifying it works

Startup log:

```
[Anima 2.9B LoRA Patch] installed (base block j -> 2.9B block [0, 1, 3, 4, 6, 7]...). Set ANIMA_LORA_REMAP=0 to disable.
```

When a 28-block LoRA is applied to 2.9B:

```
[Anima 2.9B LoRA Patch] 28-block LoRA on 40-block Anima-2.9B: remapped 1040 target keys to the expanded block layout.
```

(The count varies per LoRA.)

### Relationship with other nodes

Hooks a different function than `ComfyUI-Anima-2.9B` (the official patch) and `ComfyUI-Anima-2.9B-blocksPatch`; no dependency, no conflict. However, one of them (blocksPatch recommended) is required so that 2.9B loads with all 40 blocks — this patch cannot help a model that was already truncated to 28 blocks.

---

## 関連リポジトリ / Related repositories

- [ComfyUI-Anima-2.9B-blocksPatch](https://github.com/sparklingcoffee777/ComfyUI-Anima-2.9B-blocksPatch) — Anima-2.9B を 40 ブロックで正しくロードするためのパッチ。**本パッチを使う前提として必要です**（28 ブロックに切り詰められたモデルにはリマップが働きません） / required so that Anima-2.9B loads with all 40 blocks; this patch cannot help a model already truncated to 28 blocks

## 参考 / See also

LoRA ファイルを事前変換する別アプローチとして [storyAura/Anima2.9B-Lora-weight-conversion](https://github.com/storyAura/Anima2.9B-Lora-weight-conversion) があります（挿入インデックスは本パッチと一致）。ComfyUI 以外の環境や、変換済みファイルを配布したい場合はそちらが有用です。なお本パッチと併用しても二重リマップは起きません（変換済み LoRA はブロック 0〜27 の完全網羅に該当しないため素通しします）。

[storyAura/Anima2.9B-Lora-weight-conversion](https://github.com/storyAura/Anima2.9B-Lora-weight-conversion) takes the alternative approach of converting the LoRA files ahead of time (its insertion indices match this patch). That is useful outside ComfyUI or when distributing converted files. Running both is safe — a converted LoRA no longer covers exactly blocks 0..27, so this patch passes it through untouched.

## ライセンス / License

GPL-3.0. ComfyUI 本体（GPL-3.0）の内部を直接フックするため、同一ライセンスを採用しています。 / GPL-3.0, matching ComfyUI itself, since this patch hooks ComfyUI internals directly.
