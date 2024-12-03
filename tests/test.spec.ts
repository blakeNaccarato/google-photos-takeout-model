import { test } from "@playwright/test";

test("test", async ({ page }) => {
  // TODO: Update URL
  // await page.goto("");
  await page
    .getByRole("checkbox", {
      name: "Photo - Portrait - Aug 8, 2021, 3:19:02 PM",
    })
    .click();
  await page
    .getByRole("checkbox", {
      name: "Photo - Portrait - Aug 8, 2021, 3:24:39 PM",
    })
    .click({
      modifiers: ["Shift"],
    });
  await page.getByRole("button", { name: "More options" }).click();
  await page.getByText("Move to trash").click();
  await page.getByRole("button", { name: "Cancel" }).click();
});
