import { expect, test, type Page } from "@playwright/test";
import { mockLayoutData, status } from "./fixtures/desktop-layout";

async function transfer(page: Page, files: { name: string; size?: number }[]) {
  return page.evaluateHandle(items => {
    const data = new DataTransfer();
    for (const item of items) data.items.add(new File(["x".repeat(item.size ?? 1)], item.name));
    return data;
  }, files);
}

test.beforeEach(async ({ page }) => {
  await mockLayoutData(page);
  await page.goto("/");
  await expect(page.getByTestId("button-analyze-sample")).toBeEnabled();
});

test("ZIP drop feedback, rejected batches, selection retention and keyboard picker", async ({ page }) => {
  let posts = 0;
  page.on("request", request => { if (request.method() === "POST") posts += 1; });
  const zone = page.getByTestId("drop-archive");
  const valid = await transfer(page, [{ name: "repository.zip", size: 1024 }]);
  await zone.dispatchEvent("dragenter", { dataTransfer: valid });
  await expect(zone).toHaveAttribute("data-dragging", "true");
  await expect(zone).toContainText("Drop files to select");
  await zone.dispatchEvent("dragleave", { dataTransfer: valid });
  await expect(zone).toHaveAttribute("data-dragging", "false");
  await zone.dispatchEvent("drop", { dataTransfer: valid });
  await expect(zone).toContainText("repository.zip · 1.0 KiB selected");
  await expect(page.getByTestId("button-upload-archive")).toBeEnabled();
  await zone.dispatchEvent("drop", { dataTransfer: await transfer(page, [{ name: "bad.tar" }]) });
  await expect(zone.getByRole("alert")).toContainText("Only .zip");
  await zone.dispatchEvent("drop", { dataTransfer: await transfer(page, [{ name: "a.zip" }, { name: "b.zip" }]) });
  await expect(zone.getByRole("alert")).toContainText("one ZIP");
  await expect(zone).toContainText("repository.zip · 1.0 KiB selected");
  const choose = page.getByTestId("button-choose-archive");
  await choose.focus();
  const chooser = page.waitForEvent("filechooser");
  await page.keyboard.press("Enter");
  await (await chooser).setFiles({ name: "keyboard.zip", mimeType: "application/zip", buffer: Buffer.from("zip") });
  await expect(zone).toContainText("keyboard.zip");
  await expect(zone.getByRole("alert")).toHaveCount(0);
  await expect(page.getByTestId("checkbox-zip-ai")).not.toBeChecked();
  await expect(page).toHaveURL(/\/$/);
  expect(posts).toBe(0);
});

test("source drops append, validate, retain paths and never auto-submit", async ({ page }) => {
  let posts = 0;
  page.on("request", request => { if (request.method() === "POST") posts += 1; });
  const zone = page.getByTestId("drop-source-files");
  await page.getByTestId("input-repository-url").fill("https://github.com/example/repo");
  await page.getByTestId("input-project-path").fill("gateway");
  await zone.dispatchEvent("drop", { dataTransfer: await transfer(page, [{ name: "client.py" }]) });
  await expect(page.getByTestId("input-source-path-0")).toHaveValue("gateway/client.py");
  await page.getByTestId("input-source-path-0").fill("gateway/custom.py");
  await zone.dispatchEvent("drop", { dataTransfer: await transfer(page, [{ name: "compose.yaml" }]) });
  await expect(zone.getByRole("status")).toContainText("2 source files selected");
  await zone.dispatchEvent("drop", { dataTransfer: await transfer(page, [{ name: "valid.py" }, { name: "bad.exe" }]) });
  await expect(zone.getByRole("alert")).toContainText("bad.exe");
  await expect(zone.getByRole("status")).toContainText("2 source files selected");
  await zone.dispatchEvent("drop", { dataTransfer: await transfer(page, [{ name: "large.py", size: 512 * 1024 + 1 }]) });
  await expect(zone.getByRole("alert")).toContainText("512 KiB");
  await expect(page.getByTestId("input-source-path-0")).toHaveValue("gateway/custom.py");
  await expect(page.getByTestId("input-repository-url")).toHaveValue("https://github.com/example/repo");
  await expect(page.getByTestId("checkbox-repository-ai")).not.toBeChecked();
  expect(posts).toBe(0);
  await expect(page).toHaveURL(/\/$/);
  await page.route("**/api/v1/analyses/sources", route => route.fulfill({
    status: 422, json: { detail: "Fixture: inspect submission without analyzing" },
  }));
  const request = page.waitForRequest("**/api/v1/analyses/sources");
  await page.getByTestId("button-analyze-repository").click();
  const payload = (await request).postDataBuffer()!.toString();
  for (const value of ['name="files"; filename="client.py"', 'name="paths"', "gateway/custom.py", "gateway/compose.yaml",
    'name="repository_url"', "https://github.com/example/repo", 'name="project_path"', "gateway", 'name="ref"', 'name="use_ai"', "false"]) {
    expect(payload).toContain(value);
  }
});

test("live server limits reject oversize ZIPs and cumulative source counts immediately", async ({ page }) => {
  await page.route("**/api/v1/status", route => route.fulfill({
    json: { ...status, max_archive_mb: 1, max_source_files: 2, max_file_kb: 2 },
  }));
  await page.reload();
  await expect(page.getByTestId("button-analyze-sample")).toBeEnabled();
  const zip = page.getByTestId("drop-archive");
  await zip.dispatchEvent("drop", { dataTransfer: await transfer(page, [{ name: "large.zip", size: 1024 ** 2 + 1 }]) });
  await expect(zip.getByRole("alert")).toContainText("1 MiB");
  await expect(page.getByTestId("button-upload-archive")).toBeDisabled();
  await page.getByTestId("input-archive").setInputFiles({ name: "large.zip", mimeType: "application/zip", buffer: Buffer.alloc(1024 ** 2 + 1) });
  await expect(zip.getByRole("alert")).toContainText("1 MiB");
  const source = page.getByTestId("drop-source-files");
  await source.dispatchEvent("drop", { dataTransfer: await transfer(page, [{ name: "large.py", size: 2049 }]) });
  await expect(source.getByRole("alert")).toContainText("2 KiB");
  await source.dispatchEvent("drop", { dataTransfer: await transfer(page, [{ name: "a.py" }, { name: "b.py" }]) });
  await source.dispatchEvent("drop", { dataTransfer: await transfer(page, [{ name: "c.py" }]) });
  await expect(source.getByRole("alert")).toContainText("at most 2 source files");
  await expect(source.getByRole("status")).toContainText("2 source files selected");
});

test("native source picker remains keyboard reachable and uses the same validation", async ({ page }) => {
  const picker = page.getByTestId("input-source-files");
  await page.getByTestId("input-project-path").focus();
  await page.keyboard.press("Tab");
  await expect(picker).toBeFocused();
  const chooser = page.waitForEvent("filechooser");
  await page.keyboard.press("Space");
  await (await chooser).setFiles({ name: "keyboard.py", mimeType: "text/plain", buffer: Buffer.from("import requests") });
  await expect(page.getByTestId("input-source-path-0")).toHaveValue("keyboard.py");
  await picker.setInputFiles({ name: "wrong.zip", mimeType: "application/zip", buffer: Buffer.from("zip") });
  await expect(page.getByTestId("drop-source-files").getByRole("alert")).toContainText("wrong.zip");
  await expect(page.getByTestId("input-source-path-0")).toHaveValue("keyboard.py");
});
