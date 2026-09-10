/**
 * Headed end-to-end walkthrough: login → opportunity → transcript → framework → PPT.
 * Leaves the browser open when the deck is ready.
 *
 * Resume after framework exists:
 *   $env:E2E_OPPORTUNITY_ID="..."; node scripts/e2e_full_pipeline_headed.mjs
 */
import { chromium } from "playwright";
import { mkdir } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { existsSync, readFileSync } from "node:fs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const SHOTS = join(ROOT, ".tmp_e2e", "headed");
const LONG_WAIT_MS = 720_000;

function loadEnv() {
  const path = join(ROOT, ".env");
  if (!existsSync(path)) return;
  for (const line of readFileSync(path, "utf8").split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#") || !trimmed.includes("=")) continue;
    const idx = trimmed.indexOf("=");
    const key = trimmed.slice(0, idx).trim();
    const value = trimmed.slice(idx + 1).trim();
    if (!process.env[key]) process.env[key] = value;
  }
}

loadEnv();

const WEB = process.env.NEXT_PUBLIC_WEB_URL || "http://localhost:3000";
const EMAIL = process.env.E2E_TEST_EMAIL;
const PASSWORD = process.env.E2E_TEST_PASSWORD;
const EXISTING_OPPORTUNITY_ID = process.env.E2E_OPPORTUNITY_ID?.trim() || "";

if (!EMAIL || !PASSWORD) {
  console.error("Missing E2E_TEST_EMAIL or E2E_TEST_PASSWORD in .env");
  process.exit(1);
}

async function shot(page, name) {
  await mkdir(SHOTS, { recursive: true });
  const path = join(SHOTS, `${name}.png`);
  await page.screenshot({ path, fullPage: false });
  console.log(`[SHOT] ${path}`);
}

async function dumpFailure(page, error) {
  console.error("[FAIL]", error instanceof Error ? error.message : error);
  try {
    console.error("[URL]", page.url());
    const banner = await page.locator(".upload-banner, .alert, [role='alert']").allTextContents();
    if (banner.length) console.error("[BANNER]", banner.join(" | "));
    await shot(page, `fail-${Date.now()}`);
  } catch {
    /* ignore screenshot errors */
  }
}

async function signIn(page) {
  console.log(`[STEP] Sign in as ${EMAIL}`);
  await page.goto(`${WEB}/login`, { waitUntil: "networkidle" });
  await page.locator("#email").waitFor({ state: "visible" });
  await page.waitForTimeout(800);
  await page.locator("#email").click();
  await page.locator("#email").fill(EMAIL);
  await page.locator("#password").click();
  await page.locator("#password").fill(PASSWORD);
  if ((await page.locator("#email").inputValue()) !== EMAIL) {
    throw new Error("Email field did not keep the test account value");
  }
  await page.locator('form.auth-form button[type="submit"]').click();
  await page.waitForURL((url) => !url.pathname.includes("/login"), { timeout: 20_000 });
  await page.waitForSelector('[data-testid="auth-ready"], .site-nav-new, a:has-text("Create presentation")', {
    timeout: 20_000,
  });
  await shot(page, "01-signed-in");
}

async function createAndUpload(page) {
  console.log("[STEP] Start a new presentation");
  await page.goto(`${WEB}/upload?new=1`, { waitUntil: "domcontentloaded" });
  await page.waitForSelector('[data-testid="auth-ready"]', { state: "attached", timeout: 20_000 });
  await page.getByLabel("Client name").fill("ABC Systems");
  await page.getByLabel("Opportunity name").fill(`Q2 PO confirmation ${Date.now()}`);
  await page.getByLabel("Department").fill("Order Management");

  const createResponsePromise = page.waitForResponse(
    (response) =>
      response.url().includes("/opportunities") &&
      response.request().method() === "POST" &&
      !response.url().includes("/transcripts"),
    { timeout: 20_000 },
  );
  await page.getByRole("button", { name: "Create opportunity" }).click();
  const createResponse = await createResponsePromise;
  if (!createResponse.ok()) {
    throw new Error(`Create opportunity failed: HTTP ${createResponse.status()} ${await createResponse.text()}`);
  }
  await page.getByText("Opportunity created").waitFor({ timeout: 15_000 });
  await shot(page, "02-opportunity");
  console.log("[OK] Opportunity created");

  console.log("[STEP] Upload discovery transcript");
  await page.getByRole("button", { name: "Add sample transcript" }).click();
  await page.locator(".file-name", { hasText: "abc_systems_q2_automation_rollout.txt" }).waitFor();
  await page.getByRole("button", { name: /Upload 1 file/ }).click();
  await page.getByText("transcript ingested successfully", { exact: false }).waitFor({
    timeout: 30_000,
  });
  await shot(page, "03-transcript-uploaded");
  console.log("[OK] Transcript uploaded");

  console.log("[STEP] Open framework review");
  await page.getByRole("link", { name: "Review framework" }).click();
  await page.waitForURL("**/framework-review**", { timeout: 15_000 });
}

async function generateIfNeeded(page) {
  const generateButton = page.getByRole("button", { name: "Generate customer story" });
  const summary = page.getByTestId("framework-review-summary");
  if (await summary.isVisible().catch(() => false)) {
    console.log("[OK] Customer story already present");
    await shot(page, "05-framework-ready");
    return;
  }
  await page.getByRole("heading", { name: "Generate the customer story" }).waitFor({
    timeout: 20_000,
  });
  await shot(page, "04-framework-empty");
  console.log("[STEP] Generate customer story (live LLM — this can take several minutes)");
  await generateButton.click();
  await summary.waitFor({ timeout: LONG_WAIT_MS });
  const failedBanner = page.locator(".upload-banner").filter({ hasText: /failed|could not|error/i });
  if (await failedBanner.first().isVisible().catch(() => false)) {
    throw new Error(`Framework generation failed: ${(await failedBanner.first().innerText()).slice(0, 500)}`);
  }
  await shot(page, "05-framework-ready");
  console.log("[OK] Customer story generated");
}

async function approveAndBuild(page) {
  if (await page.getByTestId("framework-blocking-banner").isVisible().catch(() => false)) {
    const blocked = await page.getByTestId("framework-blocking-banner").innerText();
    throw new Error(`Approval is blocked:\n${blocked}`);
  }

  console.log("[STEP] Approve and build presentation");
  const retryPlan = page.getByRole("button", { name: /Generate plan again|Try again|Reconnect/i });
  const buildConfirmed = page.getByRole("button", { name: "Build presentation" });
  const checkbox = page.getByTestId("framework-human-confirm");
  if (await retryPlan.first().isVisible().catch(() => false)) {
    await retryPlan.first().click();
  } else if (await checkbox.isVisible().catch(() => false)) {
    await page.locator('[data-testid="framework-human-confirm"]:not([disabled])').waitFor({
      timeout: 30_000,
    });
    await checkbox.check();
    await page.getByTestId("framework-approve-button").click({ timeout: 15_000 });
  } else if (await buildConfirmed.first().isVisible().catch(() => false)) {
    await buildConfirmed.first().click();
  } else {
    throw new Error("No approve/build control was visible");
  }
  await shot(page, "06-building");

  await page.waitForURL("**/deck-center**", { timeout: LONG_WAIT_MS });
  await page.getByTestId("presentation-ready").waitFor({ timeout: LONG_WAIT_MS });
  await page.getByTestId("download-powerpoint").waitFor({ timeout: 30_000 });
  await shot(page, "07-ppt-ready");
  console.log("[READY] PPT generated — Download PowerPoint is visible");
  console.log(`[URL] ${page.url()}`);
}

async function main() {
  console.log("[STEP] Launching visible Chrome — watch this window");
  const launchOptions = {
    headless: false,
    slowMo: 280,
    args: ["--start-maximized"],
  };
  let browser;
  try {
    browser = await chromium.launch({ ...launchOptions, channel: "chrome" });
  } catch (chromeError) {
    console.log("[STEP] System Chrome not found, trying Edge");
    try {
      browser = await chromium.launch({ ...launchOptions, channel: "msedge" });
    } catch {
      throw chromeError;
    }
  }
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
  });
  const page = await context.newPage();
  page.setDefaultTimeout(30_000);
  page.on("console", (msg) => {
    if (msg.type() === "error") console.log("[browser]", msg.text());
  });

  try {
    await signIn(page);
    if (EXISTING_OPPORTUNITY_ID) {
      console.log(`[STEP] Resume opportunity ${EXISTING_OPPORTUNITY_ID}`);
      await page.goto(`${WEB}/framework-review?opportunityId=${EXISTING_OPPORTUNITY_ID}`, {
        waitUntil: "domcontentloaded",
      });
      await page.waitForSelector('[data-testid="auth-ready"]', { state: "attached", timeout: 20_000 });
    } else {
      await createAndUpload(page);
    }
    await generateIfNeeded(page);
    await approveAndBuild(page);
    console.log("[HOLD] Browser stays open so you can inspect the deck. Close the window when done.");
    await new Promise(() => {});
  } catch (error) {
    await dumpFailure(page, error);
    process.exitCode = 1;
    console.log("[HOLD] Browser stays open on failure so you can inspect the page.");
    await new Promise(() => {});
  }
}

await main();
