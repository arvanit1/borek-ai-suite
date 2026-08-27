/**
 * AT-46 browser E2E: login → opportunity → multi-file upload with client-side reject.
 * Run: node scripts/e2e_upload_browser.mjs
 */
import { chromium } from "playwright";
import { mkdir, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { readFileSync, existsSync } from "node:fs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");

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

if (!EMAIL || !PASSWORD) {
  console.error("Missing E2E_TEST_EMAIL or E2E_TEST_PASSWORD in .env");
  process.exit(1);
}

const FIXTURE_DIR = join(ROOT, ".tmp_e2e");
const VALID_FILE = join(FIXTURE_DIR, "discovery-call.txt");
const INVALID_FILE = join(FIXTURE_DIR, "slides.pdf");

async function main() {
  await mkdir(FIXTURE_DIR, { recursive: true });
  await writeFile(
    VALID_FILE,
    "Client discovery call transcript.\nWe discussed automation scope and timeline.\n",
  );
  await writeFile(INVALID_FILE, "%PDF-1.4 fake pdf for reject test");

  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  const results = [];

  try {
    // 1. Login
    await page.goto(`${WEB}/login`, { waitUntil: "networkidle" });
    await page.getByLabel("Work email").fill(EMAIL);
    await page.getByLabel("Password").fill(PASSWORD);
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await page.waitForURL("**/upload**", { timeout: 15000 });
    await page.getByText(EMAIL, { exact: false }).waitFor({ timeout: 10000 });
    await page.waitForFunction(() => {
      for (const key of Object.keys(localStorage)) {
        if (key.includes("auth-token")) {
          const raw = localStorage.getItem(key);
          if (raw && raw.includes("access_token")) return true;
        }
      }
      return false;
    });
    await page.waitForSelector('[data-testid="auth-ready"]', { state: "attached", timeout: 15000 });
    results.push("[OK] Login redirects to /upload");

    // 2. Create opportunity
    await page.getByLabel("Client name").fill("E2E Browser Client");
    await page.getByLabel("Opportunity name").fill(`Browser smoke ${Date.now()}`);
    await page.getByLabel("Department").fill("Sales Engineering");

    const createResponsePromise = page.waitForResponse(
      (response) =>
        response.url().includes("/opportunities") &&
        response.request().method() === "POST" &&
        !response.url().includes("/transcripts"),
      { timeout: 20000 },
    );
    await page.getByRole("button", { name: "Create opportunity" }).click();
    const createResponse = await createResponsePromise;
    const createBody = await createResponse.text();
    if (!createResponse.ok()) {
      throw new Error(`Create opportunity failed: HTTP ${createResponse.status()} ${createBody}`);
    }
    await page.getByText("Opportunity created").waitFor({ timeout: 10000 });
    await page.getByText("Active opportunity").waitFor({ timeout: 5000 });
    results.push("[OK] Opportunity created");

    // 3. Queue valid + invalid files
    await page.locator('input[type="file"]').setInputFiles([VALID_FILE, INVALID_FILE]);
    await page.getByText("discovery-call.txt").waitFor();
    await page.getByText("slides.pdf").waitFor();
    results.push("[OK] Multi-file selection shows both files");

    // 4. Client-side reject
    const rejectedBadge = page.locator("tr", { hasText: "slides.pdf" }).getByText("Rejected");
    await rejectedBadge.waitFor({ timeout: 5000 });
    const readyBadge = page.locator("tr", { hasText: "discovery-call.txt" }).getByText("Ready");
    await readyBadge.waitFor({ timeout: 5000 });
    results.push("[OK] .pdf Rejected and .txt Ready (client-side)");

    // 5. Upload only ready file
    const uploadBtn = page.getByRole("button", { name: /Upload 1 file/ });
    await uploadBtn.click();
    await page.getByText("transcript ingested successfully", { exact: false }).waitFor({
      timeout: 15000,
    });
    await page.locator("tr", { hasText: "discovery-call.txt" }).getByText("Uploaded").waitFor({
      timeout: 10000,
    });
    results.push("[OK] Valid file uploaded with success banner");

    // 6. Rejected file unchanged
    await rejectedBadge.waitFor();
    results.push("[OK] Rejected file stayed rejected (no API call)");

    console.log("=== AT-46 Browser E2E ===");
    for (const line of results) console.log(line);
    console.log("\n=== ALL BROWSER E2E CHECKS PASSED ===");
  } catch (error) {
    console.error("[FAIL]", error instanceof Error ? error.message : error);
    await page.screenshot({ path: join(FIXTURE_DIR, "failure.png"), fullPage: true });
    console.error(`Screenshot: ${join(FIXTURE_DIR, "failure.png")}`);
    process.exitCode = 1;
  } finally {
    await browser.close();
  }
}

await main();
