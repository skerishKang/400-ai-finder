# Crop Manifest (Stage #863 followup-3)

This manifest tracks individual visual assets cropped from `bukgu_home.png` to reconstruct the high-fidelity semantic DOM layout of Gwangju Buk-gu portal homepage.

---

## 1. Crop Asset List

| Asset Name | Source Image | Pixel Rectangle (x, y, width, height) | Intended DOM Placement | Runtime Usage |
| --- | --- | --- | --- | --- |
| `home-hero-mayor.png` | `bukgu_home.png` | (115, 550, 610, 350) | `.bg-hero__left` > `<img>` | Individual `<img>` only |
| `home-hero-census.png` | `bukgu_home.png` | (740, 550, 640, 350) | `.bg-hero__right` > `<img>` | Individual `<img>` only |
| `home-quick-search.png` | `bukgu_home.png` | (115, 960, 200, 200) | `.bg-quick` > `.bg-quick-item` > `<img>` | Individual `<img>` only |
| `home-quick-office.png` | `bukgu_home.png` | (325, 960, 200, 200) | `.bg-quick` > `.bg-quick-item` > `<img>` | Individual `<img>` only |
| `home-quick-donation.png` | `bukgu_home.png` | (535, 960, 200, 200) | `.bg-quick` > `.bg-quick-item` > `<img>` | Individual `<img>` only |
| `home-quick-money.png` | `bukgu_home.png` | (745, 960, 200, 200) | `.bg-quick` > `.bg-quick-item` > `<img>` | Individual `<img>` only |
| `home-quick-reservation.png` | `bukgu_home.png` | (955, 960, 200, 200) | `.bg-quick` > `.bg-quick-item` > `<img>` | Individual `<img>` only |
| `home-quick-waiting.png` | `bukgu_home.png` | (1165, 960, 215, 200) | `.bg-quick` > `.bg-quick-item` > `<img>` | Individual `<img>` only |
| `home-card-donation.png` | `bukgu_home.png` | (115, 1600, 300, 250) | `.bg-sub-carousel` (Donation) > `<img>` | Individual `<img>` only |
| `home-card-field-sketch.png` | `bukgu_home.png` | (430, 1600, 300, 250) | `.bg-sub-carousel` (Field Sketch) > `<img>` | Individual `<img>` only |
| `home-card-news.png` | `bukgu_home.png` | (745, 1600, 300, 250) | `.bg-sub-carousel` (Card News) > `<img>` | Individual `<img>` only |
| `home-card-notice.png` | `bukgu_home.png` | (1060, 1600, 320, 250) | `.bg-sub-carousel` (Notice) > `<img>` | Individual `<img>` only |
| `home-footer-open-data.png` | `bukgu_home.png` | (1050, 2450, 80, 80) | `.bg-footer__bot-badges` > `<img>` | Individual `<img>` only |
| `home-footer-wa.png` | `bukgu_home.png` | (1140, 2450, 80, 80) | `.bg-footer__bot-badges` > `<img>` | Individual `<img>` only |
| `home-footer-qr-mascot.png` | `bukgu_home.png` | (1230, 2450, 150, 80) | `.bg-footer__bot-badges` > `<img>` | Individual `<img>` only |

---

## 2. Verification
* All cropped files are stored in `src/web/static/images/bukgu-crops/`.
* Verification completed with zero usage of whole-page screenshots as primary background or page elements.
