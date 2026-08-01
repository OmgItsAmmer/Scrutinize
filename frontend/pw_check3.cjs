const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  const consoleErrors = [];
  page.on('console', (msg) => { if (msg.type() === 'error') consoleErrors.push(msg.text()); });
  page.on('pageerror', (err) => consoleErrors.push('PAGEERROR: ' + err.message));

  await page.goto('http://localhost:5183', { waitUntil: 'networkidle' });
  await page.waitForSelector('text=Sign In', { timeout: 15000 });

  // Hero, with marquee
  await page.screenshot({ path: '/tmp/pw-shots/v2-hero.png' });

  // total scroll height (via the spacer div, since real body scroll is faked)
  const scrollHeight = await page.evaluate(() => document.body.scrollHeight);
  console.log('SCROLL_HEIGHT:', scrollHeight);

  // Scroll down via wheel to exercise the inertial scroll + reveal-on-scroll
  await page.mouse.wheel(0, 2000);
  await page.waitForTimeout(900); // allow lerp to settle
  await page.screenshot({ path: '/tmp/pw-shots/v2-after-scroll-1.png' });

  await page.mouse.wheel(0, 3000);
  await page.waitForTimeout(900);
  await page.screenshot({ path: '/tmp/pw-shots/v2-after-scroll-2.png' });

  // jump to images section
  await page.locator('h2:has-text("Images")').scrollIntoViewIfNeeded();
  await page.waitForTimeout(1200);
  await page.screenshot({ path: '/tmp/pw-shots/v2-images-section.png' });

  await page.locator('h2:has-text("Video")').scrollIntoViewIfNeeded();
  await page.waitForTimeout(1200);
  await page.screenshot({ path: '/tmp/pw-shots/v2-video-section.png' });

  await page.locator('footer').scrollIntoViewIfNeeded();
  await page.waitForTimeout(1200);
  await page.screenshot({ path: '/tmp/pw-shots/v2-footer.png' });

  console.log('CONSOLE_ERRORS:', JSON.stringify(consoleErrors.filter(e => !e.includes('ERR_CONNECTION_REFUSED')), null, 2));
  await browser.close();
})();
