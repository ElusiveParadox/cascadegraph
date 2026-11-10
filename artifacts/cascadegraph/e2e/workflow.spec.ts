import { expect, test } from "@playwright/test";

test("inspect, correct, simulate, export and delete an owned analysis", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", e => errors.push(e.message));
  await page.goto("/");
  await expect(page.getByTestId("checkbox-sample-ai")).not.toBeChecked();
  await page.getByTestId("button-analyze-sample").click();
  await expect(page).toHaveURL(/\/analyses\/[^/]+$/);
  const id = new URL(page.url()).pathname.split("/").pop()!;
  await expect(page.getByTestId("text-stat-services")).toHaveText("3");
  await expect(page.getByTestId("text-stat-edges")).toHaveText("2");
  await page.getByTestId("link-to-policies").click();
  await page.getByRole("button", { name: /call_order/ }).click();
  await page.getByTestId("input-max-attempts").fill("2");
  await page.getByTestId("input-policy-note").fill("E2E source-backed correction");
  await page.getByTestId("button-confirm-policy").click();
  await expect(page.getByText("Saved. Future simulations", { exact: false })).toBeVisible();
  await page.reload();
  await expect(page.getByTestId("text-max-total-attempts")).toHaveText("2");
  const saved = await (await page.request.get(`/api/v1/analyses/${id}`)).json();
  const policy = saved.policies.find((p: { symbol: string }) => p.symbol === "call_order");
  expect(policy.source_value).toBe(3);
  expect(policy.confirmed).toBe(true);

  await page.goto(`/simulation/${id}`);
  await page.getByTestId("input-requests").fill("5");
  await page.getByTestId("input-failure_rate").fill("1");
  await page.getByTestId("input-arrival_rate").fill("0.2");
  await page.getByTestId("input-candidate_attempts").fill("1");
  await page.getByTestId("button-run-simulation").click();
  await expect(page).toHaveURL(/\/comparison\/[^/]+$/);
  const baseline = page.getByTestId("text-amplification-baseline");
  const candidate = page.getByTestId("text-amplification-candidate");
  await expect(baseline).toBeVisible();
  expect(parseFloat((await baseline.textContent())!)).toBeGreaterThan(
    parseFloat((await candidate.textContent())!),
  );
  await page.getByTestId("link-report").click();
  const download = page.waitForEvent("download");
  await page.getByTestId("button-download-report").click();
  expect((await download).suggestedFilename()).toMatch(/cascadegraph-report-.+\.json/);
  await page.reload();
  await expect(page.getByTestId("button-download-report")).toBeVisible();

  await page.goto("/");
  const row = page.getByTestId(`row-analysis-${id}`);
  await page.getByTestId(`button-delete-${id}`).click();
  await page.getByTestId("button-cancel-delete").click();
  await expect(row).toBeVisible();
  await page.getByTestId(`button-delete-${id}`).click();
  await page.getByTestId("button-confirm-delete").click();
  await expect(row).toHaveCount(0);
  expect((await page.request.get(`/api/v1/analyses/${id}`)).status()).toBe(404);
  expect(errors).toEqual([]);
});
