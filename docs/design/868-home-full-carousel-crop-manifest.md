# #868 Home Full Carousel Crop Manifest

Status: approved mechanical extraction of the R-HOME-02 carousel banner.

## Source authority

- Reference: `R-HOME-02`
- Source: `docs/artifacts/863-reference/source/CaptureX_2026-07-05_150832_bukgu.gwangju.kr_full.png`
- Required SHA-256: `e0c1d451312056a5314fa2dc5b77d62fb53ef6dc90352797d78e4bb57eae3c49`
- Required source dimensions: `1344x1833`

## Approved derived asset

| Output path | Box | Expected size |
|---|---:|---:|
| `src/web/static/images/bukgu-current/home-alert-banner-r-home-02.png` | `[562, 258, 1123, 555)` | `561x297` |

## Crop rule

- Lossless PNG only, no resize, no recompress, no annotation.
- Source file must not be altered.
- Output must match source crop pixel-for-pixel and size exactly.

## Purpose

This asset replaces the R-HOME-01 carousel slide (`home-alert-banner.png`) so that
full-home render evidence against R-HOME-02 compares the same carousel state.
