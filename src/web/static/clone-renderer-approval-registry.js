/**
 * Clone renderer approval registry (#1198).
 *
 * Repository-controlled, build-embedded metadata. Not fetched at runtime.
 *
 * Separates:
 *   approval_baseline  — which human decision (#1197 / PR #1200) authorized
 *                        the designed-home resident default
 *   current_renderer_integrity — marker-boundary SHA of today's source
 *   visual_equivalence — why current source remains visual-equivalent to
 *                        the #1197 baseline without inventing a new owner approval
 *
 * Does not invent a new project-owner visual approval event.
 */
(function (root) {
  "use strict";

  var APPROVED_HOME_RENDERER_ID = "bukgu_gwangju.home.designed.approved";
  var FIXTURE_HOME_RENDERER_ID = "bukgu_gwangju.home.fixture.candidate";

  root.__CLONE_RENDERER_APPROVAL_REGISTRY__ = Object.freeze({
    schema_version: 1,
    registry_kind: "clone_renderer_approval_registry",
    registry_id: "clone-renderer-approval-registry.v1",
    site_id: "bukgu_gwangju",
    routes: Object.freeze({
      home: Object.freeze({
        site_id: "bukgu_gwangju",
        route_id: "home",
        resident_default_renderer_id: APPROVED_HOME_RENDERER_ID,
        renderers: Object.freeze({
          "bukgu_gwangju.home.designed.approved": Object.freeze({
            site_id: "bukgu_gwangju",
            route_id: "home",
            renderer_id: APPROVED_HOME_RENDERER_ID,
            renderer_source_path: "src/web/static/citizen-action-demo-canvas.js",
            renderer_symbol: "_renderApprovedHome",
            contract_marker_begin: "CLONE_APPROVED_HOME_RENDERER_BEGIN",
            contract_marker_end: "CLONE_APPROVED_HOME_RENDERER_END",
            approval_state: "resident_default_approved",
            visual_review_state: "visual_review_approved",
            resident_default_approved: true,
            exact: false,
            preview_only: false,
            // Human decision that authorized this resident default.
            // This is NOT the current branch head SHA and NOT the current
            // source integrity hash.
            approval_baseline: Object.freeze({
              issue: "#1197",
              pull_request: "#1200",
              commit: "87db3e1ce7d01646a8fc0e8eed6ce2fc63b7ebaa",
              decision: "restore_approved_designed_home",
              note:
                "Records the completed #1197 / PR #1200 restoration decision; " +
                "does not invent a new project-owner visual approval artifact. " +
                "This commit is the approval baseline identity, not a claim that " +
                "today's source bytes equal that commit's source bytes.",
            }),
            // Legacy read-compat mirror of approval_baseline only.
            // NOT an authorization source: resident-default selection requires
            // canonical approval_baseline (legacy alone cannot approve).
            approval_provenance: Object.freeze({
              issue: "#1197",
              pull_request: "#1200",
              decision: "restore_approved_designed_home",
              note:
                "Legacy read-compatibility mirror of approval_baseline. " +
                "Not used for resident-default authorization. " +
                "approved_source_commit is the #1197 baseline commit identity, " +
                "not the current source integrity hash.",
              approved_source_commit:
                "87db3e1ce7d01646a8fc0e8eed6ce2fc63b7ebaa",
            }),
            rollback_renderer_identity: APPROVED_HOME_RENDERER_ID,
            // Canonical current repository source integrity (marker-boundary SHA).
            // Independent of approval_baseline.commit. Authorization source.
            current_renderer_integrity: Object.freeze({
              algorithm: "sha256",
              extraction: "marker_boundary",
              source_path: "src/web/static/citizen-action-demo-canvas.js",
              marker_begin: "CLONE_APPROVED_HOME_RENDERER_BEGIN",
              marker_end: "CLONE_APPROVED_HOME_RENDERER_END",
              sha256:
                "9af7315fa70e0e9db93a75b0117598e21204f541e689df8773915da8cf294d91",
            }),
            // Legacy read-compat mirror of current_renderer_integrity only.
            // NOT an authorization source: selection requires
            // current_renderer_integrity (legacy alone cannot approve).
            renderer_integrity: Object.freeze({
              algorithm: "sha256",
              extraction: "marker_boundary",
              source_path: "src/web/static/citizen-action-demo-canvas.js",
              marker_begin: "CLONE_APPROVED_HOME_RENDERER_BEGIN",
              marker_end: "CLONE_APPROVED_HOME_RENDERER_END",
              sha256:
                "9af7315fa70e0e9db93a75b0117598e21204f541e689df8773915da8cf294d91",
            }),
            // Canonical visual-equivalence record (authorization source).
            visual_equivalence: Object.freeze({
              status: "equivalent_to_approval_baseline",
              reason:
                "#1198 adds fail-closed selection metadata only; visible " +
                "designed-home composition remains equivalent to the #1197 baseline.",
              baseline_manifest:
                "tests/fixtures/clone_approved_home_visual_baseline.json",
              allowed_normalize_attributes: Object.freeze([
                "data-renderer-id",
                "data-visual-review-state",
                "data-resident-default-approved",
              ]),
              supersession_allowed: false,
            }),
          }),
          "bukgu_gwangju.home.fixture.candidate": Object.freeze({
            site_id: "bukgu_gwangju",
            route_id: "home",
            renderer_id: FIXTURE_HOME_RENDERER_ID,
            renderer_source_path: "src/web/static/citizen-action-demo-canvas.js",
            renderer_symbol: "_renderHomeFixtureProjection",
            fixture_id: "bukgu_gwangju.home.clone.2026-07-15",
            fixture_sha256:
              "81b27b98fadc091ca852079f89ea93da45b93f250372835b8b352726b2faeaed",
            capture_state: "capture_required",
            structure_state: "structure_ready",
            asset_state: "unresolved",
            unresolved_asset_count: 174,
            interaction_state: null,
            visual_review_state: "visual_review_pending",
            approval_state: "visual_review_pending",
            resident_default_approved: false,
            exact: false,
            preview_only: true,
            readiness: Object.freeze({
              capture: "capture_required",
              structure: "structure_ready",
              asset_mapping: "unresolved",
              interaction: null,
              visual_review: "visual_review_pending",
              resident_default: false,
              exact: false,
            }),
          }),
        }),
      }),
    }),
  });

  root.__CLONE_RENDERER_APPROVAL_IDS__ = Object.freeze({
    APPROVED_HOME_RENDERER_ID: APPROVED_HOME_RENDERER_ID,
    FIXTURE_HOME_RENDERER_ID: FIXTURE_HOME_RENDERER_ID,
  });
})(typeof window !== "undefined" ? window : globalThis);
