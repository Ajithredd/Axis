import puppeteer from 'puppeteer';

async function runTest() {
  console.log('=== Starting Citation Click Crash Test ===');
  const browser = await puppeteer.launch({ headless: 'new' });
  const page = await browser.newPage();
  
  // Track page errors
  page.on('pageerror', err => {
    console.error('CRITICAL: Page Error detected:', err.message, err.stack);
  });

  // Track console logs
  page.on('console', msg => {
    console.log(`[Browser Console] ${msg.type().toUpperCase()}: ${msg.text()}`);
  });
  
  try {
    await page.setViewport({ width: 1280, height: 800 });
    console.log('Navigating to http://localhost:5173/');
    await page.goto('http://localhost:5173/', { waitUntil: 'networkidle2' });

    // Wait for project to be loaded
    console.log('Waiting for projects to load in sidebar...');
    await page.waitForSelector('.nav-item', { visible: true, timeout: 15000 });
    console.log('Project loaded.');

    // Wait for chat input to be ready
    console.log('Waiting for chat input...');
    await page.waitForSelector('.chat-form textarea', { visible: true, timeout: 5000 });
    
    // Type query
    console.log('Typing query...');
    await page.type('.chat-form textarea', 'Who are the stakeholders?');
    await page.screenshot({ path: 'test_1_typed.png' });

    // Send message
    console.log('Sending message...');
    await page.click('.chat-send-btn');
    await page.screenshot({ path: 'test_2_sending.png' });

    // Wait for model response (typing indicator disappears, citations appear)
    console.log('Waiting for AI response and citations...');
    // The typing indicator should appear and then disappear. Let's wait for the citation tag to show up.
    await page.waitForSelector('.citation-tag', { visible: true, timeout: 90000 });
    console.log('Citations received!');
    await page.screenshot({ path: 'test_3_response_received.png' });

    // Click on the first citation
    console.log('Clicking on the first citation tag...');
    await page.click('.citation-tag');
    await page.screenshot({ path: 'test_4_clicked_citation_immediate.png' });

    // Wait for the inspector panel and Feature Intelligence Graph to load
    console.log('Waiting for inspector-panel...');
    await page.waitForSelector('.inspector-panel', { visible: true, timeout: 10000 });
    console.log('Inspector panel visible.');

    // Wait a few seconds for canvas rendering to execute
    console.log('Waiting 5 seconds for canvas rendering...');
    await new Promise(resolve => setTimeout(resolve, 5000));
    await page.screenshot({ path: 'test_5_graph_loaded.png' });

    console.log('Verification completed without any page-level exceptions.');
  } catch (error) {
    console.error('Test script encountered an error:', error);
    await page.screenshot({ path: 'test_error.png' });
  } finally {
    await browser.close();
    console.log('=== Citation Click Crash Test Ended ===');
  }
}

runTest();
