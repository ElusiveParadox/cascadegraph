import { expect, test } from "@playwright/test";

const clientSource = `import os
import requests
from requests.exceptions import RequestException
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type
@retry(stop=stop_after_attempt(3), wait=wait_fixed(0), retry=retry_if_exception_type(RequestException))
def call_service():
    return requests.get(os.environ["INVENTORY_URL"], timeout=0.5)
`;
const compose = `services:
  gateway:
    build: gateway
    environment:
      INVENTORY_URL: http://inventory:8000
  inventory:
    build: inventory
`;
const topology = `version: 1
edges:
  - source: gateway
    target: inventory
    policy_symbols: [call_service]
`;

test("missing source guidance leads to a complete files-only analysis", async ({ page }) => {
  const owned: string[] = [];
  try {
    await page.goto("/");
    await expect(page.getByTestId("form-source-intake")).toBeVisible();
    await page.getByTestId("input-source-files").setInputFiles({
      name: "client.py", mimeType: "text/plain", buffer: Buffer.from(clientSource),
    });
    await page.getByTestId("input-source-path-0").fill("gateway/client.py");
    await page.getByTestId("button-analyze-repository").click();
    await expect(page).toHaveURL(/\/analyses\/[^/]+$/);
    owned.push(new URL(page.url()).pathname.split("/").pop()!);
    await expect(page.getByTestId("list-requested-files")).toContainText("compose");
    await page.getByTestId("link-add-source-files").click();
    await page.getByTestId("input-source-files").setInputFiles([
      { name: "client.py", mimeType: "text/plain", buffer: Buffer.from(clientSource) },
      { name: "compose.yaml", mimeType: "text/yaml", buffer: Buffer.from(compose) },
      { name: "cascadegraph.yaml", mimeType: "text/yaml", buffer: Buffer.from(topology) },
    ]);
    await page.getByTestId("input-source-path-0").fill("gateway/client.py");
    await page.getByTestId("button-analyze-repository").click();
    await expect(page).toHaveURL(/\/analyses\/[^/]+$/);
    owned.push(new URL(page.url()).pathname.split("/").pop()!);
    await expect(page.getByTestId("text-stat-services")).toHaveText("2");
    await expect(page.getByTestId("text-stat-edges")).toHaveText("1");
    await expect(page.getByTestId("list-requested-files")).toHaveCount(0);
    const id = owned[1];
    await page.reload();
    await expect(page.getByTestId("text-stat-services")).toHaveText("2");
    const result = await (await page.request.get(`/api/v1/analyses/${id}`)).json();
    expect(result.source_type).toBe("source_files");
    expect(result.edges[0].policy_ids).toHaveLength(1);
  } finally {
    for (const id of owned) await page.request.delete(`/api/v1/analyses/${id}`);
  }
});
