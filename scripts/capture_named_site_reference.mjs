#!/usr/bin/env node
/**
 * Operator-only bounded named-site reference capture (#1303 Gate G1).
 *
 * Safety defaults:
 * - no live network unless --allow-live is explicitly supplied
 * - refuse live capture when CI=true
 * - HTTPS + exact approved host only
 * - browser network requests are GET-only; other methods are aborted
 * - no login, form submission, payment, PII entry, provider APIs, or mutation
 *
 * Routine CI should import/test pure helpers only and must never pass --allow-live.
 */

import crypto from 'node:crypto';
import fs from 'node:fs/promises';
import path from 'node:path';
import process from 'node:process';
import { pathToFileURL } from 'node:url';

export const CAPTURE_MODE = 'controlled_read_only_reference';
const USER_AGENT = '400-ai-finder-named-site-reference/1.0 (bounded read-only capture)';
const DEFAULT_PLAN = 'configs/reference-plans/seogu_gwangju.json';
const DEFAULT_ROOT = 'data/official_captures';
const RESOURCE_TYPES = new Set(['stylesheet', 'script', 'image', 'font', 'media']);
const MAX_ASSET_BODIES = 100;
const MAX_EXCEPTIONS = 100;

export class CapturePolicyError extends Error {}

export function sha256Bytes(bytes) {
  return crypto.createHash('sha256').update(bytes).digest('hex');
}

export function assertSafeId(value, label = 'id') {
  if (typeof value !== 'string' || !/^[a-z0-9][a-z0-9._-]*$/.test(value)) {
    throw new CapturePolicyError(`${label} has unsafe characters`);
  }
  return value;
}

export function normalizeAllowedHosts(hosts) {
  if (!Array.isArray(hosts) || hosts.length === 0) {
    throw new CapturePolicyError('allowed_hosts must be a non-empty array');
  }
  const out = hosts.map((host) => {
    if (typeof host !== 'string' || host.length === 0 || host !== host.toLowerCase()) {
      throw new CapturePolicyError('allowed_hosts must contain lowercase hostnames');
    }
    if (!/^[a-z0-9.-]+$/.test(host)) {
      throw new CapturePolicyError(`invalid allowed host: ${host}`);
    }
    return host;
  });
  if (new Set(out).size !== out.length) {
    throw new CapturePolicyError('allowed_hosts must be unique');
  }
  return new Set(out);
}

export function assertApprovedHttpsUrl(value, allowedHosts, label = 'url') {
  if (typeof value !== 'string' || value.length === 0) {
    throw new CapturePolicyError(`${label} must be a non-empty string`);
  }
  let parsed;
  try {
    parsed = new URL(value);
  } catch {
    throw new CapturePolicyError(`${label} must be an absolute URL`);
  }
  if (parsed.protocol !== 'https:') {
    throw new CapturePolicyError(`${label} must use https`);
  }
  if (parsed.username || parsed.password) {
    throw new CapturePolicyError(`${label} must not contain userinfo`);
  }
  if (parsed.port && parsed.port !== '443') {
    throw new CapturePolicyError(`${label} must not override the HTTPS port`);
  }
  if (!allowedHosts.has(parsed.hostname.toLowerCase())) {
    throw new CapturePolicyError(`${label} host is not exactly approved: ${parsed.hostname}`);
  }
  if (parsed.hash) {
    throw new CapturePolicyError(`${label} must not contain a fragment`);
  }
  return parsed.href;
}

export function assertPlanForLiveCapture(plan) {
  if (!plan || typeof plan !== 'object' || Array.isArray(plan)) {
    throw new CapturePolicyError('plan must be an object');
  }
  if (plan.capture_mode !== CAPTURE_MODE) {
    throw new CapturePolicyError(`capture_mode must be ${CAPTURE_MODE}`);
  }
  assertSafeId(plan.plan_id, 'plan_id');
  assertSafeId(plan.site_id, 'site_id');
  const allowedHosts = normalizeAllowedHosts(plan.allowed_hosts);
  if (JSON.stringify(plan.allowed_methods) !== JSON.stringify(['GET'])) {
    throw new CapturePolicyError("allowed_methods must be exactly ['GET']");
  }
  if (plan?.routine_ci?.network_policy !== 'offline') {
    throw new CapturePolicyError('routine_ci.network_policy must be offline');
  }
  const boundary = plan.security_boundary ?? {};
  for (const [key, value] of Object.entries(boundary)) {
    if (value !== false) {
      throw new CapturePolicyError(`security_boundary.${key} must be false`);
    }
  }
  const requiredBoundaryKeys = [
    'post_allowed',
    'form_submission_allowed',
    'login_allowed',
    'payment_allowed',
    'identity_verification_allowed',
    'pii_entry_allowed',
    'personal_file_upload_allowed',
    'actual_site_mutation_allowed',
  ];
  for (const key of requiredBoundaryKeys) {
    if (!(key in boundary)) throw new CapturePolicyError(`security_boundary.${key} missing`);
  }
  if (!Array.isArray(plan.states) || plan.states.length === 0) {
    throw new CapturePolicyError('states must be a non-empty array');
  }
  const seen = new Set();
  for (const state of plan.states) {
    assertSafeId(state.state_id, 'state_id');
    if (seen.has(state.state_id)) throw new CapturePolicyError(`duplicate state_id: ${state.state_id}`);
    seen.add(state.state_id);
    assertApprovedHttpsUrl(state.source_seed_url, allowedHosts, `${state.state_id}.source_seed_url`);
    if (!Number.isInteger(state?.viewport?.width) || state.viewport.width <= 0) {
      throw new CapturePolicyError(`${state.state_id}.viewport.width must be positive integer`);
    }
    if (!Number.isInteger(state?.viewport?.height) || state.viewport.height <= 0) {
      throw new CapturePolicyError(`${state.state_id}.viewport.height must be positive integer`);
    }
    if (typeof state?.state?.name !== 'string' || !state.state.name) {
      throw new CapturePolicyError(`${state.state_id}.state.name missing`);
    }
    if (!Array.isArray(state.required_artifacts) || state.required_artifacts.length === 0) {
      throw new CapturePolicyError(`${state.state_id}.required_artifacts must be non-empty`);
    }
  }
  return allowedHosts;
}

export function parseKeyValueArgs(values, label) {
  const out = new Map();
  for (const raw of values) {
    const index = raw.indexOf('=');
    if (index <= 0 || index === raw.length - 1) {
      throw new CapturePolicyError(`${label} must use state_id=value: ${raw}`);
    }
    const key = raw.slice(0, index);
    const value = raw.slice(index + 1);
    assertSafeId(key, `${label} state_id`);
    if (out.has(key)) throw new CapturePolicyError(`duplicate ${label} for ${key}`);
    out.set(key, value);
  }
  return out;
}

export function sanitizePublicHtml(input) {
  if (typeof input !== 'string') throw new TypeError('html input must be string');
  let text = input.replace(/\r\n?/g, '\n').replace(/\t/g, '    ');
  text = text
    .split('\n')
    .map((line) => line.replace(/[ \t]+$/g, ''))
    .join('\n');
  const redacted = '[REDACTED_SESSION_CSRF]';
  text = text.replace(/(<meta\b[^>]*\bname\s*=\s*["']?_csrf["']?[^>]*\bcontent\s*=\s*["'])[^"']*(["'])/gi, `$1${redacted}$2`);
  text = text.replace(/(<meta\b[^>]*\bcontent\s*=\s*["'])[^"']*(["'][^>]*\bname\s*=\s*["']?_csrf["']?)/gi, `$1${redacted}$2`);
  text = text.replace(/(<input\b[^>]*\bname\s*=\s*["']?_csrf["']?[^>]*\bvalue\s*=\s*["'])[^"']*(["'])/gi, `$1${redacted}$2`);
  text = text.replace(/(<input\b[^>]*\bvalue\s*=\s*["'])[^"']*(["'][^>]*\bname\s*=\s*["']?_csrf["']?)/gi, `$1${redacted}$2`);
  // Generic redaction of credential-bearing query parameters (appkey,
  // api_key, apikey, access_token, secret, client_secret) in any URL or
  // src/href attribute. The key NAME is preserved for forensic meaning;
  // only the secret VALUE is replaced with a deterministic token. Handles
  // both raw "&" and HTML-entity "&amp;" separators, and quoted JS string
  // literals passed to SDK init calls (e.g. SomeSdk.init("KEY")).
  // Site/kiosk-agnostic.
  const credQuery = '[REDACTED_QUERY_APPKEY]';
  const credParams = 'appkey|api_key|apikey|access_token|client_secret|secret';
  // URL query param: key=VALUE (value runs until &, ", ', <, or end).
  text = text.replace(
    new RegExp(`([?&](?:${credParams})=)([^&"'<]+)`, 'gi'),
    `$1${credQuery}`,
  );
  // HTML-entity-encoded variant: appkey=VALUE&amp;...
  text = text.replace(
    new RegExp(`([?&amp;](?:${credParams})=)([^&"'<]+)`, 'gi'),
    `$1${credQuery}`,
  );
  // Quoted JS string literal passed to a SDK init-style call:
  // SomeSdk.init('KEY') or SomeSdk.init("KEY").
  text = text.replace(
    new RegExp(`((?:[A-Za-z_][A-Za-z0-9_.]*)\\s*\\(\\s*)(['"])[A-Za-z0-9_-]{12,}(['"])`, 'g'),
    (m, pre, q1, q2) => `${pre}${q1}${credQuery}${q2}`,
  );
  return `${text.replace(/\n+$/g, '')}\n`;
}

export function sanitizeExceptionDetail(detail) {
  // Generic redaction of credential-bearing query parameters in blocked-
  // request exception details (e.g. "GET https://...?appkey=SECRET&...").
  // Preserves the method, URL host/path, and non-credential query params;
  // only the secret value is replaced. Site/kiosk-agnostic.
  if (typeof detail !== 'string') return String(detail ?? '');
  const credQuery = '[REDACTED_QUERY_APPKEY]';
  const credParams = 'appkey|api_key|apikey|access_token|client_secret|secret';
  return detail.replace(
    new RegExp(`([?&](?:${credParams})=)([^&\s"']+)`, 'gi'),
    `$1${credQuery}`,
  );
}

export function pngDimensions(bytes) {
  const buffer = Buffer.from(bytes);
  const signature = '89504e470d0a1a0a';
  if (buffer.length < 24 || buffer.subarray(0, 8).toString('hex') !== signature) {
    throw new CapturePolicyError('screenshot is not a valid PNG header');
  }
  return { width: buffer.readUInt32BE(16), height: buffer.readUInt32BE(20) };
}

export function computeG1Claim(plan, capturedStates) {
  const required = new Set(plan.states.filter((state) => state.capture_required).map((state) => state.state_id));
  const successful = new Set(capturedStates.filter((state) => state.result_status === 'success').map((state) => state.state_id));
  if (required.size !== successful.size) return false;
  for (const stateId of required) if (!successful.has(stateId)) return false;
  return true;
}

export function requestAllowed(method, url, allowedHosts) {
  if (method !== 'GET') return false;
  try {
    assertApprovedHttpsUrl(url, allowedHosts, 'request');
    return true;
  } catch {
    return false;
  }
}

export function kstCaptureId(date = new Date()) {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Seoul', year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
  }).formatToParts(date);
  const get = (type) => parts.find((part) => part.type === type)?.value ?? '00';
  return `${get('year')}${get('month')}${get('day')}T${get('hour')}${get('minute')}${get('second')}-0900`;
}

function parseArgs(argv) {
  const args = {
    plan: DEFAULT_PLAN,
    outRoot: DEFAULT_ROOT,
    captureId: null,
    allowLive: false,
    overrideUrls: [],
    actionSelectors: [],
    settleMs: 1000,
  };
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === '--allow-live') args.allowLive = true;
    else if (arg === '--plan') args.plan = argv[++i];
    else if (arg === '--out-root') args.outRoot = argv[++i];
    else if (arg === '--capture-id') args.captureId = argv[++i];
    else if (arg === '--override-url') args.overrideUrls.push(argv[++i]);
    else if (arg === '--action-selector') args.actionSelectors.push(argv[++i]);
    else if (arg === '--settle-ms') args.settleMs = Number(argv[++i]);
    else if (arg === '--help') args.help = true;
    else throw new CapturePolicyError(`unknown argument: ${arg}`);
  }
  if (!Number.isInteger(args.settleMs) || args.settleMs < 0 || args.settleMs > 15000) {
    throw new CapturePolicyError('--settle-ms must be integer 0..15000');
  }
  return args;
}

function printHelp() {
  console.log(`Usage:\n  node scripts/capture_named_site_reference.mjs --allow-live [options]\n\nOptions:\n  --plan PATH\n  --out-root PATH\n  --capture-id SAFE_ID\n  --override-url state_id=https://approved-host/path\n  --action-selector state_id=CSS_SELECTOR\n  --settle-ms N\n\nWithout --allow-live the command validates the plan and exits without network.`);
}

async function writeJson(file, value) {
  const bytes = Buffer.from(`${JSON.stringify(value, null, 2)}\n`, 'utf8');
  await fs.mkdir(path.dirname(file), { recursive: true });
  await fs.writeFile(file, bytes);
  return { bytes, sha256: sha256Bytes(bytes) };
}

function artifactId(repoRelative) {
  return repoRelative.split(path.sep).join('/');
}

async function captureState({ browser, state, requestedUrl, actionSelector, allowedHosts, stateDir, repoRoot, settleMs }) {
  const exceptions = [];
  const pushException = (entry) => {
    // Sanitize credential-bearing query params in exception details
    // (e.g. blocked-request URLs with appkey=...) before they enter the
    // committed ledger/exception queue. Generic, site-agnostic.
    const sanitized = (entry && typeof entry.detail === 'string')
      ? { ...entry, detail: sanitizeExceptionDetail(entry.detail) }
      : entry;
    if (exceptions.length < MAX_EXCEPTIONS) exceptions.push(sanitized);
    else if (exceptions.length === MAX_EXCEPTIONS) exceptions.push({ code: 'exception_list_truncated', detail: `additional exceptions omitted after ${MAX_EXCEPTIONS}` });
  };
  const publicAssetBodies = new Map();
  const assetTasks = new Set();
  let documentResponse = null;
  const context = await browser.newContext({
    viewport: { width: state.viewport.width, height: state.viewport.height },
    userAgent: USER_AGENT,
    serviceWorkers: 'block',
    ignoreHTTPSErrors: false,
  });
  const page = await context.newPage();
  page.on('response', (response) => {
    const task = (async () => {
      try {
        if (publicAssetBodies.size >= MAX_ASSET_BODIES) return;
        const req = response.request();
        if (req.method() !== 'GET' || !RESOURCE_TYPES.has(req.resourceType())) return;
        const url = response.url();
        if (!requestAllowed('GET', url, allowedHosts) || !response.ok()) return;
        if (publicAssetBodies.has(url)) return;
        const body = await response.body();
        if (publicAssetBodies.size >= MAX_ASSET_BODIES || publicAssetBodies.has(url)) return;
        publicAssetBodies.set(url, {
          url,
          sha256: sha256Bytes(body),
          byte_length: body.length,
          content_type: response.headers()['content-type'] ?? null,
        });
      } catch (error) {
        pushException({ code: 'asset_body_unavailable', detail: String(error?.message ?? error).slice(0, 500) });
      }
    })();
    assetTasks.add(task);
    task.finally(() => assetTasks.delete(task));
  });
  await page.route('**/*', async (route) => {
    const request = route.request();
    const url = request.url();
    if (url.startsWith('data:') || url.startsWith('blob:') || url.startsWith('about:')) {
      await route.continue();
      return;
    }
    if (!requestAllowed(request.method(), url, allowedHosts)) {
      pushException({ code: 'request_blocked_by_capture_policy', detail: `${request.method()} ${url}`.slice(0, 500) });
      await route.abort('blockedbyclient');
      return;
    }
    await route.continue();
  });

  try {
    documentResponse = await page.goto(requestedUrl, { waitUntil: 'domcontentloaded', timeout: 45000 });
    await page.waitForTimeout(settleMs);
    const finalUrl = assertApprovedHttpsUrl(page.url(), allowedHosts, `${state.state_id}.final_url`);

    if (state.state.name === 'gnb_open') {
      const candidates = actionSelector ? [actionSelector] : [
        'button[aria-label*="전체메뉴"]',
        'button[aria-label*="메뉴"]',
        'a[title*="전체메뉴"]',
        'button[title*="전체메뉴"]',
        '[class*="allmenu"] button',
        '[class*="all-menu"] button',
        '[class*="all_menu"] button',
      ];
      let opened = false;
      for (const selector of candidates) {
        try {
          const locator = page.locator(selector).first();
          if (await locator.count() && await locator.isVisible()) {
            await locator.click({ timeout: 3000 });
            await page.waitForTimeout(300);
            opened = true;
            break;
          }
        } catch {
          // Try the next generic selector.
        }
      }
      if (!opened) throw new CapturePolicyError(`unable to open gnb state; pass --action-selector ${state.state_id}=CSS_SELECTOR`);
    }

    if (assetTasks.size) await Promise.allSettled([...assetTasks]);

    const htmlText = sanitizePublicHtml(await page.content());
    const htmlPath = path.join(stateDir, 'source.html');
    const htmlBytes = Buffer.from(htmlText, 'utf8');
    await fs.writeFile(htmlPath, htmlBytes);

    const visibleInventory = await page.evaluate(() => {
      const visible = (el) => {
        const style = getComputedStyle(el);
        const rect = el.getBoundingClientRect();
        return style.visibility !== 'hidden' && style.display !== 'none' && rect.width > 0 && rect.height > 0 && rect.bottom >= 0 && rect.top <= innerHeight;
      };
      const text = (el) => (el.innerText || el.getAttribute('aria-label') || el.getAttribute('title') || '').replace(/\s+/g, ' ').trim().slice(0, 300);
      const take = (selector, max) => Array.from(document.querySelectorAll(selector)).filter(visible).slice(0, max).map((el) => ({
        tag: el.tagName.toLowerCase(), text: text(el), id: el.id || null, class_name: typeof el.className === 'string' ? el.className.slice(0, 300) : null,
      }));
      return {
        title: document.title,
        viewport: { width: innerWidth, height: innerHeight },
        landmarks: take('header,nav,main,footer,aside,section', 100),
        controls: take('a,button,input,select,textarea', 300),
      };
    });
    const inventoryPath = path.join(stateDir, 'visible-region-inventory.json');
    const inventoryWrite = await writeJson(inventoryPath, visibleInventory);

    const assetProvenance = {
      bounded: true,
      max_asset_bodies: MAX_ASSET_BODIES,
      assets: [...publicAssetBodies.values()].sort((a, b) => a.url.localeCompare(b.url)),
    };
    const assetPath = path.join(stateDir, 'public-asset-provenance.json');
    const assetWrite = await writeJson(assetPath, assetProvenance);

    const screenshotPath = path.join(stateDir, 'source.png');
    const screenshotBytes = await page.screenshot({ fullPage: true, type: 'png', animations: 'disabled' });
    await fs.writeFile(screenshotPath, screenshotBytes);
    const dimensions = pngDimensions(screenshotBytes);

    const headers = documentResponse?.headers() ?? {};
    let sourceUpdatedAt = null;
    if (headers['last-modified']) {
      const parsed = new Date(headers['last-modified']);
      if (!Number.isNaN(parsed.valueOf())) sourceUpdatedAt = parsed.toISOString();
    }
    const status = documentResponse?.status() ?? null;
    const relative = (file) => artifactId(path.relative(repoRoot, file));
    const publicAssets = assetProvenance.assets.map((asset, index) => ({
      source_url: asset.url,
      artifact_id: `${state.state_id}/public-asset/${String(index + 1).padStart(3, '0')}`,
      sha256: asset.sha256,
      provenance_note: `browser-observed same-host GET; ${asset.byte_length} bytes; ${asset.content_type ?? 'content-type unknown'}`,
    }));

    await context.close();
    return {
      state_id: state.state_id,
      requested_url: requestedUrl,
      final_url: finalUrl,
      captured_at: new Date().toISOString(),
      source_updated_at: sourceUpdatedAt,
      final_http_status: status,
      viewport: state.viewport,
      state: state.state,
      artifacts: [
        { class: 'html_dom_content', artifact_id: relative(htmlPath), sha256: sha256Bytes(htmlBytes), mime_type: 'text/html; charset=utf-8' },
        { class: 'screenshot', artifact_id: relative(screenshotPath), sha256: sha256Bytes(screenshotBytes), mime_type: 'image/png', dimensions },
        { class: 'visible_region_inventory', artifact_id: relative(inventoryPath), sha256: inventoryWrite.sha256, mime_type: 'application/json' },
        { class: 'public_asset_provenance', artifact_id: relative(assetPath), sha256: assetWrite.sha256, mime_type: 'application/json' },
      ],
      public_assets: publicAssets,
      exceptions,
      result_status: status && status >= 200 && status < 300 ? 'success' : 'partial',
    };
  } catch (error) {
    const finalUrl = (() => {
      try { return assertApprovedHttpsUrl(page.url(), allowedHosts, 'failed.final_url'); } catch { return requestedUrl; }
    })();
    pushException({ code: 'capture_failed', detail: String(error?.message ?? error).slice(0, 1000) });
    const status = documentResponse?.status() ?? null;
    await context.close();
    return {
      state_id: state.state_id,
      requested_url: requestedUrl,
      final_url: finalUrl,
      captured_at: new Date().toISOString(),
      source_updated_at: null,
      final_http_status: status,
      viewport: state.viewport,
      state: state.state,
      artifacts: [],
      public_assets: [],
      exceptions,
      result_status: 'failed',
    };
  }
}

export async function main(argv = process.argv.slice(2)) {
  const args = parseArgs(argv);
  if (args.help) {
    printHelp();
    return 0;
  }
  const repoRoot = process.cwd();
  const planPath = path.resolve(repoRoot, args.plan);
  const planBytes = await fs.readFile(planPath);
  const plan = JSON.parse(planBytes.toString('utf8'));
  const allowedHosts = assertPlanForLiveCapture(plan);
  const overrideUrls = parseKeyValueArgs(args.overrideUrls, '--override-url');
  const actionSelectors = parseKeyValueArgs(args.actionSelectors, '--action-selector');
  for (const stateId of overrideUrls.keys()) {
    if (!plan.states.some((state) => state.state_id === stateId)) throw new CapturePolicyError(`override state not in plan: ${stateId}`);
    assertApprovedHttpsUrl(overrideUrls.get(stateId), allowedHosts, `override ${stateId}`);
  }
  for (const stateId of actionSelectors.keys()) {
    if (!plan.states.some((state) => state.state_id === stateId)) throw new CapturePolicyError(`action-selector state not in plan: ${stateId}`);
  }

  console.log(`PLAN_VALID site_id=${plan.site_id} states=${plan.states.length}`);
  console.log(`PLAN_SHA256=${sha256Bytes(planBytes)}`);
  if (!args.allowLive) {
    console.log('CAPTURE_EXECUTED=NO');
    console.log('LIVE_CAPTURE_REQUIRES=--allow-live');
    return 0;
  }
  if ((process.env.CI ?? '').toLowerCase() === 'true') {
    throw new CapturePolicyError('live named-site capture is forbidden when CI=true');
  }

  const captureId = args.captureId ?? kstCaptureId();
  assertSafeId(captureId.toLowerCase(), 'capture_id');
  const outParent = path.resolve(repoRoot, args.outRoot, plan.site_id, 'g1');
  const outDir = path.join(outParent, captureId);
  await fs.mkdir(outParent, { recursive: true });
  await fs.mkdir(outDir, { recursive: false });

  const { chromium } = await import('playwright');
  const browser = await chromium.launch({ headless: true });
  const capturedStates = [];
  try {
    for (const state of plan.states) {
      const requestedUrl = overrideUrls.get(state.state_id) ?? state.source_seed_url;
      const stateDir = path.join(outDir, 'states', state.state_id);
      await fs.mkdir(stateDir, { recursive: true });
      console.log(`CAPTURE_START ${state.state_id} ${requestedUrl}`);
      const captured = await captureState({
        browser,
        state,
        requestedUrl,
        actionSelector: actionSelectors.get(state.state_id) ?? null,
        allowedHosts,
        stateDir,
        repoRoot,
        settleMs: args.settleMs,
      });
      capturedStates.push(captured);
      console.log(`CAPTURE_RESULT ${state.state_id} ${captured.result_status}`);
    }
  } finally {
    await browser.close();
  }

  const planRelative = artifactId(path.relative(repoRoot, planPath));
  const ledger = {
    schema_version: '1.0.0',
    kind: 'named_site_reference_capture_ledger',
    site_id: plan.site_id,
    capture_mode: CAPTURE_MODE,
    plan_identity: { plan_id: plan.plan_id, path: planRelative, sha256: sha256Bytes(planBytes) },
    g1_completion_claim: computeG1Claim(plan, capturedStates),
    captured_states: capturedStates,
  };
  const ledgerPath = path.join(outDir, 'ledger.json');
  await writeJson(ledgerPath, ledger);
  console.log(`LEDGER=${artifactId(path.relative(repoRoot, ledgerPath))}`);
  console.log(`G1_COMPLETION_CLAIM=${ledger.g1_completion_claim ? 'YES' : 'NO'}`);
  return ledger.g1_completion_claim ? 0 : 3;
}

const invokedPath = process.argv[1] ? pathToFileURL(path.resolve(process.argv[1])).href : null;
if (invokedPath && import.meta.url === invokedPath) {
  main().then((code) => { process.exitCode = code; }).catch((error) => {
    console.error(`NAMED_SITE_CAPTURE_ERROR: ${error?.message ?? error}`);
    process.exitCode = 2;
  });
}
