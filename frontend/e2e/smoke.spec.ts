import { expect, test } from "@playwright/test";

test.describe("Diagnosis dashboard smoke test", () => {
  test("runs 8-node demo and shows diagnosis result", async ({ page }) => {
    await page.goto("/");

    // Wait for landing state.
    await expect(page.getByRole("heading", { name: /OptiRCA Lite/i })).toBeVisible();

    // Run demo.
    const runDemoButton = page.getByRole("button", { name: /运行 Demo/i });
    await expect(runDemoButton).toBeVisible();
    await runDemoButton.click();

    // Wait for diagnosis to complete: conclusion bar shows a root cause or degraded state.
    const conclusionBar = page.getByTestId("conclusion-bar");
    await expect(conclusionBar).toHaveAttribute("data-risk", /normal|review|degraded/, {
      timeout: 120000,
    });

    // Verify conclusion bar contains diagnosis status text.
    await expect(conclusionBar).toContainText(/诊断完成|需要人工审核|诊断降级/, {
      timeout: 120000,
    });

    // Wait for playback to finish: assemble stage should be visible and done/running.
    const assembleButton = page.getByRole("button", { name: "组装" });
    await expect(assembleButton).toBeVisible({ timeout: 30000 });

    // Evidence graph should contain the root-cause node if present.
    const rootCauseNode = page.locator('[data-testid^="node-"]').first();
    await expect(rootCauseNode).toBeVisible({ timeout: 30000 });

    // If review is required, the review panel should appear.
    const risk = await page.getByTestId("conclusion-bar").getAttribute("data-risk");
    if (risk === "review") {
      await expect(page.getByRole("complementary").getByText("需要人工审核")).toBeVisible();
      await expect(page.getByRole("button", { name: "批准" })).toBeVisible();
      await expect(page.getByRole("button", { name: "驳回" })).toBeVisible();
      await expect(page.getByRole("button", { name: "升级" })).toBeVisible();
    }
  });
});
