# GhostHub Layout Framework Guide

This guide defines how layouts must be structured under `static/js/modules/layouts/**`.

## Layouts in GhostHub

- `streaming/`: row-based browsing (Netflix-style)
- `gallery/`: date timeline browsing (photos-first)
- `shared/`: reusable lifecycle/orchestration helpers

## Non-Negotiable Ownership Model

1. UI/render state belongs to `Component`.
2. Layout orchestration belongs to `Module`.
3. Mixed behavior must split into `Module` + `Component`.
4. Long-lived listeners/sockets/timers must be lifecycle-owned.

## Required Layout Contract

Each layout `index.js` should expose:

- `init()`
- `cleanup()`
- `refresh()`
- `isActive()`
- socket registration helpers when needed (`registerSocketHandlers`, `cleanupSocketHandlers`)

`init/cleanup` are called by lifecycle owners; do not self-bootstrap layout features.

## Shared Layout Utilities (Use by Default)

`layouts/shared/` contains standard orchestration building blocks:

- `layoutLifecycle.js`
  - `createLayoutChangeLifecycle(...)`
  - Owns `layoutChanged` wiring with a `Module`

- `socketHandlers.js`
  - `createLayoutSocketHandlerManager(...)`
  - Owns socket listeners + debounced refresh behavior

- `filterActions.js`
  - `createLayoutFilterActions(...)`
  - Shared category/parent/subfolder filter action flow

## Recommended Skeleton

```javascript
import { createLayoutChangeLifecycle } from '../shared/layoutLifecycle.js';
import { createLayoutSocketHandlerManager } from '../shared/socketHandlers.js';
import { createLayoutFilterActions } from '../shared/filterActions.js';

async function init() {}
function cleanup() {}
async function refresh(forceRefresh = false) {}
function isActive() { return false; }

const ensureLayoutLifecycle = createLayoutChangeLifecycle({
    layoutName: 'my-layout',
    initLayout: init,
    cleanupLayout: cleanup
});

const socketHandlers = createLayoutSocketHandlerManager({
    isActive,
    refresh,
    handleProgressUpdate: () => {},
    syncShowHiddenFromEvent: async () => {}
});

const filterActions = createLayoutFilterActions({
    isActive,
    resolveCategoryName: () => '',
    applyCategoryState: () => {},
    applyParentState: () => {},
    refreshForFilter: () => refresh()
});

ensureLayoutLifecycle();
```

## Allowed vs Disallowed Patterns

Allowed:
- `Module.on`, `Module.onSocket`, `Module.timeout`, `Module.interval`
- layout-level `registerSocketHandlers` that delegate to shared managers
- `Component` ownership for UI-only pieces

Disallowed in layout feature files:
- raw long-lived `socket.on/socket.off`
- raw long-lived `window/document.addEventListener`
- unmanaged long-lived `setTimeout/setInterval`
- orphan teardown functions not wired to `cleanup()`/`stop()`

## Selector Rule (`::` IDs)

Because `$`/`$$` use `querySelector`, IDs containing `::` must be accessed with:

```javascript
const el = document.getElementById('auto::categories');
```

## Quick Review Checklist

1. Does `index.js` own orchestration and cleanup paths?
2. Are socket/global/timer resources lifecycle-owned?
3. Are shared helpers used instead of duplicated orchestration?
4. Is layout behavior unchanged except for lifecycle hardening?
5. Are focused tests updated/passing for changed layout modules?
