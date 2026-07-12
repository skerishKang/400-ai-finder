/**
 * scripts/validate_page_agent_live_adapter.mjs
 *
 * Controlled-live validation for the Stage 4 Page Agent server adapter.
 * This is an OFFLINE fixture validator - NO live provider calls are made.
 *
 * Gated behind:
 *   RUN_PAGE_AGENT_LIVE_VALIDATION=1
 *
 * Validates that the server adapter policy correctly rejects dangerous
 * actions: execute_javascript, go_to, input_text, select_option, unknown
 * actions, multiple actions, invalid href protocol, external href, etc.
 *
 * NO live Gemini/Hy3 calls. NO submission. NO PII transmission.
 */

const RUN = process.env.RUN_PAGE_AGENT_LIVE_VALIDATION;
if (RUN !== '1') {
  console.log('[skip] RUN_PAGE_AGENT_LIVE_VALIDATION not set');
  process.exit(0);
}

const ADAPTER_URL = new URL('../functions/api/page-agent/_adapter.js', import.meta.url).pathname;
const POLICY_URL = new URL('../functions/api/page-agent/_policy.js', import.meta.url).pathname;

const {
  validateAction,
  validateProviderResponse,
  parseBrowserStateElements,
  buildProviderRequestBody,
  resolveConfig,
} = await import(ADAPTER_URL);

const P = await import(POLICY_URL);

let passed = 0;
let failed = 0;
const failures = [];

function ok(cond, msg) {
  if (!cond) throw new Error(msg || 'assertion failed');
}
function eq(a, b, msg) {
  if (a !== b) throw new Error((msg || 'assertion failed') + ` (expected ${b}, got ${a})`);
}

function assert(desc, fn) {
  try {
    fn();
    passed += 1;
    console.log('  PASS ' + desc);
  } catch (err) {
    failed += 1;
    failures.push({ desc: desc, error: err.message });
    console.log('  FAIL ' + desc + ': ' + err.message);
  }
}

// ── Mock provider response builders ───────────────────────────────────────────

function agentOutputArgs(actionObj) {
  return JSON.stringify({ action: actionObj });
}

function mockProviderResponse(actionObj) {
  return {
    choices: [
      {
        message: {
          tool_calls: [
            {
              function: {
                name: 'AgentOutput',
                arguments: agentOutputArgs(actionObj),
              },
            },
          ],
        },
      },
    ],
  };
}

// ── Browser state elements ─────────────────────────────────────────────────────

const SAFE_BROWSER_STATE =
  '[0]<a href="#" data-action-target="nav-civil-service">종합민원</a>\n' +
  '[1]<div data-action-target="apartment-guidance-card" tabindex="0">공동주택과</div>\n' +
  '[2]<a href="http://localhost:9000/internal" data-action-target="nav-complaint-category">민원</a>\n' +
  '[3]<a href="https://cgbukku.pages.dev/same" data-action-target="mayor-office-open">열린구청장실</a>\n' +
  '[5]<a href="https://evil.example.com" data-action-target="nav-civil-service">외부</a>\n' +
  '[7]<button data-action-target="login-button">로그인</button>';

const SAFE_ELEMENTS = parseBrowserStateElements(SAFE_BROWSER_STATE);
const REQUEST_ORIGIN = 'http://localhost:8766';

// ── Offline policy validation tests ───────────────────────────────────────────

console.log('\n[PageAgent controlled-live offline validation]');

assert('valid click_element_by_index on safe target -> ok', () => {
  const r = validateAction({ click_element_by_index: { index: 1 } }, SAFE_ELEMENTS, { requestOrigin: REQUEST_ORIGIN });
  ok(r.ok, 'should be ok');
  eq(r.name, 'click_element_by_index', 'name');
});

assert('valid scroll -> ok', () => {
  const r = validateAction({ scroll: { num_pages: 2 } }, SAFE_ELEMENTS, { requestOrigin: REQUEST_ORIGIN });
  ok(r.ok, 'should be ok');
  eq(r.name, 'scroll', 'name');
});

assert('valid done -> ok', () => {
  const r = validateAction({ done: { text: '작업을 완료했습니다', success: true } }, SAFE_ELEMENTS, { requestOrigin: REQUEST_ORIGIN });
  ok(r.ok, 'should be ok');
  eq(r.name, 'done', 'name');
});

assert('execute_javascript -> rejected', () => {
  const r = validateAction({ execute_javascript: { script: 'alert(1)' } }, SAFE_ELEMENTS, { requestOrigin: REQUEST_ORIGIN });
  ok(!r.ok, 'should not be ok');
  eq(r.failureCode, 'unknown_action', 'failure code');
});

assert('go_to -> rejected', () => {
  const r = validateAction({ go_to: { url: 'https://example.com' } }, SAFE_ELEMENTS, { requestOrigin: REQUEST_ORIGIN });
  ok(!r.ok, 'should not be ok');
  eq(r.failureCode, 'unknown_action', 'failure code');
});

assert('input_text -> rejected', () => {
  const r = validateAction({ input_text: { index: 2, text: 'hello' } }, SAFE_ELEMENTS, { requestOrigin: REQUEST_ORIGIN });
  ok(!r.ok, 'should not be ok');
  eq(r.failureCode, 'unknown_action', 'failure code');
});

assert('select_option -> rejected', () => {
  const r = validateAction({ select_option: { index: 2, value: 'opt1' } }, SAFE_ELEMENTS, { requestOrigin: REQUEST_ORIGIN });
  ok(!r.ok, 'should not be ok');
  eq(r.failureCode, 'unknown_action', 'failure code');
});

assert('wait -> rejected', () => {
  const r = validateAction({ wait: { milliseconds: 1000 } }, SAFE_ELEMENTS, { requestOrigin: REQUEST_ORIGIN });
  ok(!r.ok, 'should not be ok');
  eq(r.failureCode, 'unknown_action', 'failure code');
});

assert('unknown action -> rejected', () => {
  const r = validateAction({ fly_to_the_moon: {} }, SAFE_ELEMENTS, { requestOrigin: REQUEST_ORIGIN });
  ok(!r.ok, 'should not be ok');
  eq(r.failureCode, 'unknown_action', 'failure code');
});

assert('multiple actions -> rejected', () => {
  const r = validateAction({ click_element_by_index: { index: 1 }, done: { text: 'x', success: true } }, SAFE_ELEMENTS, { requestOrigin: REQUEST_ORIGIN });
  ok(!r.ok, 'should not be ok');
  eq(r.failureCode, 'invalid_action', 'failure code');
});

assert('click on forbidden target (submit button) -> rejected', () => {
  const r = validateAction({ click_element_by_index: { index: 7 } }, SAFE_ELEMENTS, { requestOrigin: REQUEST_ORIGIN });
  ok(!r.ok, 'should not be ok');
  eq(r.failureCode, 'unsafe_target', 'failure code');
});

assert('click on javascript: href -> rejected', () => {
  const elements = parseBrowserStateElements('[0]<a href="javascript:alert(1)" data-action-target="nav-civil-service">X</a>');
  const r = validateAction({ click_element_by_index: { index: 0 } }, elements, { requestOrigin: REQUEST_ORIGIN });
  ok(!r.ok, 'should not be ok');
  eq(r.failureCode, 'unsafe_target', 'failure code');
});

assert('click on data: href -> rejected', () => {
  const elements = parseBrowserStateElements('[0]<a href="data:text/html,<script>alert(1)</script>" data-action-target="nav-civil-service">X</a>');
  const r = validateAction({ click_element_by_index: { index: 0 } }, elements, { requestOrigin: REQUEST_ORIGIN });
  ok(!r.ok, 'should not be ok');
  eq(r.failureCode, 'unsafe_target', 'failure code');
});

assert('click on blob: href -> rejected', () => {
  const elements = parseBrowserStateElements('[0]<a href="blob:https://example.com/xxx" data-action-target="nav-civil-service">X</a>');
  const r = validateAction({ click_element_by_index: { index: 0 } }, elements, { requestOrigin: REQUEST_ORIGIN });
  ok(!r.ok, 'should not be ok');
  eq(r.failureCode, 'unsafe_target', 'failure code');
});

assert('click on mailto: href -> rejected', () => {
  const elements = parseBrowserStateElements('[0]<a href="mailto:test@example.com" data-action-target="nav-civil-service">X</a>');
  const r = validateAction({ click_element_by_index: { index: 0 } }, elements, { requestOrigin: REQUEST_ORIGIN });
  ok(!r.ok, 'should not be ok');
  eq(r.failureCode, 'unsafe_target', 'failure code');
});

assert('click on tel: href -> rejected', () => {
  const elements = parseBrowserStateElements('[0]<a href="tel:1234567890" data-action-target="nav-civil-service">X</a>');
  const r = validateAction({ click_element_by_index: { index: 0 } }, elements, { requestOrigin: REQUEST_ORIGIN });
  ok(!r.ok, 'should not be ok');
  eq(r.failureCode, 'unsafe_target', 'failure code');
});

assert('click on external HTTPS href (different origin) -> rejected', () => {
  const elements = parseBrowserStateElements('[0]<a href="https://evil.example.com/page" data-action-target="nav-civil-service">X</a>');
  const r = validateAction({ click_element_by_index: { index: 0 } }, elements, { requestOrigin: REQUEST_ORIGIN });
  ok(!r.ok, 'should not be ok');
  eq(r.failureCode, 'unsafe_target', 'failure code');
});

assert('click on different cgbukku preview subdomain -> rejected', () => {
  const elements = parseBrowserStateElements('[0]<a href="https://different-preview.cgbukku.pages.dev/path" data-action-target="nav-civil-service">X</a>');
  const r = validateAction({ click_element_by_index: { index: 0 } }, elements, { requestOrigin: 'https://cgbukku.pages.dev' });
  ok(!r.ok, 'should not be ok');
  eq(r.failureCode, 'unsafe_target', 'failure code');
});

assert('click on different localhost port -> rejected', () => {
  const elements = parseBrowserStateElements('[0]<a href="http://localhost:9999/path" data-action-target="nav-civil-service">X</a>');
  const r = validateAction({ click_element_by_index: { index: 0 } }, elements, { requestOrigin: 'http://localhost:8766' });
  ok(!r.ok, 'should not be ok');
  eq(r.failureCode, 'unsafe_target', 'failure code');
});

assert('click on same-origin relative href -> ok', () => {
  const elements = parseBrowserStateElements('[0]<a href="/internal/path" data-action-target="nav-civil-service">X</a>');
  const r = validateAction({ click_element_by_index: { index: 0 } }, elements, { requestOrigin: 'http://localhost:8766' });
  ok(r.ok, 'should be ok (relative href resolved against requestOrigin)');
});

assert('click on same-origin absolute HTTPS href -> ok', () => {
  const elements = parseBrowserStateElements('[0]<a href="https://cgbukku.pages.dev/same" data-action-target="nav-civil-service">X</a>');
  const r = validateAction({ click_element_by_index: { index: 0 } }, elements, { requestOrigin: 'https://cgbukku.pages.dev' });
  ok(r.ok, 'should be ok');
});

assert('validateProviderResponse accepts valid AgentOutput', () => {
  const resp = mockProviderResponse({ click_element_by_index: { index: 1 } });
  const r = validateProviderResponse(resp);
  ok(r.ok, 'should be ok');
});

assert('validateProviderResponse rejects missing tool call', () => {
  const resp = { choices: [{ message: { tool_calls: [] } }] };
  const r = validateProviderResponse(resp);
  ok(!r.ok, 'should not be ok');
  eq(r.failureCode, 'missing_tool_call', 'failure code');
});

assert('validateProviderResponse rejects wrong function name', () => {
  const resp = {
    choices: [{
      message: {
        tool_calls: [{
          function: { name: 'OtherTool', arguments: '{}' }
        }]
      }
    }]
  };
  const r = validateProviderResponse(resp);
  ok(!r.ok, 'should not be ok');
  eq(r.failureCode, 'missing_tool_call', 'failure code');
});

assert('validateProviderResponse rejects malformed arguments', () => {
  const resp = {
    choices: [{
      message: {
        tool_calls: [{
          function: { name: 'AgentOutput', arguments: 'not-json' }
        }]
      }
    }]
  };
  const r = validateProviderResponse(resp);
  ok(!r.ok, 'should not be ok');
  eq(r.failureCode, 'malformed_response', 'failure code');
});

assert('validateProviderResponse rejects action without required keys', () => {
  const resp = {
    choices: [{
      message: {
        tool_calls: [{
          function: { name: 'AgentOutput', arguments: JSON.stringify({ wrong_key: {} }) }
        }]
      }
    }]
  };
  const r = validateProviderResponse(resp);
  ok(!r.ok, 'should not be ok');
  eq(r.failureCode, 'malformed_response', 'failure code');
});

assert('resolveConfig builds correct request body', () => {
  const config = resolveConfig({
    PAGE_AGENT_LLM_ENABLED: 'true',
    PAGE_AGENT_LLM_PROVIDER: 'gemini',
    GEMINI_API_KEY: 'test-key',
  });
  const body = buildProviderRequestBody(config, '공동주택과', 'browser state content');
  ok(body.messages.length === 2, 'two messages');
  ok(body.tools.length === 1, 'one tool');
  eq(body.tools[0].function.name, 'AgentOutput', 'tool name');
  ok(body.messages[0].role === 'system', 'system message');
  ok(body.messages[1].role === 'user', 'user message');
  ok(body.messages[1].content.includes('<user_request>'), 'user_request tag');
  ok(body.messages[1].content.includes('<browser_state>'), 'browser_state tag');
});

assert('P.detectUserRequestPii catches known patterns', () => {
  ok(P.detectUserRequestPii('주민번호 123456-1234567'), 'rrn');
  ok(P.detectUserRequestPii('카드 1234-5678-9012-3456'), 'card');
  ok(P.detectUserRequestPii('내 번호 010-1234-5678'), 'phone');
  ok(P.detectUserRequestPii('me@test.com 문의'), 'email');
  ok(P.detectUserRequestPii('비밀번호를忘了'), 'password');
  ok(!P.detectUserRequestPii('공동주택과 연락처 찾아줘'), 'clean');
});

assert('P.isAllowedOrigin accepts production HTTPS', () => {
  ok(P.isAllowedOrigin('https://cgbukku.pages.dev'), 'prod');
  ok(P.isAllowedOrigin('https://preview.cgbukku.pages.dev'), 'preview');
  ok(P.isAllowedOrigin('http://localhost:8766'), 'localhost');
  ok(P.isAllowedOrigin('http://127.0.0.1:8766'), '127.0.0.1');
  ok(!P.isAllowedOrigin('http://cgbukku.pages.dev'), 'http prod rejected');
  ok(!P.isAllowedOrigin('https://evil.example.com'), 'evil');
  ok(!P.isAllowedOrigin('not-a-url'), 'malformed');
});

assert('P.isSafeTarget allows civic targets, rejects forbidden', () => {
  ok(P.isSafeTarget('nav-civil-service'), 'nav ok');
  ok(P.isSafeTarget('apartment-guidance-card'), 'card ok');
  ok(P.isSafeTarget('complaint-write'), 'complaint ok');
  ok(!P.isSafeTarget('confirm-draft-prefill'), 'submit rejected');
  ok(!P.isSafeTarget('login-button'), 'login rejected');
  ok(!P.isSafeTarget('payment-submit'), 'payment rejected');
});

assert('P.SAFE_TARGET_PREFIXES has all expected entries', () => {
  const expected = ['nav-civil-service', 'nav-complaint-category', 'mayor-office-open', 'complaint-write', 'apartment-guidance-card'];
  for (const t of expected) {
    ok(P.SAFE_TARGET_PREFIXES.includes(t), t);
  }
});

assert('ALLOWED_ACTIONS only has 3 actions', () => {
  eq(P.ALLOWED_ACTIONS.length, 3, '3 allowed');
  ok(P.ALLOWED_ACTIONS.includes('click_element_by_index'), 'click');
  ok(P.ALLOWED_ACTIONS.includes('scroll'), 'scroll');
  ok(P.ALLOWED_ACTIONS.includes('done'), 'done');
});

// ── summary ─────────────────────────────────────────────────────────────────────

console.log('\n[PageAgent controlled-live validator] passed=' + passed + ' failed=' + failed);
if (failed > 0) {
  console.log('FAILURES:');
  for (const f of failures) console.log('  - ' + f.desc + ': ' + f.error);
  process.exit(1);
}
console.log('All controlled-live offline validation tests passed.');
console.log('(NO live provider calls were made)');