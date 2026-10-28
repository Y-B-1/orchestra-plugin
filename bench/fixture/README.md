# Pulse

Pulse is an internal market-insights dashboard. It shows key figures, a sortable table of instruments, a watchlist, top movers and recent activity; the house portfolio with an allocation chart; a filterable, paginated trade blotter with a detail drawer; an instrument page with price history, key stats and recent trades; a searchable client list with a detail drawer and client notes; a list of daily reports with status badges; notifications in the top bar; and user settings (theme and notifications) saved in the browser.

Routes: `/` dashboard, `/portfolio`, `/trades`, `/instruments/:symbol`, `/clients`, `/reports`, `/settings`.

All data is mocked: typed fetchers in `src/api` read JSON files in `src/data` after a short artificial delay.

## Run it

Requires Node 20 or newer.

```sh
npm install
npm run dev        # start the dev server
npm test           # vitest, one run
npm run typecheck  # tsc in strict mode
npm run lint       # eslint (flat config)
npm run build      # type check, then production build into dist/
```

## Layout

- `src/components` shared UI pieces (Table, Drawer, Tabs, Pagination, AsyncContent and more), with tests beside them
- `src/components/<feature>` pieces used by one area: `trades`, `portfolio`, `instrument`, `notifications`, `clients`, `dashboard`
- `src/pages` one component per route
- `src/hooks` data loading (`useAsync`), `useDebounce`, `useLocalStorage`, and the settings and notifications contexts
- `src/api` mock fetchers; `src/data` JSON fixtures
- `src/utils` formatting (`format`, `numbers`, `dates`), sorting, pagination, CSV, portfolio maths, storage and search helpers
- `src/styles/theme.css` theme variables; `global.css` styles
