/**
 * content-script.js — MV3 local fixture transport/validation scaffold.
 *
 * This file is a transport/validation scaffold only.
 * It does NOT execute DOM clicks, scrolls, route navigation, or draft prefill.
 *
 * Responsibilities:
 * 1. Check protocol global exists
 * 2. Guard that page is a local fixture
 * 3. Add an active status marker (local fixture only)
 * 4. Listen on chrome.runtime.onMessage
 * 5. Delegate to protocol.validateActionMessage() and return result
 *
 * Banned: window.addEventListener("message"), window.postMessage, fetch,
 * XMLHttpRequest, WebSocket, chrome.storage, localStorage, sessionStorage,
 * indexedDB, document.cookie, eval, Function, import(), window.open,
 * location.assign, element.click, scrollIntoView, innerHTML, etc.
 */

(function () {
  "use strict";

  // ========================================================================
  // Protocol guard
  // ========================================================================
  if (typeof window.CitizenActionMV3LocalBridgeProtocol === "undefined") {
    return;
  }

  var protocol = window.CitizenActionMV3LocalBridgeProtocol;

  // ========================================================================
  // Active marker — added only when on a local fixture page
  // ========================================================================
  if (protocol.isLocalFixtureLocation(window.location)) {
    var marker = document.createElement("div");
    marker.id = "citizen-action-mv3-local-bridge-status";
    marker.setAttribute("role", "status");
    marker.setAttribute("data-state", "active");
    marker.textContent =
      "MV3 로컬 브리지 활성 · 로컬 fixture에서만 심볼릭 action을 검증합니다.";
    // Append to body; if body not yet available, append to document.documentElement
    var target = document.body || document.documentElement;
    target.appendChild(marker);
  }

  // ========================================================================
  // Fixture-only guard — exit early if not on a local fixture
  // ========================================================================
  if (!protocol.isLocalFixtureLocation(window.location)) {
    return;
  }

  // ========================================================================
  // chrome.runtime.onMessage listener — MV3 standard pattern
  // ========================================================================
  chrome.runtime.onMessage.addListener(function (message, sender, sendResponse) {
    // Validate using protocol
    var result = protocol.validateActionMessage(message);

    if (result.ok) {
      sendResponse({ status: "accepted", action: result.action });
    } else {
      sendResponse({ status: "blocked", reason_code: result.reason_code });
    }

    // Return false to indicate synchronous sendResponse (MV3 requirement)
    return false;
  });

})();