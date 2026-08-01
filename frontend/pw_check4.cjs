const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  const consoleErrors = [];
  page.on('console', (msg) => { if (msg.type() === 'error') consoleErrors.push(msg.text()); });
  page.on('pageerror', (err) => consoleErrors.push('PAGEERROR: ' + err.message));

  await page.goto('http://localhost:5183', { waitUntil: 'networkidle' });
  await page.waitForSelector('text=Sign In', { timeout: 15000 });

  console.log('scrollY before:', await page.evaluate(() => window.scrollY));

  // Use CDP wheel dispatch (real 'wheel' events, unlike page.mouse.wheel which is also wheel but let's confirm consistency)
  await page.mouse.wheel(0, 1500);
  await page.waitForTimeout(150);
  const midScroll = await page.evaluate(() => window.scrollY);
  console.log('scrollY mid-inertia (should be less than final, still easing):', midScroll);
  await page.waitForTimeout(700);
  const settledScroll = await page.evaluate(() => window.scrollY);
  console.log('scrollY settled:', settledScroll);

  // Now test scrollIntoView correctness (the thing that broke before)
  const beforeH2Scroll = await page.evaluate(() => window.scrollY);
  await page.locator('h2:has-text("Images")').scrollIntoViewIfNeeded();
  await page.waitForTimeout(300);
  const afterH2Scroll = await page.evaluate(() => window.scrollY);
  console.log('scrollY before scrollIntoView(Images):', beforeH2Scroll, ' after:', afterH2Scroll, ' moved:', afterH2Scroll !== beforeH2Scroll);
  await page.screenshot({ path: '/tmp/pw-shots/v3-images-section.png' });

  await page.locator('h2:has-text("Video")').scrollIntoViewIfNeeded();
  await page.waitForTimeout(300);
  await page.screenshot({ path: '/tmp/pw-shots/v3-video-section.png' });

  await page.locator('footer').scrollIntoViewIfNeeded();
  await page.waitForTimeout(300);
  await page.screenshot({ path: '/tmp/pw-shots/v3-footer.png' });

  await page.locator('h2:has-text("Audio")').scrollIntoViewIfNeeded();
  await page.waitForTimeout(300);
  await page.screenshot({ path: '/tmp/pw-shots/v3-audio-section.png' });

  console.log('CONSOLE_ERRORS:', JSON.stringify(consoleErrors.filter(e => !e.includes('ERR_CONNECTION_REFUSED')), null, 2));
  await browser.close();
})();
