# Buk-gu AI Administrative Browser Product Directive

Status: owner-approved and authoritative from 2026-07-10.

This directive supersedes the narrow local/static product-scope restrictions in
the #863-#870 reference and execution documents. Those documents remain useful
for screenshot provenance, visual comparison, and historical decisions, but
they no longer limit the authorized MVP product experience.

## Product intent

The product is not a chat widget attached to an institutional website. It is an
AI administrative browser that lets a resident describe a goal in natural
language, then watches the assistant find, open, search, and prepare work inside
a faithful Buk-gu website experience.

The initial experience is intentionally chat-first. After the first supported
request, the interface transitions cinematically into a split workspace:

- the left side is a semantic, interactive Buk-gu website clone;
- the right side is the conversation, action explanation, and confirmation rail;
- an on-screen AI cursor visibly moves, clicks, scrolls, focuses controls, and
  types search terms or draft text;
- the resident can interrupt, take over, revise, or cancel at any time.

The entry screen may use approved Buk-gu identity, civic imagery, the mayor's
portrait, motion, video, and editorial composition to make the service feel
ambitious and public-facing rather than like an internal prototype.

## Owner authorization

The project owner has stated that the MVP is being produced under an agreement
with Buk-gu leadership and has authorized use of Buk-gu site structure,
branding, public content, and supplied media for the demonstration. Authorized
live-site inspection and public-content synchronization may therefore be used
to keep the clone and answers current.

This statement is a project implementation directive, not a substitute for the
access credentials, data-processing terms, or deployment approvals required by
a later production contract.

## Interaction authority

The agent may perform reversible, visible actions without an extra confirmation:

- navigate menus and pages;
- open tabs, accordions, and search results;
- type and submit site searches;
- select filters and non-binding options;
- draft and prefill board posts, applications, and administrative documents;
- explain the source, route, and current action in the chat rail.

The agent must pause for explicit resident confirmation immediately before an
irreversible or externally consequential action:

- final complaint, application, or board-post submission;
- payment, electronic signature, identity verification, or account creation;
- upload or transmission of personal files or sensitive personal information;
- deletion, cancellation, or modification of an existing official record.

The confirmation boundary is part of the product experience. It must be clear
and confident, not a blanket prohibition on useful agent behavior.

Sensitive personal data must not be persisted in browser storage, analytics,
fixtures, screenshots, or model logs.

## Content freshness

Production answers should be grounded in current official content through a
versioned Buk-gu content adapter. Each answer should carry source URL, retrieval
time, and freshness state internally. When current evidence is missing or
conflicting, the assistant must say so instead of inventing an answer.

The deterministic local journeys remain valuable as reliable presentation
fallbacks, but they are not the final content architecture.

## Clone architecture

- Build page structure and controls as semantic DOM/CSS, not screenshot
  backgrounds or coordinate overlays.
- Use authorized local media for official marks, portraits, banners, photos,
  video, and artwork where DOM recreation would reduce fidelity.
- Keep page routes, content data, and agent actions separate so another district
  can be added through a site adapter rather than a full rewrite.
- Keep a visible distinction between local demo data, cached official data, and
  live official data in diagnostics and operator tooling.
- Preserve keyboard access and reduced-motion behavior even when the primary
  presentation uses rich animation.

## First vertical demonstration

The first polished slice is:

1. Rich Buk-gu entry composition with civic identity and mayor imagery.
2. A resident asks which department handles apartment-related inquiries.
3. The chat surface transitions into the split administrative browser.
4. A visible AI cursor opens `북구소개`, selects `업무 및 전화번호 안내`,
   focuses the search field, types `공동주택`, clicks search, and highlights the
   grounded result.
5. The right rail explains each action and reports the official result.

This slice establishes the interaction language for later writing, application,
document-preparation, and multi-district scenarios.
