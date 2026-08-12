"""
ComfyUI-Anima-2.9B-loraPatch

Applies 28-block Anima LoRAs (anima-base-v1.0 / anima-preview and its finetunes)
to the 40-block Anima-2.9B model by remapping their block indices.

Why this is needed
------------------
Anima-2.9B is a block-expansion (depth upscale) of anima-base-v1.0, not a retrain.
Verified by direct weight comparison: all 28 original transformer blocks are present
in 2.9B bit-identically (max|diff| == 0), as are x_embedder and final_layer. Twelve
new blocks were inserted at indices 2, 5, 8, 11, 14, 17, 21, 24, 27, 30, 33, 36.

So base block j no longer lives at index j:

    base  0  1  2  3  4  5  6  7  8  9 10 11 12 13 ...
    2.9B  0  1  3  4  6  7  9 10 12 13 15 16 18 19 ...

A LoRA trained on the 28-block base is therefore applied to the wrong layer from
block 2 onward -- and silently, because blocks.2 .. blocks.27 do exist in the
40-block model, so no "lora key not loaded" warning is ever emitted.

What this does
--------------
Wraps comfy.lora.load_lora and rewrites its key_map so LoRA block j targets the
block that actually holds the original base weights. The key_map already contains
both the kohya (lora_unet_blocks_5_...) and the peft (diffusion_model.blocks.5....)
spellings pointing at the same model key, so rewriting the map values fixes both
LoRA formats at once. Text-encoder keys (lora_te_*) go through model_lora_keys_clip
and are left untouched.

Remapping is applied only when all of the following hold:
  - the model is Anima (its key_map references diffusion_model.llm_adapter.*)
  - the model has exactly blocks 0..39 (the layout this mapping was measured on)
  - the LoRA covers exactly blocks 0..27
Anything else -- a 28-block model, a native 40-block LoRA, a non-Anima model, an
unknown block layout -- is passed through unchanged.

Set the environment variable ANIMA_LORA_REMAP=0 to disable at runtime.
"""

import logging
import os
import re

import comfy.lora

LOG_PREFIX = "[Anima 2.9B LoRA Patch]"

# Indices of the 12 blocks inserted by the 2.9B depth expansion.
INSERTED_BLOCKS = (2, 5, 8, 11, 14, 17, 21, 24, 27, 30, 33, 36)

NUM_BLOCKS_29B = 40
NUM_BLOCKS_BASE = NUM_BLOCKS_29B - len(INSERTED_BLOCKS)  # 28


def _build_block_map():
    # The original base blocks are the 2.9B blocks that were not inserted, in order.
    kept = [i for i in range(NUM_BLOCKS_29B) if i not in INSERTED_BLOCKS]
    return {j: i for j, i in enumerate(kept)}


# base block index -> Anima-2.9B block index
BASE_TO_29B = _build_block_map()
assert len(BASE_TO_29B) == NUM_BLOCKS_BASE

# Matches a model-side (key_map value) diffusion block key.
# Anchored so that diffusion_model.llm_adapter.blocks.N.* is NOT matched.
MODEL_BLOCK_RE = re.compile(r"^(diffusion_model\.blocks\.)(\d+)(\..*)$")

# Matches a LoRA-side key belonging to a diffusion block, in the formats seen in
# the wild for Anima. llm_adapter and text-encoder keys do not match these.
LORA_BLOCK_RES = (
    re.compile(r"^lora_unet_blocks_(\d+)_"),           # kohya  (networks.lora_anima)
    re.compile(r"^diffusion_model\.blocks\.(\d+)\."),  # peft / generic
    re.compile(r"^blocks\.(\d+)\."),                   # bare
)


def _enabled():
    return os.environ.get("ANIMA_LORA_REMAP", "1").strip().lower() not in ("0", "off", "false", "no")


def _model_block_indices(to_load):
    out = set()
    for value in to_load.values():
        if not isinstance(value, str):
            continue
        m = MODEL_BLOCK_RE.match(value)
        if m is not None:
            out.add(int(m.group(2)))
    return out


def _lora_block_indices(lora):
    out = set()
    for key in lora.keys():
        if not isinstance(key, str):
            continue
        for rex in LORA_BLOCK_RES:
            m = rex.match(key)
            if m is not None:
                out.add(int(m.group(1)))
                break
    return out


def _is_anima(to_load):
    for value in to_load.values():
        if isinstance(value, str) and value.startswith("diffusion_model.llm_adapter."):
            return True
    return False


def _remap_key_map(to_load):
    """Return a copy of to_load with diffusion block targets shifted to the 2.9B layout."""
    out = {}
    remapped = 0
    for key, value in to_load.items():
        m = MODEL_BLOCK_RE.match(value) if isinstance(value, str) else None
        if m is None:
            out[key] = value
            continue

        src = int(m.group(2))
        dst = BASE_TO_29B.get(src)
        if dst is None:
            # Blocks 28..39 are unreachable for a 28-block LoRA. Dropping these
            # entries keeps the map a clean bijection onto real target blocks.
            continue

        out[key] = "{}{}{}".format(m.group(1), dst, m.group(3))
        if dst != src:
            remapped += 1
    return out, remapped


def _needs_remap(lora, to_load):
    if not _enabled():
        return False
    if not _is_anima(to_load):
        return False

    model_blocks = _model_block_indices(to_load)
    if not model_blocks:
        return False

    if model_blocks != set(range(NUM_BLOCKS_29B)):
        # 28-block Anima (nothing to do) or an unknown layout this map was not
        # measured against -- stay out of the way either way.
        if len(model_blocks) not in (0, NUM_BLOCKS_BASE):
            logging.info(
                "{} unknown Anima block layout ({} blocks); leaving LoRA untouched.".format(
                    LOG_PREFIX, len(model_blocks)
                )
            )
        return False

    lora_blocks = _lora_block_indices(lora)
    if lora_blocks == set(range(NUM_BLOCKS_BASE)):
        return True

    if lora_blocks and lora_blocks != set(range(NUM_BLOCKS_29B)):
        logging.info(
            "{} LoRA covers {} diffusion blocks (max {}); not a 28-block base LoRA, "
            "leaving it untouched.".format(LOG_PREFIX, len(lora_blocks), max(lora_blocks))
        )
    return False


_orig_load_lora = getattr(comfy.lora, "load_lora", None)


def patched_load_lora(lora, to_load, *args, **kwargs):
    try:
        if _needs_remap(lora, to_load):
            new_to_load, remapped = _remap_key_map(to_load)
            logging.info(
                "{} 28-block LoRA on 40-block Anima-2.9B: remapped {} target keys "
                "to the expanded block layout.".format(LOG_PREFIX, remapped)
            )
            to_load = new_to_load
    except Exception as err:
        # Never let this patch break LoRA loading -- fall through untouched.
        logging.warning("{} remap skipped due to error: {}".format(LOG_PREFIX, err))

    return _orig_load_lora(lora, to_load, *args, **kwargs)


patched_load_lora._anima29b_lora_patch = True

if _orig_load_lora is None:
    logging.warning(
        "{} comfy.lora.load_lora not found; cannot install. This ComfyUI version is "
        "not supported by this patch.".format(LOG_PREFIX)
    )
elif getattr(_orig_load_lora, "_anima29b_lora_patch", False):
    logging.info("{} already installed; skipping.".format(LOG_PREFIX))
else:
    comfy.lora.load_lora = patched_load_lora
    logging.info(
        "{} installed (base block j -> 2.9B block {}...). Set ANIMA_LORA_REMAP=0 to disable.".format(
            LOG_PREFIX, [BASE_TO_29B[j] for j in range(6)]
        )
    )

# No workflow nodes: this is a load-time patch only.
NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}
