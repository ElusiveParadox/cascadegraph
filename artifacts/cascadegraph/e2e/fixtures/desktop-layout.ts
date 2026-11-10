import type { Analysis, AnalysisSummary, SystemStatus } from "@workspace/api-client-react";
import { expect, type Locator, type Page } from "@playwright/test";

export const longPath = `${"services/".repeat(30)}inventory/client.py`;
export const longExcerpt = `response = requests.get("${"inventory-endpoint".repeat(35)}")`;
export const history: AnalysisSummary = {
  id: "layout-fixture",
  name: `repository${"UnbrokenName".repeat(50)}`,
  source_type: "source_files",
  status: "complete",
  created_at: "2026-11-10T10:00:00Z",
  expires_at: "2026-11-11T10:00:00Z",
  file_count: 1,
  service_count: 1,
  policy_count: 0,
};
export const status: SystemStatus = {
  version: "1.0.0", model_version: "layout-fixture", ai_available: false,
  ai_provider: "none", storage: "test", supported_parsers: [], limitations: [],
  max_archive_mb: 50, max_files: 2000, max_expanded_mb: 200,
  max_source_mb: 20, max_file_kb: 512, max_source_files: 100,
};
const analysis: Analysis = {
  ...history,
  // Also exercise the shared PageHeader with an unbroken title.
  name: `source-${"long-title".repeat(28)}`,
  fingerprint: "a".repeat(64),
  nodes: [{
    id: "inventory", name: "inventory", startup_dependencies: [],
    evidence: [{ path: longPath, line_start: 123, line_end: 123, excerpt: longExcerpt, sha256: "b".repeat(64) }],
  }],
  edges: [], policies: [], findings: [], stages: [], assumptions: [],
};

export async function mockLayoutData(page: Page) {
  // These fixtures are presentation-only: never create, mutate or delete server data.
  await page.route("**/api/v1/status", route => route.fulfill({ json: status }));
  await page.route("**/api/v1/analyses", async route => {
    expect(route.request().method()).toBe("GET");
    await route.fulfill({ json: [history] });
  });
  await page.route(`**/api/v1/analyses/${history.id}`, async route => {
    expect(route.request().method()).toBe("GET");
    await route.fulfill({ json: analysis });
  });
}

export async function expectNoPageOverflow(page: Page) {
  const dimensions = await page.evaluate(() => ({
    viewport: window.innerWidth,
    document: document.documentElement.scrollWidth,
    body: document.body.scrollWidth,
  }));
  expect(dimensions.document).toBeLessThanOrEqual(dimensions.viewport + 1);
  expect(dimensions.body).toBeLessThanOrEqual(dimensions.viewport + 1);
}

export async function expectKeyboardFocus(locator: Locator) {
  await expect(locator).toBeFocused();
  // Assert the computed indicator, not merely a focus class or DOM focus.
  const focus = await locator.evaluate(element => {
    const css = getComputedStyle(element);
    const box = element.getBoundingClientRect();
    return {
      visible: element.matches(":focus-visible"),
      outlineStyle: css.outlineStyle,
      outlineWidth: parseFloat(css.outlineWidth),
      outlineColor: css.outlineColor,
      inViewport: box.left >= 0 && box.right <= innerWidth + 1 && box.top >= 0 && box.bottom <= innerHeight + 1,
    };
  });
  expect(focus.visible).toBe(true);
  expect(focus.outlineStyle).toBe("solid");
  expect(focus.outlineWidth).toBeGreaterThanOrEqual(2);
  expect(focus.outlineColor).not.toBe("rgba(0, 0, 0, 0)");
  expect(focus.inViewport, `Focused control is outside viewport: ${JSON.stringify(focus)}`).toBe(true);
}
