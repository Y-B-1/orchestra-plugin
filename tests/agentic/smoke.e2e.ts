import { test } from '@e2e-dev/web';
import { expect } from 'e2e';

test('Learn more opens IANA content', async ({ app, agent, screen }) => {
  await app.open('/');
  // Jev acts. The goal names a destination the page text proves, not a click.
  await agent.act('go to the Example Domains page');
  // Text assertion: the default agent (Jev) judges it from the page text.
  await agent.assert('the page shows IANA content about example domains');
  // Visual assertion: route to the vision agent (Luna) for this call only.
  await agent.assert('the page shows a heading and body text, with no error message', {
    agent: 'luna',
    vision: true,
  });
  await expect(screen.getByRole('heading', 'Example Domains')).toBeVisible();
});
