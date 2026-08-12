import { expect, test } from "@playwright/test";

test.describe("OptiRCA diagnosis workbench", () => {
  test("loads the real demo, runs diagnosis, and records human confirmation", async ({ page }) => {
    const consoleErrors: string[] = [];
    page.on("console", (message) => {
      if (message.type() === "error") consoleErrors.push(message.text());
    });

    await page.goto("/");
    await expect(page.getByRole("heading", { name: "从并发告警中，定位一个可执行的物理根因" })).toBeVisible();

    await page.getByRole("button", { name: /加载真实 Demo/ }).click();
    await expect(page.getByText("输入已就绪")).toBeVisible({ timeout: 30000 });
    await expect(page.getByText("8", { exact: true }).first()).toBeVisible();
    await expect(page.getByText("权威拓扑 · 可信度 100%")).toBeVisible();

    await page.getByRole("button", { name: "开始诊断" }).click();
    await expect(page.getByText("诊断运行中", { exact: false })).toBeVisible();
    await expect(page.getByTestId("conclusion-card")).toContainText("N1-N2 光纤链路故障", {
      timeout: 120000,
    });
    await expect(page.getByTestId("demo-expectation")).toContainText("根因匹配");
    await expect(page.getByTestId("business-topology")).toBeVisible();

    const stageLabels = ["告警解析", "拓扑构建", "传播判断", "根因排序", "可信度复核", "案卷组装"];
    for (const label of stageLabels) await expect(page.getByText(label, { exact: true })).toBeVisible();

    await page.getByRole("button", { name: "确认根因" }).click();
    await expect(page.getByText("反馈已写入诊断案卷")).toBeVisible();
    await expect(page.getByText("已人工确认系统根因")).toBeVisible();

    expect(consoleErrors).toEqual([]);
  });
});
