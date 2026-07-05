import puppeteer from 'puppeteer';
import fs from 'fs';

async function runTest() {
  console.log('Starting browser test...');
  const browser = await puppeteer.launch({ headless: 'new' });
  const page = await browser.newPage();
  
  try {
    await page.setViewport({ width: 1280, height: 800 });
    console.log('Navigating to http://localhost:5173/');
    await page.goto('http://localhost:5173/', { waitUntil: 'networkidle2' });

    // Click "Connect GitLab" button in sidebar
    console.log('Clicking Connect GitLab button...');
    const connectBtn = await page.waitForSelector('button:has-text("Connect GitLab")');
    if(connectBtn) await connectBtn.click();
    else {
      // Find button by looking at all buttons
      const buttons = await page.$$('button');
      for (const btn of buttons) {
        const text = await page.evaluate(el => el.textContent, btn);
        if (text && text.includes('Connect GitLab')) {
          await btn.click();
          break;
        }
      }
    }

    // Wait for modal to appear and find the input field
    console.log('Waiting for modal and input field...');
    const tokenInput = await page.waitForSelector('.token-input', { visible: true, timeout: 5000 });
    
    // Type token
    console.log('Entering PAT...');
    await tokenInput.type('glpat-GaWIAim3NSC54zh8z_9ORGM6MQpvOjEKdTptcXRkMQ8.01.1700cgibp');

    // Click "Save Token"
    console.log('Clicking Save Token...');
    const saveBtn = await page.$('.btn-primary');
    await saveBtn.click();

    // Wait for project list to load
    console.log('Waiting for projects to load...');
    await page.waitForSelector('.project-list-item', { visible: true, timeout: 15000 });
    console.log('Projects loaded successfully.');

    // Click "Connect" on the first project
    console.log('Connecting to first project...');
    const importBtn = await page.$('.btn-import:not(.success)');
    if (importBtn) {
      await importBtn.click();
      
      // Wait for success state
      await page.waitForSelector('.btn-import.success', { visible: true, timeout: 10000 });
      console.log('Project connected successfully!');
    } else {
      console.log('No available projects to connect to, or already connected.');
    }

    // Take screenshot
    await page.screenshot({ path: 'pat_test_success.png' });
    console.log('Test completed successfully. Screenshot saved to pat_test_success.png');
  } catch (error) {
    console.error('Test failed:', error);
    await page.screenshot({ path: 'pat_test_error.png' });
  } finally {
    await browser.close();
  }
}

runTest();
