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
| R-DEPT-01 | `bukgu-menu-dropdown.png` | `738b7155d3ab5f5bdc6cc5027aa65f0a7b913f6bf40bbaf8e483aa8221a7c650` | 1343×755 | Desktop home with `북구소개` mega-menu expanded |
| R-DEPT-02 | `CaptureX_2026-07-06_001130_bukgu.gwangju.kr_upmu.png` | `dc82c006207adb87b9e5681261e924460eece16144d08e65404ecb20aa36052d` | 1344×756 | `업무 및 전화번호 안내` initial viewport |
| R-DEPT-03 | `CaptureX_2026-07-06_001132_bukgu.gwangju.kr_upmu_full.png` | `29fd59f502d7ff8b1f501d642fa210f587755af32000319ec96113dd144df6a9` | 1344×1242 | `업무 및 전화번호 안내` full default directory |
| R-DEPT-04 | `CaptureX_2026-07-06_001716_bukgu.gwangju.kr_gongdong.png` | `c9d23765583f24b54a5c5ba6802707cbe3392a6431fe96429ea8b4d01bf93949` | 1344×756 | `공동주택` query result initial viewport |
| R-DEPT-05 | `CaptureX_2026-07-06_001719_bukgu.gwangju.kr_gongdong_full.png` | `1907dccd84112f22bf1425b25d75e1ebb8cb27ab66bb297ced98f7d1bdcd7823` | 1344×1335 | `공동주택` query result full page |

## Required verification after local import

```text
sha256sum docs/artifacts/863-reference/source/CaptureX_2026-07-05_150817_bukgu.gwangju.kr.png \
          docs/artifacts/863-reference/source/CaptureX_2026-07-05_150832_bukgu.gwangju.kr_full.png
```

The output must match this manifest exactly before any crop extraction or home implementation work begins.

## #869 required verification

Verify the five R-DEPT source files byte-for-byte against their SHA-256 values
and dimensions before any J-DEPT-01 implementation work. These captures remain
reference/comparison and crop-source artifacts only; they must never be used as
runtime page surfaces, page backgrounds, or screenshot overlays.