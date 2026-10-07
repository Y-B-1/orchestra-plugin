import { existsSync } from 'node:fs';
import type { E2EConfig } from 'e2e';
import { web } from '@e2e-dev/web';
import { decisionExecutor } from '@e2e-dev/decision';
import { typeSafeAi } from '@ai-sdk/typesafe-ai';
import { openrouter } from '@openrouter/ai-sdk-provider';

// Keys come from the shell or from this gitignored file. Never commit values.
// OPENROUTER_API_KEY -> Luna.  TYPESAFE_AI_API_KEY -> Jev.
if (existsSync('.env.e2e.local')) process.loadEnvFile('.env.e2e.local');

// Luna: writes typed values and judges assert / waitFor / extract. Also the full vision agent.
const luna = openrouter('openai/gpt-6-luna');

export default {
  // Agentic tests live apart from the existing Playwright suites.
  tests: ['tests/agentic/**/*.e2e.ts'],
  targets: [
    {
      engine: web(),
      app: { url: process.env.APP_URL ?? 'https://example.com' },
    },
  ],
  agents: {
    // Default: Jev picks each action (no screenshots); Luna types values and judges.
    default: {
      executor: decisionExecutor({ model: typeSafeAi.decisionModel('jev-latest') }),
      model: luna,
    },
    // Fallback for steps that need vision: run with --agent luna.
    luna: {
      model: luna,
      system: 'You are a thorough QA agent. Verify every outcome.',
    },
  },
} satisfies E2EConfig;
