# #868 Home Layout Specification

Status: implementation specification derived from `R-HOME-01` and `R-HOME-02` in #867.

## Reference canvas

- Initial viewport: 1344×756 (`R-HOME-01`)
- Full page: 1344×1833 (`R-HOME-02`)
- Desktop content container: centered, approximately 910px wide in the reference viewport.
- The left official page inside the final split demo uses a fixed internal desktop canvas. It may scale uniformly, but may not independently reflow or distort.

## Above-fold block order

1. `official-notice-strip`
2. `official-utility-row`
3. `official-primary-header`
4. `official-brand-search`
5. `official-lead-grid`
6. `official-quick-links`
7. `official-notice-sites`

## Initial viewport geometry

The following values are starting layout constants to be refined only against the approved references:

| Region | Reference target |
|---|---|
| content max width | 910px |
| notice strip | full width, compact height |
| utility row | full width, compact height, centered weather/status with right-side dropdown controls |
| header/GNB block | light surface; logo left; six GNB labels centered; search and all-menu icons right |
| brand/search region | brand copy left, long outlined search field right, hashtag hints below |
| lead grid | mayor card about 340px wide + banner card about 560px wide; shared height about 294px |
| quick-links card | full container width, one horizontal row with prev/next affordances and six icon labels |
| notice/sites grid | notice panel about 545px + major-sites panel about 350px |

## Semantic DOM targets

```text
.bg-page--home
  .bg-official-notice-strip
  .bg-home-utility
  header.bg-home-header
    .bg-home-header__logo
    nav.bg-home-gnb
    .bg-home-header__actions
  section.bg-home-search
  main#bg-content-main
    section.bg-home-lead
      article.bg-home-mayor-card
      article.bg-home-carousel-card
    nav.bg-home-quick-links
    section.bg-home-notice-sites
    section.bg-home-media-row
    section.bg-home-field-info
    section.bg-home-partner-strip
  footer.bg-home-footer
```

## Required content decisions

- Visible identity is `전남광주통합특별시북구`.
- GNB labels and order are exactly the six values in the reference ledger.
- The initial carousel is a single frozen slide chosen from `R-HOME-01`; no automatic rotation.
- Card surfaces, labels, controls, and lists are DOM/CSS. Portrait, banner artwork, visual editorial cards, official logo, and footer certification artwork are individual approved image crops only.
- The split-demo chat shell is not nested inside `.bg-page--home`.

## CSS constraints

- Every home-specific selector starts with `.bg-page--home`.
- Shared selector names may only carry neutral primitives, not home geometry.
- No bare `.bg-util-bar`, `.bg-header`, `.bg-gnb`, `.bg-search-hero`, or `.bg-hero` rules may carry home-only dimensions or colors.
- No emoji may stand in for official search, menu, service, or site icons.

## Evidence required for the first home patch

1. Local render at 1344×756.
2. Local full render at 1344×1833.
3. 1:1 reference/render comparison for the above-fold region.
4. 1:1 reference/render comparison for lower modules and footer.
5. Browser console errors: 0.
6. External requests: 0.
7. Storage writes: 0.
