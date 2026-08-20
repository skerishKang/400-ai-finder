import assert from 'node:assert/strict';
import test from 'node:test';

import {
  CapturePolicyError,
  assertApprovedHttpsUrl,
  assertPlanForLiveCapture,
  computeG1Claim,
  kstCaptureId,
  normalizeAllowedHosts,
  parseKeyValueArgs,
  pngDimensions,
  requestAllowed,
  sanitizeExceptionDetail,
  sanitizePublicHtml,
  sha256Bytes,
} from '../../scripts/capture_named_site_reference.mjs';

function plan() {
  return {
    plan_id: 'seogu_gwangju.g1.v1',
    site_id: 'seogu_gwangju',
    capture_mode: 'controlled_read_only_reference',
    allowed_hosts: ['www.seogu.gwangju.kr'],
    allowed_methods: ['GET'],
    routine_ci: { network_policy: 'offline' },
    security_boundary: {
      post_allowed: false,
      form_submission_allowed: false,
      login_allowed: false,
      payment_allowed: false,
      identity_verification_allowed: false,
      pii_entry_allowed: false,
      personal_file_upload_allowed: false,
      actual_site_mutation_allowed: false,
    },
    states: [
      {
        state_id: 'home.desktop.default',
        source_seed_url: 'https://www.seogu.gwangju.kr/',
        viewport: { width: 1440, height: 900 },
        state: { name: 'default' },
        required_artifacts: ['html_dom_content', 'screenshot'],
        capture_required: true,
      },
      {
        state_id: 'notice.list.desktop',
        source_seed_url: 'https://www.seogu.gwangju.kr/board.es?mid=x',
        viewport: { width: 1440, height: 900 },
        state: { name: 'default' },
        required_artifacts: ['html_dom_content', 'screenshot'],
        capture_required: true,
      },
    ],
  };
}

test('safe plan validates and returns exact allowed host set', () => {
  const hosts = assertPlanForLiveCapture(plan());
  assert.deepEqual([...hosts], ['www.seogu.gwangju.kr']);
});

test('exact-host URL policy rejects scheme, suffix, userinfo, port, and fragment attacks', () => {
  const hosts = normalizeAllowedHosts(['www.seogu.gwangju.kr']);
  assert.equal(assertApprovedHttpsUrl('https://www.seogu.gwangju.kr/path?q=1', hosts), 'https://www.seogu.gwangju.kr/path?q=1');
  for (const bad of [
    'http://www.seogu.gwangju.kr/',
    'https://www.seogu.gwangju.kr.evil.example/',
    'https://www.seogu.gwangju.kr@evil.example/',
    'https://attacker@www.seogu.gwangju.kr/',
    'https://www.seogu.gwangju.kr:444/',
    'https://www.seogu.gwangju.kr/#fragment',
  ]) {
    assert.throws(() => assertApprovedHttpsUrl(bad, hosts), CapturePolicyError);
  }
});

test('request policy is GET-only and exact-host only', () => {
  const hosts = normalizeAllowedHosts(['www.seogu.gwangju.kr']);
  assert.equal(requestAllowed('GET', 'https://www.seogu.gwangju.kr/a.css', hosts), true);
  assert.equal(requestAllowed('POST', 'https://www.seogu.gwangju.kr/api', hosts), false);
  assert.equal(requestAllowed('GET', 'https://cdn.example.com/a.css', hosts), false);
});

test('plan rejects a write capability or non-offline routine CI', () => {
  const writePlan = plan();
  writePlan.security_boundary.post_allowed = true;
  assert.throws(() => assertPlanForLiveCapture(writePlan), /post_allowed/);
  const onlinePlan = plan();
  onlinePlan.routine_ci.network_policy = 'online';
  assert.throws(() => assertPlanForLiveCapture(onlinePlan), /network_policy/);
});

test('override parser preserves URL values containing equals signs and rejects duplicates', () => {
  const parsed = parseKeyValueArgs(['notice.list.desktop=https://www.seogu.gwangju.kr/board.es?a=1&b=2'], '--override-url');
  assert.equal(parsed.get('notice.list.desktop'), 'https://www.seogu.gwangju.kr/board.es?a=1&b=2');
  assert.throws(() => parseKeyValueArgs(['x=a', 'x=b'], '--override-url'), /duplicate/);
});

test('HTML sanitizer normalizes whitespace and redacts csrf meta/input values', () => {
  const input = '<meta name="_csrf" content="secret">\r\n<input name="_csrf" value="token">\t\r\n';
  const out = sanitizePublicHtml(input);
  assert.equal(out.includes('secret'), false);
  assert.equal(out.includes('token'), false);
  assert.match(out, /\[REDACTED_SESSION_CSRF\]/);
  assert.equal(out.endsWith('\n'), true);
  assert.equal(out.includes('\r'), false);
});

test('PNG IHDR dimensions are parsed without image dependencies', () => {
  const png = Buffer.alloc(24);
  Buffer.from('89504e470d0a1a0a', 'hex').copy(png, 0);
  png.writeUInt32BE(1440, 16);
  png.writeUInt32BE(1234, 20);
  assert.deepEqual(pngDimensions(png), { width: 1440, height: 1234 });
  assert.throws(() => pngDimensions(Buffer.from('not-png')), /PNG/);
});

test('G1 claim requires every capture-required state to succeed exactly once', () => {
  const p = plan();
  assert.equal(computeG1Claim(p, [
    { state_id: 'home.desktop.default', result_status: 'success' },
    { state_id: 'notice.list.desktop', result_status: 'success' },
  ]), true);
  assert.equal(computeG1Claim(p, [
    { state_id: 'home.desktop.default', result_status: 'success' },
    { state_id: 'notice.list.desktop', result_status: 'failed' },
  ]), false);
});

test('default capture id is filesystem-safe and KST-stamped', () => {
  const id = kstCaptureId(new Date('2026-08-12T12:34:56Z'));
  assert.equal(id, '20260812T213456-0900');
  assert.match(id.toLowerCase(), /^[a-z0-9][a-z0-9._-]*$/);
});

test('sha256 helper is deterministic lowercase 64 hex', () => {
  assert.equal(sha256Bytes(Buffer.from('abc')), 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad');
});

test("HTML sanitizer redacts appkey query value in SDK script src (raw & separator)", () => {
  const input = `<script src="//dapi.kakao.com/v2/maps/sdk.js?appkey=a1b2c3d4e5f6a1b2c3d4e5f6&libraries=services,drawing"></script>`;
  const out = sanitizePublicHtml(input);
  assert.equal(out.includes("a1b2c3d4e5f6a1b2c3d4e5f6"), false, "raw appkey value must be absent");
  assert.match(out, /appkey=\[REDACTED_QUERY_APPKEY\]/, "appkey value must be redacted");
  assert.ok(out.includes("dapi.kakao.com/v2/maps/sdk.js"), "URL host/path preserved");
  assert.ok(out.includes("libraries=services,drawing"), "non-credential query params preserved");
});

test("HTML sanitizer redacts appkey query value in SDK script src (HTML &amp; separator)", () => {
  const input = `<script src="//dapi.kakao.com/v2/maps/sdk.js?appkey=a1b2c3d4e5f6a1b2c3d4e5f6&amp;libraries=services"></script>`;
  const out = sanitizePublicHtml(input);
  assert.equal(out.includes("a1b2c3d4e5f6a1b2c3d4e5f6"), false);
  assert.match(out, /appkey=\[REDACTED_QUERY_APPKEY\]/);
  assert.ok(out.includes("libraries=services"), "non-credential params preserved");
});

test("HTML sanitizer redacts credential value in SDK init string literal", () => {
  const input = `Kakao.init('a1b2c3d4e5f6a1b2c3d4e5f6');`;
  const out = sanitizePublicHtml(input);
  assert.equal(out.includes("a1b2c3d4e5f6a1b2c3d4e5f6"), false, "raw credential must be absent");
  assert.ok(out.includes("[REDACTED_QUERY_APPKEY]"), "credential replaced with redaction token");
});

test("HTML sanitizer preserves unrelated ordinary query parameters", () => {
  const input = `<a href="https://example.com/page?id=42&lang=ko&category=civic">link</a>`;
  const out = sanitizePublicHtml(input);
  assert.ok(out.includes("id=42") && out.includes("lang=ko") && out.includes("category=civic"), "ordinary params preserved");
  assert.equal(out.includes("REDACTED"), false, "no false redaction of ordinary params");
});

test("HTML sanitizer CSRF redaction remains intact alongside appkey redaction", () => {
  const input = `<meta name="_csrf" content="csrfsecret123">\n<script src="//dapi.kakao.com/v2/maps/sdk.js?appkey=a1b2c3d4e5f6a1b2c3d4e5f6&libraries=services"></script>`;
  const out = sanitizePublicHtml(input);
  assert.equal(out.includes("csrfsecret123"), false, "csrf value must be absent");
  assert.equal(out.includes("a1b2c3d4e5f6a1b2c3d4e5f6"), false, "appkey value must be absent");
  assert.match(out, /\[REDACTED_SESSION_CSRF\]/, "csrf redaction token present");
  assert.match(out, /appkey=\[REDACTED_QUERY_APPKEY\]/, "appkey redaction token present");
});

test("sanitizeExceptionDetail redacts appkey in blocked-request URL detail", () => {
  const detail = `GET https://dapi.kakao.com/v2/maps/sdk.js?appkey=a1b2c3d4e5f6a1b2c3d4e5f6&libraries=services,clusterer,drawing`;
  const out = sanitizeExceptionDetail(detail);
  assert.equal(out.includes("a1b2c3d4e5f6a1b2c3d4e5f6"), false, "raw appkey must be absent from exception detail");
  assert.match(out, /appkey=\[REDACTED_QUERY_APPKEY\]/, "appkey redacted in exception detail");
  assert.ok(out.startsWith("GET https://dapi.kakao.com/v2/maps/sdk.js"), "method + URL host/path preserved");
  assert.ok(out.includes("libraries=services,clusterer,drawing"), "non-credential params preserved");
});

test("sanitizeExceptionDetail preserves non-credential details unchanged", () => {
  const detail = "request_blocked_by_capture_policy: cross-origin redirect";
  assert.equal(sanitizeExceptionDetail(detail), detail, "non-credential detail unchanged");
});
