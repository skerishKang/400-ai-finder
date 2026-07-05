# Source Capture Manifest

This directory records user-supplied current Buk-gu reference captures for issue #867.

## Import policy

- Copy each approved PNG byte-for-byte.
- Do not crop, resize, annotate, recompress, optimize, or rename the source file during import.
- Confirm the imported bytes match the SHA-256 value below.
- Source captures are comparison and crop-source artifacts only. They are not runtime page surfaces.

## Approved entries

| Capture ID | Filename | SHA-256 | Dimensions | Role |
|---|---|---|---:|---|
| R-HOME-01 | `CaptureX_2026-07-05_150817_bukgu.gwangju.kr.png` | `e851f990a710b13251700177e8355f18477fcceb5c5e8497a9504e085e2d2397` | 1344×756 | Initial desktop home viewport |
| R-HOME-02 | `CaptureX_2026-07-05_150832_bukgu.gwangju.kr_full.png` | `e0c1d451312056a5314fa2dc5b77d62fb53ef6dc90352797d78e4bb57eae3c49` | 1344×1833 | Full home flow and footer |

## Required verification after local import

```text
sha256sum docs/artifacts/863-reference/source/CaptureX_2026-07-05_150817_bukgu.gwangju.kr.png \
          docs/artifacts/863-reference/source/CaptureX_2026-07-05_150832_bukgu.gwangju.kr_full.png
```

The output must match this manifest exactly before any crop extraction or home implementation work begins.