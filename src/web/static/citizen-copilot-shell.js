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
  var _isCompactViewport = false;

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
  // Utility: are we in compact (mobile/narrow) viewport?
  // -----------------------------------------------------------------------
  function _isCompact() {
    return window.matchMedia("(max-width: 767px)").matches;
  }

  // -----------------------------------------------------------------------
  // Inert / aria-hidden management for compact drawer
  // -----------------------------------------------------------------------
  function _applyInertToRail(add) {
    if (!_copilotRail) { return; }
    if (add) {
      _copilotRail.setAttribute("inert", "");
      _copilotRail.setAttribute("aria-hidden", "true");
    } else {
      _copilotRail.removeAttribute("inert");
      _copilotRail.setAttribute("aria-hidden", "false");
    }
  }

  // -----------------------------------------------------------------------
  // Dock toggle — switch between left and right (desktop layout only)
  // -----------------------------------------------------------------------
  function _applyDock(dock) {
    _body.setAttribute("data-copilot-dock", dock);
    _currentDock = dock;

    if (_isCompactViewport) {
      // In compact mode, dock-switch closes drawer and applies no other change
      if (_isCompactOpen) {
        _closeCompactDrawer();
      }
    } else {
      // Desktop: close any compact drawer state
      _body.classList.remove("compact-drawer-open");
      _isCompactOpen = false;
      _applyInertToRail(false);
      if (_compactToggle) {
        _compactToggle.setAttribute("aria-expanded", "false");
      }
    }

    if (_dockToggle) {
      _dockToggle.setAttribute(
        "aria-label",
        "패널 위치 전환 — 현재 " + (dock === "right" ? "우측" : "좌측")
      );
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
  // Compact-mode drawer (mobile / narrow viewport)
  // -----------------------------------------------------------------------
  function _openCompactDrawer() {
    _body.classList.add("compact-drawer-open");
    _isCompactOpen = true;
    _applyInertToRail(false);  // make rail interactive
    if (_compactToggle) {
      _compactToggle.setAttribute("aria-expanded", "true");
      _compactToggle.setAttribute("aria-label", "행동 가이드 패널 닫기");
    }
    // Move programmatic focus to the rail (not the toggle)
    if (_copilotRail) {
      _copilotRail.focus();
    }
  }

  // Make Escape collapse compact drawer
  function _closeCompactDrawer() {
    _body.classList.remove("compact-drawer-open");
    _isCompactOpen = false;
    _applyInertToRail(true);  // hide from accessibility tree
    if (_compactToggle) {
      _compactToggle.setAttribute("aria-expanded", "false");
      _compactToggle.setAttribute("aria-label", "행동 가이드 패널 열기");
      _compactToggle.focus();
    }
  }

  function _toggleCompact() {
    if (_isCompactOpen) {
      _closeCompactDrawer();
    } else {
      _openCompactDrawer();
    }
  }

  if (_compactToggle) {
    _compactToggle.addEventListener("click", _toggleCompact);
  }

  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && _isCompactOpen) {
      _closeCompactDrawer();
    }
  });

  // -----------------------------------------------------------------------
  // Viewport-change listener: sync compact state on resize / rotate
  // -----------------------------------------------------------------------
  function _onViewportChange() {
    _isCompactViewport = _isCompact();

    if (_isCompactViewport) {
      if (_isCompactOpen) {
        _applyInertToRail(false);
      } else {
        _applyInertToRail(true);
      }
      _body.classList.remove("compact-drawer-open");
      _isCompactOpen = false;
    } else {
      _body.classList.remove("compact-drawer-open");
      _isCompactOpen = false;
      _applyInertToRail(false);
      if (_compactToggle) {
        _compactToggle.setAttribute("aria-expanded", "false");
      }
    }
  }

  var _viewportMedia = window.matchMedia("(max-width: 767px)");
  if (_viewportMedia.addEventListener) {
    _viewportMedia.addEventListener("change", _onViewportChange);
  } else {
    _viewportMedia.addListener(_onViewportChange);
  }

  // -----------------------------------------------------------------------
  // Confirmation buttons — visual/local only
  // -----------------------------------------------------------------------
  function _handleApprove() {
    var notice = document.getElementById("confirm-notice");
    if (notice) {
      notice.textContent = "확인 완료 — 계속 진행합니다.";
    }
  }

  function _handleCancel() {
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
  // Chat Scenario Chips Bridge (High-fidelity interactive demo flow)
  // -----------------------------------------------------------------------
  var _scenarioChips = document.querySelectorAll(".chat-scenario-chip");
  _scenarioChips.forEach(function (chip) {
    chip.addEventListener("click", function () {
      var scenario = chip.getAttribute("data-scenario");
      var mapping = {
        "illegal-parking": "illegal-parking",
        "public-parking": "public-parking-inconvenience",
        "residential-parking": "residential-parking",
        "traffic-safety": "traffic-or-facility-safety"
      };
      var targetCatId = mapping[scenario];
      if (!targetCatId) return;

      // Find the hidden category button in the DOM and click it to trigger reducer
      var hiddenBtn = document.querySelector('button[data-journey-category-id="' + targetCatId + '"]');
      if (hiddenBtn) {
        hiddenBtn.click();

        // Style the clicked chip
        _scenarioChips.forEach(function (c) { c.classList.remove("chat-scenario-chip--active"); });
        chip.classList.add("chat-scenario-chip--active");

        // Append user bubble to thread
        var chatThread = document.getElementById("chat-thread");
        if (chatThread) {
          var oldBubble = document.getElementById("dynamic-user-bubble");
          if (oldBubble) oldBubble.remove();

          var wrapper = document.createElement("div");
          wrapper.id = "dynamic-user-bubble";
          wrapper.className = "chat-bubble-wrapper chat-bubble-wrapper--user";
          wrapper.innerHTML =
            '<div class="chat-bubble-avatar">👤</div>' +
            '<div class="chat-bubble chat-bubble--user">' +
              chip.textContent.trim() + ' 시나리오에 대해 안내해 주세요.' +
            '</div>';

          // Insert user bubble right after welcome bubble (before scenarios grid)
          var welcomeBubble = chatThread.querySelector(".chat-bubble-wrapper--assistant");
          if (welcomeBubble && welcomeBubble.nextSibling) {
            chatThread.insertBefore(wrapper, welcomeBubble.nextSibling);
          } else {
            chatThread.appendChild(wrapper);
          }

          // Scroll down
          var content = document.querySelector(".chat-content");
          if (content) content.scrollTop = content.scrollHeight;
        }
      }
    });
  });

  // -----------------------------------------------------------------------
  // Initialize
  // -----------------------------------------------------------------------
  _isCompactViewport = _isCompact();

  var initialDock = _body.getAttribute("data-copilot-dock") || "right";
  if (initialDock === "left" || initialDock === "right") {
    _applyDock(initialDock);
  } else {
    _applyDock("right");
  }

  if (_isCompactViewport && !_isCompactOpen) {
    _applyInertToRail(true);
  }

  // Export close method for accessibility tests
  window._closeCompactDrawer = _closeCompactDrawer;

})();
