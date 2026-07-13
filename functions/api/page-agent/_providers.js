// ═════════════════════════════════════════════════════════════════════════
// functions/api/page-agent/_providers.js
//
// Provider factory + stubs for Stage 4.
//   PAGE_AGENT_MODEL_ENABLED  — server-only enable
//   PAGE_AGENT_MODEL_PROVIDER — "disabled" | "mock" (server-only)
// No network. No secrets. Browser cannot choose provider.
// ═════════════════════════════════════════════════════════════════════════

import { buildValidatedPlanShape, findParityScenario } from './_parity_scenarios.js';
import * as S from './_schema.js';

export class PageAgentModelProvider {
  /**
   * @param {object} _request
   * @param {{ signal?: AbortSignal }} _options
   * @returns {Promise<{ ok: boolean, plan?: object, error?: string, detail?: string }>}
   */
  async createPlan(_request, _options) {
    throw new Error('page_agent_provider_not_implemented');
  }
}

export class DisabledStubProvider extends PageAgentModelProvider {
  async createPlan(_request, options) {
    const signal = options && options.signal;
    if (signal && signal.aborted) {
      const err = new Error('page_agent_cancelled');
      err.code = 'page_agent_cancelled';
      throw err;
    }
    return {
      ok: false,
      error: 'page_agent_provider_not_configured',
      detail: 'stage4_stub_only',
    };
  }
}

export class DeterministicMockProvider extends PageAgentModelProvider {
  async createPlan(request, options) {
    const signal = options && options.signal;
    if (signal && signal.aborted) {
      const err = new Error('page_agent_cancelled');
      err.code = 'page_agent_cancelled';
      throw err;
    }

    const scenario = findParityScenario(request && request.question);
    if (!scenario) {
      return {
        ok: false,
        error: 'page_agent_unsupported_task',
        detail: 'no_parity_scenario',
      };
    }

    const plan = buildValidatedPlanShape(scenario);
    plan.result_boundary = S.RESULT_BOUNDARY;
    return { ok: true, plan: plan };
  }
}

/**
 * Truthy server enable flag only.
 */
export function isModelAdapterEnabled(env) {
  if (!env || typeof env !== 'object') return false;
  const raw = env[S.ENABLE_FLAG];
  if (raw === true || raw === 1) return true;
  if (typeof raw !== 'string') return false;
  const v = raw.trim().toLowerCase();
  return v === '1' || v === 'true' || v === 'yes' || v === 'on';
}

/**
 * Resolve provider name from server env only (never request body/query).
 * @returns {'disabled'|'not_configured'|'mock'|'unsupported'}
 */
export function resolveProviderKind(env) {
  if (!isModelAdapterEnabled(env)) return 'disabled';
  const raw = env && env[S.PROVIDER_ENV];
  const name = typeof raw === 'string' ? raw.trim().toLowerCase() : '';
  if (!name || name === 'disabled') return 'not_configured';
  if (name === 'mock') return 'mock';
  return 'unsupported';
}

/**
 * @returns {{ kind: string, provider: PageAgentModelProvider|null, name: string }}
 */
export function createProvider(env) {
  const kind = resolveProviderKind(env);
  if (kind === 'disabled') {
    return { kind: kind, provider: null, name: 'disabled' };
  }
  if (kind === 'not_configured') {
    return { kind: kind, provider: new DisabledStubProvider(), name: 'disabled' };
  }
  if (kind === 'mock') {
    return { kind: kind, provider: new DeterministicMockProvider(), name: 'mock' };
  }
  return { kind: 'unsupported', provider: null, name: String((env && env[S.PROVIDER_ENV]) || '') };
}
