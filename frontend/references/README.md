# UI/UX Intake Notes

Source bundle:
- `/Users/jangseongjin/Downloads/Design UI_UX Enhancements-2.zip`

Applied priority:
1. Master spec is source of truth for layout/flow/cognitive-load rules.
2. Zip is material source only.

Imported as reusable material:
- `shadcn-ui` minimum set:
  - `button.tsx`, `card.tsx`, `badge.tsx`, `input.tsx`, `label.tsx`
  - `select.tsx`, `tabs.tsx`, `table.tsx`
  - `separator.tsx`, `switch.tsx`, `scroll-area.tsx`, `progress.tsx`
  - `utils.ts`
- Theme reference:
  - `theme.from-zip.css` (structure reference only)

Explicitly excluded:
- `src/app/App.tsx` visual language
  - glassmorphism, glow-heavy gradients, strong motion patterns
  - not aligned with current Lattice/PaperPipe operational UI tone

Current runtime UI implementation:
- `/ui` (served from `frontend/index.html`)
- Theme tokens standardized to `--pp-*` in `frontend/styles/pp-theme.css`
