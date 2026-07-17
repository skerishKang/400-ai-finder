/**
 * Clone renderer approval registry (#1198).
 *
 * Repository-controlled, build-embedded metadata. Not fetched at runtime.
 * Records existing #1197 / PR #1200 restoration provenance only — does not
 * invent a new project-owner visual approval event.
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
            approval_provenance: Object.freeze({
              issue: "#1197",
              pull_request: "#1200",
              decision: "restore_approved_designed_home",
              note:
                "Records the completed #1197 / PR #1200 restoration decision; " +
                "does not invent a new project-owner visual approval artifact.",
              approved_source_commit:
                "87db3e1ce7d01646a8fc0e8eed6ce2fc63b7ebaa",
            }),
            rollback_renderer_identity: APPROVED_HOME_RENDERER_ID,
            renderer_integrity: Object.freeze({
              algorithm: "sha256",
              extraction: "marker_boundary",
              source_path: "src/web/static/citizen-action-demo-canvas.js",
              marker_begin: "CLONE_APPROVED_HOME_RENDERER_BEGIN",
              marker_end: "CLONE_APPROVED_HOME_RENDERER_END",
              // Marker-boundary SHA-256 of _renderApprovedHome source (exclusive of marker lines).
              sha256:
                "9af7315fa70e0e9db93a75b0117598e21204f541e689df8773915da8cf294d91",
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
