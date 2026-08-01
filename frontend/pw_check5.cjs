const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  await page.goto('http://localhost:5183', { waitUntil: 'networkidle' });
  await page.waitForSelector('text=Sign In', { timeout: 15000 });

  const count = await page.locator('h2:has-text("Images")').count();
  console.log('MATCH COUNT for h2:has-text(Images):', count);
  const box = await page.locator('h2:has-text("Images")').first().boundingBox();
  console.log('bounding box (pre-scroll, absolute-in-doc via evaluate below):', box);

  const docPos = await page.locator('h2:has-text("Images")').first().evaluate((el) => {
    const r = el.getBoundingClientRect();
    return { top: r.top + window.scrollY, text: el.textContent };
  });
  console.log('doc-relative top + text:', docPos);

  await page.locator('h2:has-text("Images")').first().scrollIntoViewIfNeeded();
  await page.waitForTimeout(400);
  console.log('scrollY after direct scrollIntoView on fresh page:', await page.evaluate(() => window.scrollY));
  await page.screenshot({ path: '/tmp/pw-shots/v4-images-direct.png' });

  await browser.close();
})();
