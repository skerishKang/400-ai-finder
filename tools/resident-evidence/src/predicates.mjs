// tools/resident-evidence/src/predicates.mjs
//
// Reusable predicate combinators for DOM/runtime state verification.
// Each combinator returns a function (page) => Promise<{passed: boolean, detail: string}>.
// Predicates are designed to be composed into state-spec predicate bundles.

/**
 * @typedef {Object} PredicateResult
 * @property {boolean} passed - whether the predicate held
 * @property {string} detail - human-readable explanation
 */

/**
 * Check that a body attribute equals an expected value (or is absent when expected is null).
 * @param {string} attr - body attribute name (without data- prefix)
 * @param {string|null} expected - expected value; null means attribute must be absent
 * @returns {(page: import('playwright').Page) => Promise<PredicateResult>}
 */
export function bodyAttrIs(attr, expected) {
  const fullAttr = attr.startsWith("data-") ? attr : `data-${attr}`;
  return async (page) => {
    const actual = await page.getAttribute("body", fullAttr);
    if (expected === null) {
      return {
        passed: actual === null,
        detail: `body[${fullAttr}] expected absent, got ${JSON.stringify(actual)}`,
      };
    }
    return {
      passed: actual === expected,
      detail: `body[${fullAttr}] expected "${expected}", got ${JSON.stringify(actual)}`,
    };
  };
}

/**
 * Check that a body attribute is NOT a specific value.
 * @param {string} attr - attribute name
 * @param {string} forbidden - value that must NOT be present
 */
export function bodyAttrIsNot(attr, forbidden) {
  const fullAttr = attr.startsWith("data-") ? attr : `data-${attr}`;
  return async (page) => {
    const actual = await page.getAttribute("body", fullAttr);
    return {
      passed: actual !== forbidden,
      detail: `body[${fullAttr}] must not be "${forbidden}", got ${JSON.stringify(actual)}`,
    };
  };
}

/**
 * Check that a selector exists in the DOM.
 * @param {string} selector
 */
export function selectorExists(selector) {
  return async (page) => {
    const count = await page.locator(selector).count();
    return {
      passed: count > 0,
      detail: `selector ${selector} exists: ${count > 0} (count=${count})`,
    };
  };
}

/**
 * Check that a selector does NOT exist in the DOM.
 * @param {string} selector
 */
export function selectorAbsent(selector) {
  return async (page) => {
    const count = await page.locator(selector).count();
    return {
      passed: count === 0,
      detail: `selector ${selector} absent: ${count === 0} (count=${count})`,
    };
  };
}

/**
 * Check that a selector is visible (non-zero bounding box, not display:none/visibility:hidden).
 * @param {string} selector
 */
export function selectorVisible(selector) {
  return async (page) => {
    const el = page.locator(selector).first();
    const exists = await el.count() > 0;
    if (!exists) {
      return { passed: false, detail: `selector ${selector} does not exist` };
    }
    const visible = await el.isVisible();
    const box = await el.boundingBox();
    return {
      passed: visible && box !== null && box.width > 0 && box.height > 0,
      detail: `selector ${selector} visible: ${visible && box !== null && box.width > 0 && box.height > 0}`,
    };
  };
}

/**
 * Check that a selector is NOT visible.
 * @param {string} selector
 */
export function selectorNotVisible(selector) {
  return async (page) => {
    const el = page.locator(selector).first();
    const exists = await el.count() > 0;
    if (!exists) {
      return { passed: true, detail: `selector ${selector} does not exist (not visible)` };
    }
    const visible = await el.isVisible();
    const box = await el.boundingBox();
    const actuallyVisible = visible && box !== null && box.width > 0 && box.height > 0;
    return {
      passed: !actuallyVisible,
      detail: `selector ${selector} not visible: ${!actuallyVisible}`,
    };
  };
}

/**
 * Check that an input/textarea element has a non-empty value.
 * @param {string} selector
 */
export function inputValueNonEmpty(selector) {
  return async (page) => {
    const el = page.locator(selector).first();
    const exists = await el.count() > 0;
    if (!exists) {
      return { passed: false, detail: `element ${selector} does not exist` };
    }
    const value = await el.inputValue();
    return {
      passed: value !== null && value.length > 0,
      detail: `${selector} value non-empty: ${value !== null && value.length > 0} (len=${value ? value.length : 0})`,
    };
  };
}

/**
 * Check that an element is disabled.
 * @param {string} selector
 */
export function elementDisabled(selector) {
  return async (page) => {
    const el = page.locator(selector).first();
    const exists = await el.count() > 0;
    if (!exists) {
      return { passed: false, detail: `element ${selector} does not exist` };
    }
    const disabled = await el.isDisabled();
    const ariaDisabled = await el.getAttribute("aria-disabled");
    return {
      passed: disabled || ariaDisabled === "true",
      detail: `${selector} disabled: ${disabled || ariaDisabled === "true"}`,
    };
  };
}

/**
 * Check that visible page text contains a specific string.
 * Uses a scoped text scan to avoid expensive full-body scans where possible.
 * @param {string} text - exact substring to find in visible text
 * @param {string} [scope] - optional CSS selector to scope the text search
 */
export function visibleTextContains(text, scope = "body") {
  return async (page) => {
    const found = await page.evaluate(
      ({ text, scope }) => {
        const root = document.querySelector(scope) || document.body;
        const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
          acceptNode(node) {
            const el = node.parentElement;
            if (!el) return NodeFilter.FILTER_REJECT;
            const style = window.getComputedStyle(el);
            if (style.display === "none" || style.visibility === "hidden") return NodeFilter.FILTER_REJECT;
            const rect = el.getBoundingClientRect();
            if (rect.width === 0 || rect.height === 0) return NodeFilter.FILTER_REJECT;
            return node.textContent.includes(text) ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT;
          },
        });
        return walker.nextNode() !== null;
      },
      { text, scope },
    );
    return {
      passed: found,
      detail: `visible text contains "${text}": ${found}`,
    };
  };
}

/**
 * Check that visible page text does NOT contain a specific string.
 * @param {string} text - substring that must NOT be present in visible text
 * @param {string} [scope] - optional CSS selector to scope the text search
 */
export function visibleTextAbsent(text, scope = "body") {
  return async (page) => {
    const predicate = visibleTextContains(text, scope);
    const result = await predicate(page);
    return {
      passed: !result.passed,
      detail: `visible text absent "${text}": ${!result.passed}`,
    };
  };
}

/**
 * Check that an element's text content contains a specific string.
 * @param {string} selector
 * @param {string} text
 */
export function elementTextContains(selector, text) {
  return async (page) => {
    const el = page.locator(selector).first();
    const exists = await el.count() > 0;
    if (!exists) {
      return { passed: false, detail: `element ${selector} does not exist` };
    }
    const content = await el.textContent();
    return {
      passed: content !== null && content.includes(text),
      detail: `${selector} text contains "${text}": ${content !== null && content.includes(text)}`,
    };
  };
}

/**
 * Check that an element's aria attribute equals an expected value.
 * @param {string} selector
 * @param {string} attr - aria attribute name (e.g. "aria-pressed")
 * @param {string} expected
 */
export function ariaIs(selector, attr, expected) {
  return async (page) => {
    const el = page.locator(selector).first();
    const exists = await el.count() > 0;
    if (!exists) {
      return { passed: false, detail: `element ${selector} does not exist` };
    }
    const actual = await el.getAttribute(attr);
    return {
      passed: actual === expected,
      detail: `${selector}[${attr}] expected "${expected}", got ${JSON.stringify(actual)}`,
    };
  };
}

/**
 * Run a list of predicates and collect all results.
 * Returns {allPassed, results}.
 * @param {import('playwright').Page} page
 * @param {Array<{name: string, check: (page: import('playwright').Page) => Promise<PredicateResult>}>} predicates
 */
export async function evaluatePredicates(page, predicates) {
  const results = [];
  let allPassed = true;
  for (const { name, check } of predicates) {
    const result = await check(page);
    results.push({ name, ...result });
    if (!result.passed) allPassed = false;
  }
  return { allPassed, results };
}
