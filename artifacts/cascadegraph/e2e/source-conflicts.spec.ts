import { mkdtemp, mkdir, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { expect, test, type Page } from "@playwright/test";
import { mockLayoutData, status } from "./fixtures/desktop-layout";

const upload = (name: string, content: string) => ({ name, mimeType: "text/plain", buffer: Buffer.from(content) });
async function submission(page: Page) {
  // Chromium omits disk-backed folder uploads from request.postDataBuffer().
  // Inspect the actual FormData passed to fetch, then forward it unchanged.
  await page.evaluate(() => {
    const original = window.fetch.bind(window);
    window.fetch = async (input, init) => {
      if (String(input).endsWith("/api/v1/analyses/sources") && init?.body instanceof FormData) {
        const fields = await Promise.all([...init.body.entries()].map(async ([key, value]) =>
          `${key}: ${value instanceof File ? `${value.name}\n${await value.text()}` : value}`));
        (window as Window & { sourcePayload?: string }).sourcePayload = fields.join("\n");
      }
      return original(input, init);
    };
  });
  await page.route("**/api/v1/analyses/sources", route => route.fulfill({
    status: 422, json: { detail: "Fixture: inspect explicit submission" },
  }));
  const request = page.waitForRequest("**/api/v1/analyses/sources");
  await page.getByTestId("button-analyze-repository").click();
  await request;
  return page.evaluate(() => (window as Window & { sourcePayload?: string }).sourcePayload!);
}

test.beforeEach(async ({ page }) => {
  await mockLayoutData(page);
  await page.route("**/api/v1/status", route => route.fulfill({ json: { ...status, max_source_files: 3 } }));
  await page.goto("/");
  await expect(page.getByTestId("input-source-files")).toBeEnabled();
});

test("single-file keep, cancel and replace preserve edits and wait for explicit Analyze", async ({ page }) => {
  let posts = 0;
  page.on("request", req => { if (req.method() === "POST") posts++; });
  const picker = page.getByTestId("input-source-files");
  await picker.setInputFiles([upload("client.py", "ORIGINAL"), upload("compose.yaml", "UNAFFECTED")]);
  await page.getByTestId("input-source-path-1").fill("edited/compose.yaml");
  await picker.setInputFiles([upload("client.py", "KEPT_OUT"), upload("retry.py", "ADDED")]);
  const dialog = page.getByRole("alertdialog");
  await expect(dialog).toContainText("client.py");
  await expect(page.getByTestId("button-analyze-repository")).toBeDisabled();
  await dialog.getByRole("button", { name: "Keep existing", exact: true }).click();
  await expect(page.getByTestId("input-source-path-2")).toHaveValue("retry.py");
  await picker.setInputFiles([upload("client.py", "CANCELLED"), upload("extra.py", "DISCARDED")]);
  await dialog.getByRole("button", { name: "Cancel", exact: true }).click();
  await expect(page.locator('[data-testid^="input-source-path-"]')).toHaveCount(3);
  await picker.setInputFiles(upload("client.py", "REPLACED"));
  await dialog.getByRole("button", { name: "Replace", exact: true }).click();
  await expect(page.getByTestId("input-source-path-1")).toHaveValue("edited/compose.yaml");
  expect(posts).toBe(0);
  const payload = await submission(page);
  for (const value of ["REPLACED", "UNAFFECTED", "edited/compose.yaml", "ADDED"]) expect(payload).toContain(value);
  for (const value of ["ORIGINAL", "KEPT_OUT", "CANCELLED", "DISCARDED"]) expect(payload).not.toContain(value);
});

test("nested folder reselection at capacity replaces only matching paths and rejects overflow atomically", async ({ page }) => {
  const temp = await mkdtemp(path.join(os.tmpdir(), "cascadegraph-conflicts-"));
  try {
    const root = path.join(temp, "repository");
    await mkdir(path.join(root, "services"), { recursive: true });
    await writeFile(path.join(root, "services/client.py"), "OLD_NESTED");
    await writeFile(path.join(root, "compose.yaml"), "COMPOSE");
    await page.getByTestId("input-project-path").fill("app");
    const picker = page.getByTestId("input-source-folder");
    await picker.setInputFiles(root);
    const paths = page.locator('[data-testid^="input-source-path-"]');
    await expect(paths).toHaveCount(2);
    const composePath = page.getByRole("textbox", { name: "Relative path for compose.yaml", exact: true });
    await expect(composePath).toHaveValue("app/compose.yaml");
    await expect(page.getByRole("textbox", { name: "Relative path for client.py", exact: true })).toHaveValue("app/services/client.py");
    await composePath.fill("edited/compose.yaml");
    await page.getByTestId("input-source-files").setInputFiles(upload("keep.py", "KEEP"));
    // Keep the original disk-backed files intact while selecting new versions.
    const incoming = path.join(temp, "incoming/repository");
    await mkdir(path.join(incoming, "services"), { recursive: true });
    await writeFile(path.join(incoming, "services/client.py"), "NEW_NESTED");
    await writeFile(path.join(incoming, "compose.yaml"), "NEW_COMPOSE");
    // The edited compose path is intentionally a new path on re-selection.
    await picker.setInputFiles(incoming);
    const dialog = page.getByRole("alertdialog");
    await expect(dialog).toContainText("app/services/client.py");
    await dialog.getByRole("button", { name: "Replace", exact: true }).click();
    await expect(page.getByTestId("drop-source-files").getByRole("alert")).toContainText("at most 3");
    await expect(paths).toHaveCount(3);
    await expect(composePath).toHaveValue("edited/compose.yaml");
    // Remove the nonconflicting incoming file, then repeat the same folder.
    await rm(path.join(incoming, "compose.yaml"));
    await picker.setInputFiles(incoming);
    await dialog.getByRole("button", { name: "Replace", exact: true }).click();
    await expect(paths).toHaveCount(3);
    const payload = await submission(page);
    for (const value of ["NEW_NESTED", "edited/compose.yaml", "COMPOSE", "KEEP"]) expect(payload).toContain(value);
    expect(payload).not.toContain("OLD_NESTED");
  } finally {
    await rm(temp, { recursive: true, force: true });
  }
});
