# ComfyUI-Anima-2.9B-loraPatch

**English** | [日本語](README.ja.md)

A load-time patch that applies LoRAs trained on anima-base-v1.0 / anima-preview (28 blocks) to Anima-2.9B (40 blocks) **with the correct layer correspondence**. No workflow nodes are added.

## Why it is needed

Anima-2.9B is a block expansion (depth upscale) of anima-base-v1.0: 12 new blocks were inserted **between** the original 28. So base block j no longer lives at index j:

| base | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2.9B | 0 | 1 | 3 | 4 | 6 | 7 | 9 | 10 | 12 | 13 | 15 | 16 | 18 | 19 |

| base | 14 | 15 | 16 | 17 | 18 | 19 | 20 | 21 | 22 | 23 | 24 | 25 | 26 | 27 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2.9B | 20 | 22 | 23 | 25 | 26 | 28 | 29 | 31 | 32 | 34 | 35 | 37 | 38 | 39 |

(Measured by direct weight comparison; the 28 mapped blocks are bit-identical to the base model.)

Without this patch, a 28-block LoRA applied to 2.9B hits the **wrong layers silently** — `blocks.2` through `blocks.27` all exist in the 40-block model, so no "lora key not loaded" warning is ever emitted. Only blocks 0 and 1 land correctly. This manifests as "the LoRA doesn't work" or "raising strength degrades the image instead".

## Installation

1. Put this folder into `ComfyUI/custom_nodes/`
2. Restart ComfyUI
3. Apply LoRAs with the standard LoRA Loader nodes as usual; remapping happens automatically only when the conditions below are met

No extra pip installs, no workflow changes.

**Note: nothing appears in the node list (Add Node menu).** This patch takes effect automatically at startup; the log lines below are the only way to confirm it is active.

To uninstall, delete the folder or append `.disabled` to its name.

## Requirements

You also need [ComfyUI-Anima-2.9B-blocksPatch](https://github.com/sparklingcoffee777/ComfyUI-Anima-2.9B-blocksPatch) (or the original ComfyUI-Anima-2.9B) so that Anima-2.9B loads with all 40 blocks. This patch cannot help a model that was already truncated to 28 blocks.

## How it works

Wraps `comfy.lora.load_lora` and rewrites the block indices in the key_map values (the LoRA-key → model-key table). Both the kohya format (`lora_unet_blocks_5_...`) and the peft / AI-Toolkit format (`diffusion_model.blocks.5....`) resolve through the same key_map, so one rewrite fixes both.

Remapping is applied only when **all** of the following hold:

- the model is Anima (its key_map references `diffusion_model.llm_adapter.*`)
- the model has exactly blocks 0..39 (the layout this mapping was measured on)
- the LoRA covers exactly blocks 0..27

Anything else — a 28-block model, a native 40-block LoRA, a non-Anima model, an unknown layout — passes through unchanged. Text-encoder keys (`lora_te_*`) and `llm_adapter` keys are never touched.

## Verifying it works

Startup log:

```
[Anima 2.9B LoRA Patch] installed (base block j -> 2.9B block [0, 1, 3, 4, 6, 7]...). Set ANIMA_LORA_REMAP=0 to disable.
```

When a 28-block LoRA is applied to 2.9B:

```
[Anima 2.9B LoRA Patch] 28-block LoRA on 40-block Anima-2.9B: remapped 1040 target keys to the expanded block layout.
```

(The count varies per LoRA.)

## Environment variables

| Variable | Default | Meaning |
|---|---|---|
| `ANIMA_LORA_REMAP` | `1` | Set to `0` to disable remapping |

## Caveats

- Layer correspondence becomes correct, but the residual stream now passes through 12 new blocks and a retrained llm_adapter, so **the LoRA will not behave identically** to how it does on the base model. Start around strength 0.5–0.7
- A future LoRA trained natively on 2.9B that deliberately targets only the lower 28 blocks would be misdetected (an unusual configuration; disable via the environment variable above if it ever happens)

## See also

[storyAura/Anima2.9B-Lora-weight-conversion](https://github.com/storyAura/Anima2.9B-Lora-weight-conversion) takes the alternative approach of converting the LoRA files ahead of time (its insertion indices match this patch). That is useful outside ComfyUI or when distributing converted files. Running both is safe — a converted LoRA no longer covers exactly blocks 0..27, so this patch passes it through untouched.

## License

GPL-3.0, matching ComfyUI itself, since this patch hooks ComfyUI internals directly.
