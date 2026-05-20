---
name: vue-optimize
description: Analyze Vue 3 components for performance and code-reuse opportunities and produce an actionable report. Use this skill when the user asks to analyze, audit, review, or optimize Vue components, find duplication across .vue files, suggest composables to extract, or improve reactivity/rendering performance in client/src/.
---

# Vue Component Optimization

This skill audits the Vue 3 frontend in `client/src/` and produces a concrete, file-cited report of performance and code-reuse opportunities. It does **not** modify `.vue` files — per the project's mandatory rule, any actual `.vue` change must be delegated to the `vue-expert` subagent after the user picks which suggestions to act on.

## When to invoke

Trigger this skill when the user asks to:
- Analyze / audit / review Vue component structure
- Optimize rendering, reactivity, or bundle size on the frontend
- Find duplication across views/components and suggest composables to extract
- Spot v-for / v-if / watch / computed misuse

Do **not** invoke for: backend code, single-line cosmetic fixes, or general Vue questions answered by `client/CLAUDE.md`.

## Scope

Audit these paths only:
- `client/src/views/*.vue` (page-level)
- `client/src/components/*.vue` (reusable UI)
- `client/src/composables/*.js` (shared logic)
- `client/src/api.js`, `client/src/main.js`

Skip: `client/node_modules/`, locale JSON files, anything outside `client/src/`.

## Procedure

### Step 1 — Inventory

Use `Glob` to list the `.vue` files in scope. Use `Grep` (not Read) to scan for patterns first; only `Read` a file when a grep hit needs context. For most audits, reading 3–6 files in full is enough — do not Read every component.

### Step 2 — Run the checklist

Walk every check below. For each hit, record: file path, line number(s), the problem in one sentence, and the suggested fix. Skip checks that don't apply rather than padding.

#### Performance checks

1. **v-for with index key or no key.** `:key="index"` or missing `:key` on a `v-for` over data that can reorder. (See `client/CLAUDE.md` → Common Pitfalls.) Suggest a stable id (`sku`, `order_number`, `id`).
2. **v-for + v-if on same element.** Vue evaluates `v-for` first, so `v-if` runs per item. Suggest filtering in a `computed` instead.
3. **Function or object literal in template.** `:style="{ color: x ? 'red' : 'green' }"` or `@click="() => doThing(item.id)"` inside a `v-for`. Suggest a `computed` or named handler — inline literals re-allocate every render.
4. **Heavy work in methods that should be computed.** Method called from template that filters/maps a large list each call. Computed is cached; methods aren't.
5. **Computed that should be a method.** Pure side-effect-free transforms with no reactive deps don't benefit from `computed`. Rare, but flag if found.
6. **Watcher that should be computed.** `watch(a, () => b.value = transform(a.value))` is a `computed` in disguise. Computed is cheaper and declarative.
7. **`deep: true` or `immediate: true` watchers.** Flag both — deep watchers traverse large structures on every change; `immediate` often masks an init-time bug that belongs in `onMounted`.
8. **v-if for frequently toggled UI.** Modals, dropdowns, expand/collapse — these should usually be `v-show`. (Documented in `client/CLAUDE.md`.)
9. **v-show for rarely shown heavy UI.** Inverse: large charts/tables hidden by default should be `v-if` (or `defineAsyncComponent`) so they don't ship DOM eagerly.
10. **Eagerly imported heavy components.** Modals and chart-heavy views imported at the top of a parent. Suggest `defineAsyncComponent(() => import('...'))`.
11. **Large frozen data wrapped reactively.** `ref(largeStaticArray)` or `ref(bigConfig)` where the data never mutates internally. Suggest `shallowRef` or `markRaw`.
12. **Unscoped global styles.** `<style>` without `scoped` in a component (not `App.vue`). Causes cross-component bleed and forces the whole CSS recompile.
13. **Un-debounced watchers driving API calls.** A `watch(filterRef, loadData)` without `watchDebounced` or a manual debounce. Especially on text input.
14. **Date parsing without validation.** `new Date(x).getMonth()` without an `isNaN` check (documented pitfall in `CLAUDE.md`).

#### Code-reuse checks

1. **Duplicated data-loading boilerplate.** The `loading/error/data + try/catch/finally` block from `client/CLAUDE.md` repeated in many views. If it appears in ≥3 files, suggest a `useAsyncData(fn)` composable in `client/src/composables/`.
2. **Views wiring filters by hand instead of using `useFilters`.** Grep for `selectedPeriod`, `selectedLocation`, `selectedCategory`, `selectedStatus` outside `useFilters.js` / `FilterBar.vue`. Any view that re-declares these should use the composable.
3. **Inline formatters duplicated across files.** `toLocaleString('en-US', { style: 'currency', ... })`, `formatDate`, percentage formatting. If repeated, suggest `client/src/utils/format.js` (check whether one already exists before suggesting).
4. **Duplicate modal scaffolding.** Multiple `*DetailModal.vue` files share open/close/backdrop/escape-key logic. If patterns diverge only in body content, suggest a `BaseModal.vue` shell with a slot.
5. **Repeated table layouts.** Order/Inventory/Restocking tables that share row/cell structure. Suggest a `DataTable.vue` with column-config prop only if ≥3 tables share ≥80% of structure — don't over-abstract.
6. **Repeated chart skeletons.** SVG chart wrappers with the same viewBox/axis logic. Same threshold: 3+ tangible duplicates before suggesting extraction.
7. **API calls not centralized.** Any `axios.get`/`axios.post` outside `client/src/api.js`. Move it.
8. **Mixed Options + Composition API.** A component using `data()` / `methods` alongside `setup()`. Project convention is Composition-only.
9. **Hard-coded strings that should be i18n keys.** User-visible text not routed through `t(...)`. Note location; don't list every string.

### Step 3 — Write the report

Output a markdown report directly in the chat (do **not** create a file unless the user asks). Use this shape:

```markdown
## Vue audit — <scope summary>

### Performance (N findings)

**1. v-for with index key — `views/Restocking.vue:42`**
Problem: `<tr v-for="(item, i) in items" :key="i">` reorders incorrectly when sorted.
Fix: `:key="item.sku"`.

**2. Inline arrow handler in v-for — `views/Orders.vue:88`**
Problem: `@click="() => openModal(o.id)"` re-allocates per render across N rows.
Fix: hoist to `const openOrder = (id) => ...` and use `@click="openOrder(o.id)"`.

### Code reuse (M findings)

**1. `useAsyncData` composable opportunity**
Five views (`Orders`, `Inventory`, `Demand`, `Backlog`, `Spending`) repeat the `loading/error/data + try/finally` block. Extract:
```javascript
// composables/useAsyncData.js
export function useAsyncData(fetcher) {
  const data = ref(null)
  const loading = ref(false)
  const error = ref(null)
  const run = async (...args) => { ... }
  return { data, loading, error, run }
}
```

### Skipped / not applicable
- Deep watchers: none found.
- Mixed API styles: none found.

### Recommended next steps
1. Apply the v-for key fixes (low risk, high signal).
2. Extract `useAsyncData` — touches 5 views, delegate to `vue-expert`.
3. Defer the `DataTable` extraction until a 3rd duplicate appears.
```

Rules for the report:
- **Cite every finding with `file:line`.** No vague "some components do X."
- **Order findings by impact, not by check number.** A v-for-key bug in a hot list beats a stylistic note.
- **Group "Skipped / not applicable"** so the user sees the checklist was complete, not selectively applied.
- **Never include findings you didn't verify** by reading the relevant lines. If grep gave a false-positive context, drop it.
- **Cap the report** at the top ~15 findings. If more exist, end with "N more low-priority findings — ask to expand."

### Step 4 — Handoff

End the report with: "Tell me which findings to act on and I'll delegate the `.vue` edits to `vue-expert`." Do not start editing components in the same turn — the user picks the scope first.

## Anti-patterns this skill must avoid

- **Don't suggest abstractions for 2 occurrences.** Wait for the rule-of-three. Three similar lines is better than a premature abstraction (per project instructions).
- **Don't recommend TypeScript, Pinia, Vue Router upgrades, or build-tool changes** unless the user asked. Stay inside the existing stack.
- **Don't flag style nitpicks** (indentation, naming) — those belong in code review, not a perf/reuse audit.
- **Don't read every file.** Grep first; Read selectively. A typical audit reads 4–6 files in full.
- **Don't write a report file unless asked.** Output in chat.
