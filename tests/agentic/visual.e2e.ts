import { test } from '@e2e-dev/web';
import { expect } from 'e2e';

test('example.com looks like a plain page', async ({ app, agent, screen }) => {
  await app.open('/');
  // Visual checks go to the vision agent (Luna), per AGENTS.md.
  await agent.assert('the page shows plain text content and exactly one link', {
    agent: 'luna',
    vision: true,
  });
  await agent.assert('no error banner shows on the page', {
    agent: 'luna',
    vision: true,
  });
  // Exact check: the screen lists exactly one link.
  await expect(screen.getByRole('link')).toHaveCount(1);
});
