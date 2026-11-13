import { test } from '@e2e-dev/web';
import { expect } from 'e2e';

// TEMPLATE for a project that has a UI. Orchestra is a plugin with no web UI,
// so this test is skipped by default and tagged 'template'. Copy it, point the
// target app URL at your app, drop `skip`, and write one test per user behavior.
// This repo's real end-to-end check is scripts/live-check.py (costs tokens, release only).
test(
  'a visitor adds a todo and sees it listed',
  { tags: ['template'], skip: 'template for a project with a UI' },
  async ({ app, agent, screen }) => {
    // Arrange: start where a user starts.
    await app.open('/todos');
    // Act: one goal, written as a result, never as a click.
    await agent.act('add a todo named "Buy coffee"');
    // Assert: locators for exact text, the agent for meaning.
    await expect(screen.getByTestId('todo')).toContainText('Buy coffee');
    await agent.assert('the todo list contains "Buy coffee"');
  },
);
