import { expect, test, type Locator } from "@playwright/test";
import { expectKeyboardFocus, expectNoPageOverflow, history, longExcerpt, longPath, mockLayoutData } from "./fixtures/desktop-layout";

const sizes = [
  { name: "wide desktop", viewport: { width: 1600, height: 1000 }, deviceScaleFactor: 1, columns: true, sidebar: true },
  { name: "compact desktop", viewport: { width: 1024, height: 768 }, deviceScaleFactor: 1, columns: false, sidebar: true },
  // Layout-zoom emulation: a 1440×900 desktop at 200% has 720×450 CSS pixels.
  // Double pixel density preserves the physical size. deviceScaleFactor alone
  // (or CDP pinch zoom) would NOT exercise media-query reflow.
  { name: "desktop at 200% zoom (reflow emulation)", viewport: { width: 720, height: 450 }, deviceScaleFactor: 2, columns: false, sidebar: false },
];

async function box(locator: Locator) {
  const bounds = await locator.boundingBox();
  expect(bounds).not.toBeNull();
  return bounds!;
}

for (const size of sizes) {
  test.describe(size.name, () => {
    test.use({ viewport: size.viewport, deviceScaleFactor: size.deviceScaleFactor });
    test.beforeEach(async ({ page }) => { await mockLayoutData(page); });

    test("intake panels reflow and long source paths remain editable", async ({ page }) => {
      await page.goto("/");
      await expect(page.getByTestId("button-analyze-sample")).toBeEnabled();
      await expect(page.getByTestId("text-page-title")).toHaveCSS("font-family", /Poppins/);
      await expect(page.getByTestId("input-repository-ref")).toHaveCSS("font-family", /JetBrains Mono/);
      // Computed colors catch a lost theme stylesheet, not just renamed classes.
      await expect(page.locator("main").locator("..")).toHaveCSS("background-color", "rgb(245, 245, 242)");
      if (size.sidebar) {
        await expect(page.locator("aside > div")).toHaveCSS("background-color", "rgb(19, 18, 21)");
        await expect(page.getByText("retry-policy workbench", { exact: true })).toHaveCSS("font-family", /Georgia/);
      }
      const intake = page.getByTestId("form-source-intake");
      const sample = page.locator("section").filter({ has: page.getByRole("heading", { name: "Bundled sample", exact: true }) });
      const archive = page.locator("section").filter({ has: page.getByRole("heading", { name: "ZIP archive", exact: true }) });
      const intakeBox = await box(intake);
      const sampleBox = await box(sample);
      const archiveBox = await box(archive);
      if (size.columns) {
        expect(sampleBox.x).toBeGreaterThan(intakeBox.x + intakeBox.width);
        expect(Math.abs(sampleBox.y - intakeBox.y)).toBeLessThan(100);
      } else {
        expect(sampleBox.y).toBeGreaterThan(intakeBox.y + intakeBox.height);
      }
      // Both fallbacks remain separate and reachable, with no panel overlap.
      if (size.viewport.width >= 1024 && !size.columns) {
        expect(archiveBox.x).toBeGreaterThan(sampleBox.x + sampleBox.width);
        expect(Math.abs(archiveBox.y - sampleBox.y)).toBeLessThan(1);
      } else {
        expect(archiveBox.y).toBeGreaterThan(sampleBox.y + sampleBox.height);
      }
      await expect(page.getByTestId("button-mobile-nav")).toBeVisible({ visible: !size.sidebar });
      await expect(page.locator("aside")).toBeVisible({ visible: size.sidebar });
      const filename = `${"very-long-source-name-".repeat(10)}client.py`;
      await page.getByTestId("input-source-files").setInputFiles({
        name: filename, mimeType: "text/plain", buffer: Buffer.from("import requests\n"),
      });
      const path = page.getByRole("textbox", { name: `Relative path for ${filename}`, exact: true });
      await path.fill(longPath);
      await expect(path).toHaveValue(longPath);
      await path.press("End");
      await path.press("Shift+Tab");
      await page.keyboard.press("Tab");
      await expectKeyboardFocus(path);
      await page.keyboard.press("Tab");
      const remove = page.getByRole("button", { name: `Remove ${filename}`, exact: true });
      await expectKeyboardFocus(remove);
      await page.keyboard.press("Enter");
      await expect(path).toHaveCount(0);
      await expectNoPageOverflow(page);
    });

    test("skip link, focus indicators and current-page navigation work by keyboard", async ({ page }) => {
      await page.goto("/");
      await expect(page.getByTestId("button-analyze-sample")).toBeEnabled();
      const skip = page.getByRole("link", { name: "Skip to content" });
      expect((await box(skip)).y).toBeLessThan(0);
      await page.keyboard.press("Tab");
      await expectKeyboardFocus(skip);
      await page.keyboard.press("Enter");
      await expect(page.getByRole("main")).toBeFocused();
      await page.keyboard.press("Tab");
      await expectKeyboardFocus(page.getByTestId("input-repository-url"));
      await page.keyboard.press("Tab");
      await expectKeyboardFocus(page.getByTestId("input-repository-ref"));
      await page.keyboard.press("Tab");
      await expectKeyboardFocus(page.getByTestId("input-project-path"));
      // Return to the shell via actual keyboard order, not locator.focus().
      await page.keyboard.press("Shift+Tab");
      await page.keyboard.press("Shift+Tab");
      await page.keyboard.press("Shift+Tab");
      if (!size.sidebar) {
        await expectKeyboardFocus(page.getByTestId("button-mobile-nav"));
        await page.keyboard.press("Enter");
      }
      const nav = page.getByRole("navigation", { name: "Workspace" });
      await expect(nav.locator('[aria-current="page"]')).toHaveCount(1);
      await expect(nav.getByTestId("link-nav-home")).toHaveAttribute("aria-current", "page");
      const disabled = nav.getByTestId("link-nav-analyses");
      await expect(disabled).toHaveAttribute("aria-disabled", "true");
      await expect(disabled).not.toHaveAttribute("href");
      expect(await disabled.evaluate(element => (element as HTMLElement).tabIndex)).toBe(-1);
      // Reach Help from wherever keyboard focus is in the shell. Disabled items
      // must be skipped, and each enabled link must show its focus indicator.
      const help = nav.getByTestId("link-nav-help");
      for (let i = 0; i < 12 && !await help.evaluate(el => el === document.activeElement); i++) {
        await page.keyboard.press(size.sidebar ? "Shift+Tab" : "Tab");
      }
      await expectKeyboardFocus(help);
      await page.keyboard.press("Enter");
      await expect(page).toHaveURL(/\/help$/);
      if (!size.sidebar) {
        await page.getByTestId("button-mobile-nav").press("Enter");
      }
      await expect(nav.locator('[aria-current="page"]')).toHaveCount(1);
      await expect(help).toHaveAttribute("aria-current", "page");
      await expect(nav.getByTestId("link-nav-home")).not.toHaveAttribute("aria-current");
      await expectNoPageOverflow(page);
    });

    if (!size.sidebar) {
      test("compact navigation announces its state, contains focus and closes by keyboard", async ({ page }) => {
        await page.goto("/");
        await expect(page.getByTestId("button-analyze-sample")).toBeEnabled();
        const toggle = page.getByTestId("button-mobile-nav");
        await expect(toggle).toHaveAttribute("aria-expanded", "false");
        const controlledId = await toggle.getAttribute("aria-controls");
        expect(controlledId).toBeTruthy();
        const overlay = page.locator(`[id="${controlledId}"]`);
        await expect(overlay).toBeHidden();
        await page.keyboard.press("Tab"); // Skip link.
        await page.keyboard.press("Tab");
        await expectKeyboardFocus(toggle);
        await page.keyboard.press("Enter");
        await expect(toggle).toHaveAttribute("aria-expanded", "true");
        await expect(overlay).toBeVisible();
        const brand = overlay.getByTestId("link-brand");
        const home = overlay.getByTestId("link-nav-home");
        const validation = overlay.getByTestId("link-nav-validation");
        const help = overlay.getByTestId("link-nav-help");
        await expectKeyboardFocus(brand);
        await page.keyboard.press("Tab");
        await expectKeyboardFocus(home);
        await page.keyboard.press("Tab"); // Disabled analysis links are not stops.
        await expectKeyboardFocus(validation);
        await page.keyboard.press("Tab");
        await expectKeyboardFocus(help);
        await page.keyboard.press("Tab"); // Wrap, never reach the covered intake.
        await expectKeyboardFocus(toggle);
        await page.keyboard.press("Shift+Tab");
        await expectKeyboardFocus(help);
        await page.keyboard.press("Tab");
        await page.keyboard.press("Tab");
        await expectKeyboardFocus(brand);
        await page.keyboard.press("Escape");
        await expect(overlay).toBeHidden();
        await expect(toggle).toHaveAttribute("aria-expanded", "false");
        await expectKeyboardFocus(toggle);
        await page.keyboard.press("Tab");
        await expectKeyboardFocus(page.getByTestId("input-repository-url"));
        // Reopening must install a fresh loop; the toggle can also close it.
        await page.keyboard.press("Shift+Tab");
        await page.keyboard.press("Space");
        await expectKeyboardFocus(brand);
        await page.keyboard.press("Shift+Tab");
        await expectKeyboardFocus(toggle);
        await page.keyboard.press("Enter");
        await expect(toggle).toHaveAttribute("aria-expanded", "false");
        await expectKeyboardFocus(toggle);
        // Route changes close the overlay and restore focus, including same-route links.
        await page.keyboard.press("Enter");
        await page.keyboard.press("Tab");
        await page.keyboard.press("Enter");
        await expect(overlay).toBeHidden();
        await expectKeyboardFocus(toggle);
        await page.keyboard.press("Enter");
        await page.keyboard.press("Shift+Tab");
        await page.keyboard.press("Shift+Tab");
        await expectKeyboardFocus(help);
        await page.keyboard.press("Enter");
        await expect(page).toHaveURL(/\/help$/);
        await expect(toggle).toHaveAttribute("aria-expanded", "false");
        await expectKeyboardFocus(toggle);
        // Switching to the persistent sidebar must remove the compact focus trap.
        await page.keyboard.press("Enter");
        await page.setViewportSize({ width: 1024, height: 768 });
        await expect(toggle).toHaveAttribute("aria-expanded", "false");
        await expect(page.locator("aside")).toBeVisible();
        await page.getByRole("link", { name: "Skip to content" }).focus();
        await page.keyboard.press("Enter");
        await expect(page.getByRole("main")).toBeFocused();
        await page.setViewportSize(size.viewport);
        await expect(toggle).toHaveAttribute("aria-expanded", "false");
        await expect(overlay).toBeHidden();
      });
    }

    test("history and evidence overflow locally without widening the page", async ({ page }) => {
      await page.goto("/");
      const row = page.getByTestId(`row-analysis-${history.id}`);
      await expect(row).toBeVisible();
      const scroller = row.locator("xpath=ancestor::table/parent::*");
      const dimensions = await scroller.evaluate(el => ({
        client: el.clientWidth, scroll: el.scrollWidth, overflow: getComputedStyle(el).overflowX,
      }));
      expect(dimensions.overflow).toBe("auto");
      expect(dimensions.scroll).toBeGreaterThan(dimensions.client);
      await expectNoPageOverflow(page);
      const link = page.getByTestId(`link-analysis-${history.id}`);
      await link.scrollIntoViewIfNeeded();
      // Tab from the link must reveal the otherwise off-screen final column.
      // press() focuses the link and sends a real keyboard event.
      await link.press("Tab");
      const remove = page.getByTestId(`button-delete-${history.id}`);
      await expectKeyboardFocus(remove);
      expect(await scroller.evaluate(el => el.scrollLeft)).toBeGreaterThan(0);
      const scrollBox = await box(scroller);
      const removeBox = await box(remove);
      expect(removeBox.x + removeBox.width).toBeLessThanOrEqual(scrollBox.x + scrollBox.width + 1);
      await expectNoPageOverflow(page);
      await page.keyboard.press("Shift+Tab");
      await expect(link).toBeFocused();
      await page.keyboard.press("Enter");
      await expect(page).toHaveURL(new RegExp(`/analyses/${history.id}$`));
      await expect(page.getByTestId("text-page-title")).toHaveText(`source-${"long-title".repeat(28)}`);
      const evidence = page.getByTestId("button-node-evidence-0");
      await expect(evidence).toContainText(longPath);
      await expect(evidence).toContainText("L123");
      await expect(evidence).toHaveAttribute("aria-expanded", "true");
      const pathLabel = evidence.locator("span").filter({ hasText: longPath });
      expect(await pathLabel.evaluate(el => el.scrollWidth > el.clientWidth)).toBe(true);
      const excerpt = page.locator("pre").filter({ hasText: longExcerpt });
      await expect(excerpt).toBeVisible();
      expect(await excerpt.evaluate(el => el.scrollWidth > el.clientWidth)).toBe(true);
      await excerpt.evaluate(el => { el.scrollLeft = el.scrollWidth; });
      expect(await excerpt.evaluate(el => el.scrollLeft)).toBeGreaterThan(0);
      await evidence.press("Tab");
      await page.keyboard.press("Shift+Tab");
      await expectKeyboardFocus(evidence);
      await page.keyboard.press("Enter");
      await expect(evidence).toHaveAttribute("aria-expanded", "false");
      await expect(excerpt).toHaveCount(0);
      await page.keyboard.press("Space");
      await expect(evidence).toHaveAttribute("aria-expanded", "true");
      await expect(excerpt).toContainText(longExcerpt);
      await expectNoPageOverflow(page);
    });
  });
}
