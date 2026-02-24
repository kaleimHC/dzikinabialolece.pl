# Visual Baselines — Current Dark (pre-token-migration)

Captured: 2026-05-27
Git HEAD: 0daf82251c21ed2229416666297e2889d35dd2a8
Theme: Current Dark (default, no theme system yet)
Browser: Playwright Chromium headless
Desktop viewport: 1280×800
Mobile viewport: 390×844 (iPhone 14 equiv)
URL: http://localhost:5173

## Files

### desktop/
- `01_initial_load.png` — App load, map visible, no overlays active (733KB)
- `02_risk_map_on.png` — Risk grid overlay visible (688KB)
- `03_risk_and_population_on.png` — Both risk + population overlays on (762KB)
- `04_fresh_load_full_ui.png` — Full UI: header + ModeToggle (top-right) + RecalcPanel (733KB)
- `05_research_panel_pipeline_tab.png` — Research panel open, Konfiguracja tab (98KB)
- `06_research_panel_docs_tab.png` — Research panel, Dokumentacja tab (155KB)
- `07_research_panel_code_tab.png` — Research panel, Kod tab (154KB)
- `08_research_panel_literature_tab.png` — Research panel, Literatura tab (185KB)

### mobile/
- `01_mobile_initial_load.png` — App load on mobile (252KB)
- `02_mobile_bottom_pills.png` — Mobile UI with Próba + Warstwy bottom pills (252KB)
- `03_mobile_proba_bar_open.png` — Próba bottom bar expanded (219KB)
- `04_mobile_warstwy_bar_open.png` — Warstwy bottom bar expanded (192KB)

## Usage

These are pre-migration reference screenshots. After Phase 1 (tiered token migration),
re-run capture and diff against these files to verify zero regressions.
