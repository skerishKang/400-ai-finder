/**
 * citizen-copilot-shell.js
 * Dockable citizen-action copilot shell — client-side only.
 *
 * Privacy/safety guarantees:
 * - No localStorage, sessionStorage, indexedDB, cookies, or analytics.
 * - No fetch, XMLHttpRequest, WebSocket, EventSource, navigator.sendBeacon.
 * - No provider import, runner invocation, DOM automation, or external URLs.
 * - No login, identity, upload, payment, or final-submission controls.
 * - All content is local placeholder/demo — no personal data collection.
 */

(function () {
  "use strict";

  // -----------------------------------------------------------------------
  // State
  // -----------------------------------------------------------------------
  /** @type {'left' | 'right'} */
  var _currentDock = "right";
  var _isCompactOpen = false;

  // -----------------------------------------------------------------------
  // DOM references
  // -----------------------------------------------------------------------
  var _body = document.body;
  var _dockToggle = document.getElementById("dock-toggle");
  var _compactToggle = document.getElementById("compact-toggle");
  var _copilotRail = document.getElementById("copilot-rail");
  var _confirmApprove = document.getElementById("btn-confirm-approve");
  var _confirmCancel = document.getElementById("btn-confirm-cancel");

  // -----------------------------------------------------------------------
  // Dock toggle — switch between left and right
  // -----------------------------------------------------------------------
  function _applyDock(dock) {
    _body.setAttribute("data-copilot-dock", dock);
    _currentDock = dock;
    // Remove compact open state when switching dock on desktop
    _body.classList.remove("compact-drawer-open");
    _isCompactOpen = false;
    if (_compactToggle) {
      _compactToggle.setAttribute("aria-expanded", "false");
    }
    if (_dockToggle) {
      _dockToggle.setAttribute("aria-label", "패널 위치 전환 — 현재 " + (dock === "right" ? "우측" : "좌측"));
    }
  }

  function _toggleDock() {
    var next = _currentDock === "right" ? "left" : "right";
    _applyDock(next);
  }

  if (_dockToggle) {
    _dockToggle.addEventListener("click", _toggleDock);
  }

  // -----------------------------------------------------------------------
  // Compact-mode drawer (mobile/ narrow viewport)
  // -----------------------------------------------------------------------
  function _openCompact() {
    _body.classList.add("compact-drawer-open");
    _isCompactOpen = true;
    if (_compactToggle) {
      _compactToggle.setAttribute("aria-expanded", "true");
      _compactToggle.setAttribute("aria-label", "행동 가이드 패널 닫기");
      _compactToggle.focus();
    }
  }

  function _closeCompact() {
    _body.classList.remove("compact-drawer-open");
    _isCompactOpen = false;
    if (_compactToggle) {
      _compactToggle.setAttribute("aria-expanded", "false");
      _compactToggle.setAttribute("aria-label", "행동 가이드 패널 열기");
      _compactToggle.focus();
    }
  }

  function _toggleCompact() {
    if (_isCompactOpen) {
      _closeCompact();
    } else {
      _openCompact();
    }
  }

  if (_compactToggle) {
    _compactToggle.addEventListener("click", _toggleCompact);
  }

  // Escape key collapses open compact drawer
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && _isCompactOpen) {
      _closeCompact();
    }
  });

  // -----------------------------------------------------------------------
  // Confirmation buttons — visual/local only
  // -----------------------------------------------------------------------
  function _handleApprove() {
    // Visual feedback only — no submit, navigate, send, or plan trigger
    var notice = document.getElementById("confirm-notice");
    if (notice) {
      notice.textContent = "확인 완료 — 계속 진행합니다.";
    }
  }

  function _handleCancel() {
    // Visual feedback only — no submit, navigate, send, or plan trigger
    var notice = document.getElementById("confirm-notice");
    if (notice) {
      notice.textContent = "취소되었습니다.";
    }
  }

  if (_confirmApprove) {
    _confirmApprove.addEventListener("click", _handleApprove);
  }
  if (_confirmCancel) {
    _confirmCancel.addEventListener("click", _handleCancel);
  }

  // -----------------------------------------------------------------------
  // Demo canvas buttons — visual simulation only
  // -----------------------------------------------------------------------
  var _canvasBtnPrefill = document.getElementById("canvas-btn-prefill");
  var _canvasBtnReset = document.getElementById("canvas-btn-reset");

  if (_canvasBtnPrefill) {
    _canvasBtnPrefill.addEventListener("click", function () {
      var placeholder = document.querySelector(".demo-canvas__placeholder");
      if (placeholder) {
        placeholder.style.opacity = "0.5";
        setTimeout(function () {
          placeholder.style.opacity = "1";
        }, 600);
      }
    });
  }

  if (_canvasBtnReset) {
    _canvasBtnReset.addEventListener("click", function () {
      var notice = document.getElementById("confirm-notice");
      if (notice) notice.textContent = "확인이 필요합니다. 계속 진행하려면 사용자의 확인이 필요합니다.";
      var explanation = document.getElementById("current-explanation");
      if (explanation) explanation.textContent = "해당 페이지로 이동합니다.";
    });
  }

  // -----------------------------------------------------------------------
  // Choice buttons — visual demo only, no data submission
  // -----------------------------------------------------------------------
  var _choiceBtns = document.querySelectorAll(".choice-btn");
  _choiceBtns.forEach(function (btn) {
    btn.addEventListener("click", function () {
      // Visual highlight only — no network, no provider call
      _choiceBtns.forEach(function (b) { b.style.fontWeight = ""; });
      btn.style.fontWeight = "700";
    });
  });

  // -----------------------------------------------------------------------
  // Initialize dock from current body attribute (default: right)
  // -----------------------------------------------------------------------
  var initialDock = _body.getAttribute("data-copilot-dock") || "right";
  if (initialDock === "left" || initialDock === "right") {
    _applyDock(initialDock);
  } else {
    _applyDock("right");
  }

})();