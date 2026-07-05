# Source Capture Manifest

This directory contains user-supplied current Buk-gu reference captures for issue #867.

## Import policy

- Copy each user-supplied PNG byte-for-byte.
- Do not crop, resize, annotate, recompress, optimize, or rename the source file during import.
- Record SHA-256 and decoded dimensions after import.
- Source captures are comparison and crop-source artifacts only. They are not runtime page surfaces.

## Required entries

| Capture ID | Filename | SHA-256 | Dimensions | Role |
|---|---|---|---:|---|
| R-HOME-01 | `CaptureX_2026-07-05_150817_bukgu.gwangju.kr.png` | pending | 1344×756 | Initial desktop home viewport |
| R-HOME-02 | `CaptureX_2026-07-05_150832_bukgu.gwangju.kr_full.png` | pending | 1344×1833 | Full home flow and footer |

The SHA-256 values must be populated only after the original binary files are added to this directory.