// Smoke test giao diện: đi trọn luồng của kế toán trên server đang chạy và chụp màn hình.
// Cần: backend (OCR_PROVIDER=tesseract) + frontend đang chạy, tài khoản demo đã tạo, và playwright-core.
//   BASE_URL=http://localhost:3000 CHROME=/đường/dẫn/chrome OUT=./shots node e2e/smoke.mjs
import { mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright-core";
const here = dirname(fileURLToPath(import.meta.url));
const dir = process.env.OUT || join(here, "shots");
mkdirSync(dir, { recursive: true });
const browser = await chromium.launch({ executablePath: process.env.CHROME });
const page = await browser.newPage({ viewport: { width: 1360, height: 900 }, locale: "vi-VN" });
const errors = [];
page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
page.on("pageerror", (e) => errors.push(String(e)));
const shot = (n) => page.screenshot({ path: `${dir}/${n}.png`, fullPage: true });
const B = process.env.BASE_URL || "http://localhost:3000";

await page.goto(`${B}/login`);
await page.fill("#email", process.env.EMAIL || "ketoan@demo.vn");
await page.fill("#password", process.env.PASSWORD || "demo-password-123");
await page.click("button:has-text('Đăng nhập')");
await page.waitForURL(`${B}/`);
await page.fill("#new-name", "Quán ăn Minh Anh");
await page.click("button:has-text('Thêm hộ')");
await page.waitForSelector("text=Quán ăn Minh Anh");
await shot("01-customers");

await page.click("a:has-text('Nhập dữ liệu')");
await page.waitForSelector("#chat-text");
await page.fill("#business-date", "2026-10-03");
await page.setInputFiles("#file-input", [join(here, "hd_tanphat.jpg"), join(here, "hd_kimlong.jpg"), join(here, "phieu_mo.jpg"), join(here, "ck_5tr.jpg"), join(here, "hd_5tr.jpg")]);
await page.fill("#chat-text", "2tr5\ntiền thịt\nDoanh thu hôm nay 12tr5\nok em nhé\nphiếu gas gửi nhầm nhé");
await shot("02-import-filled");
await page.click("button:has-text('Lưu đợt nhập')");
await page.waitForSelector("text=Đã lưu", { timeout: 60000 });
await shot("03-import-done");

await page.click("a:has-text('Sang hàng chờ duyệt')");
await page.waitForSelector("text=/Còn \\d+ mục/");
const log = [];
for (let step = 1; step <= 20; step++) {
  await page.waitForTimeout(600);
  if (await page.locator("text=Không còn mục nào chờ duyệt").count()) break;
  const heading = await page.locator("main h1 + span").innerText();
  await shot(`04-review-${String(step).padStart(2, "0")}`);
  if (await page.locator("button.choice").count()) {
    const first = await page.locator("button.choice").first().innerText();
    log.push(`${heading} | chọn 1: ${first.replace(/\s+/g, " ").slice(0, 90)}`);
    await page.keyboard.press("1");
  } else if (await page.locator("text=Khách báo gửi nhầm").count()) {
    log.push(`${heading} | loại khỏi sổ vì khách báo gửi nhầm`);
    await page.click("button:has-text('Loại khỏi sổ')");
    await page.click("button:has-text('Xác nhận loại')");
  } else {
    const amount = page.locator("input[id^=amount-]");
    if (!(await amount.inputValue())) await amount.fill("950k");
    if (!(await page.locator("button[aria-pressed=true]").count())) await page.click("button:has-text('Chi')");
    const date = page.locator("input[id^=posting-]");
    if (!(await date.inputValue())) await date.fill("2026-10-03");
    log.push(`${heading} | xác nhận giao dịch, số tiền ${await amount.inputValue()}`);
    await amount.press("Enter");
  }
  await page.waitForTimeout(900);
  const alert = page.locator(".alert");
  if (await alert.count()) log.push("LỖI: " + (await alert.innerText()));
}
await shot("05-review-empty");

// Việc cần xử lý: chuyển khoản 5tr chưa có chứng từ → tạo tin nhắn → ghép với hóa đơn 5tr.
await page.click("a:has-text('Việc cần xử lý')");
await page.waitForSelector("text=/Đang mở \\(\\d+\\)/");
await page.waitForTimeout(800);
await shot("09-findings");
const transferCard = page.locator("article", { hasText: "Chuyển khoản 5.000.000đ" });
if (!(await transferCard.count())) throw new Error("Không thấy phát hiện cho chuyển khoản 5.000.000đ");
await transferCard.locator("input[type=checkbox]").check();
await page.click("button:has-text('Tạo tin nhắn đòi chứng từ')");
await page.waitForSelector("#request-text");
log.push("tin nhắn: " + (await page.locator("#request-text").inputValue()).replace(/\n/g, " | "));
await shot("10-request-text");
await transferCard.locator("button:has-text('Ghép chứng từ')").click();
await transferCard.locator("button:has-text('Xác nhận ghép')").first().click();
await page.waitForTimeout(1000);
await page.click("button:has-text('Đã xử lý')");
await page.waitForTimeout(500);
await shot("11-findings-resolved");
log.push("đã xử lý: " + (await page.locator("article").count()) + " việc");

await page.click("a:has-text('Sổ theo ngày')");
await page.fill("#month", "2026-10");
await page.waitForTimeout(1200);
await shot("06-ledger");
await page.locator("tr.clickable").first().click();
await page.waitForSelector("aside.drawer");
await page.waitForTimeout(800);
await shot("07-ledger-drawer");
await page.setViewportSize({ width: 400, height: 860 });
await page.click("aside.drawer button:has-text('Đóng')");
await page.waitForTimeout(300);
await shot("08-ledger-mobile");
console.log(log.join("\n"));
console.log("console errors:", errors.length ? errors : "none");
await browser.close();
if (errors.length) process.exit(1);
