import { expect, test } from "@playwright/test";

test("backend gated runtime readiness page keeps browser-safe summary details", async ({ page }) => {
  await page.goto("/ui/ready");

  await expect(page.getByRole("heading", { name: "Check whether this workspace is ready for real runs" })).toBeVisible();
  await expect(page.getByTestId("runtime-readiness-overall")).toBeVisible();
  await expect(page.getByTestId("runtime-readiness-check-config_file")).toBeVisible();
  await expect(page.getByTestId("runtime-readiness-check-external_roots")).toBeVisible();
  await expect(page.getByTestId("runtime-readiness-check-watch_folder")).toBeVisible();
  await expect(page.getByTestId("runtime-readiness-check-downloads_watch_dir")).toBeVisible();
  await expect(page.getByTestId("runtime-readiness-check-pdf_storage_dir")).toBeVisible();
  await expect(page.getByTestId("runtime-readiness-check-runtime_storage")).toBeVisible();
  await expect(page.getByTestId("runtime-readiness-check-ui_bundle")).toBeVisible();
  await expect(page.getByTestId("runtime-readiness-check-backend_runtime")).toBeVisible();
  await expect(page.getByTestId("runtime-readiness-check-runtime_db")).toHaveCount(0);
  await expect(page.getByTestId("runtime-readiness-check-storage_root")).toHaveCount(0);
  await expect(page.getByTestId("runtime-readiness-check-logs_root")).toHaveCount(0);
  await expect(page.getByTestId("runtime-readiness-check-cache_root")).toHaveCount(0);
  await expect(page.getByTestId("runtime-readiness-check-backend_entrypoint")).toHaveCount(0);
  await expect(page.getByText(/^Path:/)).toHaveCount(0);
  await expect(page.getByTestId("runtime-readiness-fallback")).toHaveCount(0);
});
