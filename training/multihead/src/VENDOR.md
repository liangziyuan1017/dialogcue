# Multihead self-contained runtime

Vendored from frozen `training/src` so this package does **not** import Stage1/2 code.

| Path | Role |
|------|------|
| `src/conversation_parser.py` | Load `output_rewarded*.py` |
| `src/remap/` | Emotion/willingness mappers (slot relocate only) |
| `src/models/text_encoder.py` | RoBERTa / mock encoder |
| `configs/slot_relocate/` | Emotion/willingness YAML copies |

Warm-start `encoder_ckpt` may still point at `training/checkpoints/...` if present; missing → HF/scratch init.
