/**
 * Smoke test — Zustand store przełączanie trybów.
 *
 * Wykrywa regresję w sightingsStore.js przy refaktorze:
 * - toggleFastGrid/toggleHeatmap/toggleResearchGrid
 * - setDisplayMode
 * - completeOnboarding
 *
 * Uruchom: npm test
 */
import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { useSightingsStore } from "./sightingsStore";

describe("sightingsStore — tryby wyświetlania", () => {
  beforeEach(() => {
    useSightingsStore.setState({
      displayMode: "fast",
      showFastGrid: true,
      showHeatmap: true,
      showResearchGrid: true,
      linkedToggles: false,
    });
  });

  it("setDisplayMode zmienia na publication", () => {
    useSightingsStore.getState().setDisplayMode("publication");
    expect(useSightingsStore.getState().displayMode).toBe("publication");
  });

  it("setDisplayMode zmienia na research", () => {
    useSightingsStore.getState().setDisplayMode("research");
    expect(useSightingsStore.getState().displayMode).toBe("research");
  });

  it("setDisplayMode z research wyłącza wMatrix", () => {
    useSightingsStore.setState({
      displayMode: "research",
      visibleLayers: { wMatrix: true, population: false },
    });
    useSightingsStore.getState().setDisplayMode("fast");
    expect(useSightingsStore.getState().visibleLayers.wMatrix).toBe(false);
  });

  it("toggleFastGrid odwraca widoczność", () => {
    const przed = useSightingsStore.getState().showFastGrid;
    useSightingsStore.getState().toggleFastGrid();
    expect(useSightingsStore.getState().showFastGrid).toBe(!przed);
  });

  it("toggleHeatmap odwraca widoczność", () => {
    const przed = useSightingsStore.getState().showHeatmap;
    useSightingsStore.getState().toggleHeatmap();
    expect(useSightingsStore.getState().showHeatmap).toBe(!przed);
  });

  it("toggleResearchGrid odwraca widoczność", () => {
    const przed = useSightingsStore.getState().showResearchGrid;
    useSightingsStore.getState().toggleResearchGrid();
    expect(useSightingsStore.getState().showResearchGrid).toBe(!przed);
  });
});

describe("sightingsStore — onboarding", () => {
  afterEach(() => {
    localStorage.removeItem("dziki-onboarded");
  });

  it("completeOnboarding ustawia hasSeenOnboarding i zapisuje do localStorage", () => {
    useSightingsStore.setState({ hasSeenOnboarding: false });
    useSightingsStore.getState().completeOnboarding();
    expect(useSightingsStore.getState().hasSeenOnboarding).toBe(true);
    expect(localStorage.getItem("dziki-onboarded")).toBe("1");
  });
});
