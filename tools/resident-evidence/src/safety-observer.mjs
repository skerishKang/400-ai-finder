// tools/resident-evidence/src/safety-observer.mjs
//
// Safety observer — monitors external requests, failed requests, console
// errors, and page errors during controlled browser runs.
//
// Controlled test runs require: external_origin_requests = 0
//
// Never serializes cookies, auth headers, tokens, secrets, or PII.

const LOCAL_HOSTS = new Set(["127.0.0.1", "localhost", "::1"]);

/**
 * Classify a URL as local, browser-internal, or external.
 * @param {string} url
 * @returns {"local" | "browser-internal" | "external" | "unparseable"}
 */
export function classifyUrl(url) {
  if (!url) return "unparseable";
  try {
    const u = new URL(url);
    const host = u.hostname.replace(/^\[|\]$/g, "");
    if (LOCAL_HOSTS.has(host)) return "local";
    if (u.protocol === "data:" || u.protocol === "blob:") return "browser-internal";
    return "external";
  } catch {
    return "unparseable";
  }
}

/**
 * Attach safety observers to a page.
 * Returns a handle with methods to get counts and detach.
 *
 * @param {import('playwright').Page} page
 * @returns {{getCounts: () => Object, getExternalRequests: () => Array, detach: () => void}}
 */
export function attachSafetyObserver(page) {
  const externalRequests = [];
  const failedRequests = [];
  const consoleErrors = [];
  const pageErrors = [];

  const onRequest = (request) => {
    const url = request.url();
    if (classifyUrl(url) === "external") {
      externalRequests.push({ url, resourceType: request.resourceType() });
    }
  };

  const onResponse = (response) => {
    const status = response.status();
    if (status >= 400) {
      const url = response.url();
      if (classifyUrl(url) === "local") {
        failedRequests.push({ url: url.replace(/\?.*$/, ""), status });
      }
    }
  };

  const onConsole = (msg) => {
    if (msg.type() === "error") {
      consoleErrors.push(msg.text().slice(0, 500));
    }
  };

  const onPageError = (error) => {
    pageErrors.push(String(error.message || error).slice(0, 500));
  };

  page.on("request", onRequest);
  page.on("response", onResponse);
  page.on("console", onConsole);
  page.on("pageerror", onPageError);

  return {
    getCounts() {
      return {
        externalOriginRequests: externalRequests.length,
        failedRequests: failedRequests.length,
        consoleErrors: consoleErrors.length,
        pageErrors: pageErrors.length,
        externalRequestUrls: [...externalRequests],
        failedRequestDetails: [...failedRequests],
        consoleErrorTexts: [...consoleErrors],
        pageErrorTexts: [...pageErrors],
      };
    },

    getExternalRequests() {
      return [...externalRequests];
    },

    detach() {
      page.off("request", onRequest);
      page.off("response", onResponse);
      page.off("console", onConsole);
      page.off("pageerror", onPageError);
    },
  };
}

/**
 * Assert that a controlled run has zero external-origin requests.
 * @param {Object} counts — from getCounts()
 * @throws if externalOriginRequests > 0
 */
export function assertZeroExternalRequests(counts) {
  if (counts.externalOriginRequests > 0) {
    const urls = counts.externalRequestUrls.map((r) => r.url).join(", ");
    throw new Error(
      `SAFETY VIOLATION: external-origin requests detected (${counts.externalOriginRequests}): ${urls}`,
    );
  }
}
