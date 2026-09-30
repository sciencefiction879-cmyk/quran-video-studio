import { spawn } from 'child_process';
import fs from 'fs';

async function run() {
  const chromePath = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
  const userDir = `/tmp/chrome_test_verify_${Date.now()}`;
  const args = [
    '--headless=new',
    '--remote-debugging-port=9223',
    '--autoplay-policy=no-user-gesture-required',
    '--window-size=1920,1080',
    `--user-data-dir=${userDir}`,
    'http://localhost:8765/'
  ];

  console.log("Launching headless Chrome on port 9223...");
  const chromeProc = spawn(chromePath, args);

  let wsUrl = null;
  for (let i = 0; i < 30; i++) {
    await new Promise(r => setTimeout(r, 200));
    try {
      const res = await fetch('http://127.0.0.1:9223/json/list');
      const list = await res.json();
      const page = list.find(t => t.type === 'page' && t.url.includes('localhost:8765'));
      if (page && page.webSocketDebuggerUrl) {
        wsUrl = page.webSocketDebuggerUrl;
        break;
      }
    } catch (e) {}
  }

  if (!wsUrl) {
    console.error("Could not connect to Chrome CDP");
    chromeProc.kill();
    process.exit(1);
  }

  console.log("Connected to Chrome CDP WebSocket:", wsUrl);
  const ws = new WebSocket(wsUrl);
  let idCounter = 1;
  const pending = new Map();

  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.method === 'Runtime.consoleAPICalled') {
      console.log(`[Browser Console ${data.params.type}]`, ...data.params.args.map(a => a.value || a.description));
    }
    if (data.id && pending.has(data.id)) {
      pending.get(data.id)(data);
      pending.delete(data.id);
    }
  };

  await new Promise(r => ws.onopen = r);

  function send(method, params = {}) {
    return new Promise(resolve => {
      const id = idCounter++;
      pending.set(id, (res) => resolve(res ? res.result : null));
      ws.send(JSON.stringify({ id, method, params }));
    });
  }

  await send('Runtime.enable');
  await send('Page.enable');

  console.log("Waiting 3s for page initialization...");
  await new Promise(r => setTimeout(r, 3000));

  // Evaluate initial state
  const state = await send('Runtime.evaluate', {
    expression: `({
      url: window.location.href,
      currentSurah: currentSurah,
      headingText: document.getElementById('heroSurahHeading')?.innerText,
      mainHeaderTitle: document.getElementById('mainHeaderTitle')?.innerText,
      topNavSurahName: document.getElementById('topNavSurahName')?.innerText,
      inEditorBadge: document.getElementById('inEditorCurrentSurahBadge')?.innerText,
      surahSelectVal: document.getElementById('surahSelect')?.value,
      waveformStyle: currentWaveformConfig?.style,
      sadaqahText: currentSadaqahConfig?.text,
      activeWordsCount: document.querySelectorAll('.wbw-word').length
    })`,
    returnByValue: true
  });

  console.log("Initial Page State:", JSON.stringify(state.result?.value, null, 2));

  // Take screenshot of default initial state
  const snap1 = await send('Page.captureScreenshot', { format: 'png' });
  if (snap1 && snap1.data) {
    fs.writeFileSync('/Users/shaddo/.gemini/antigravity/scratch/surah_fatiha/verify_step1_initial.png', Buffer.from(snap1.data, 'base64'));
    console.log("Saved verify_step1_initial.png");
  }

  // Test opening Waveform modal and selecting another style (e.g. 'thin_line' or 'vertical_bars')
  console.log("Testing Waveform Library Modal...");
  await send('Runtime.evaluate', {
    expression: `
      window.openWaveformLibraryModal();
    `
  });
  await new Promise(r => setTimeout(r, 1000));

  const snap2 = await send('Page.captureScreenshot', { format: 'png' });
  if (snap2 && snap2.data) {
    fs.writeFileSync('/Users/shaddo/.gemini/antigravity/scratch/surah_fatiha/verify_step2_wf_modal.png', Buffer.from(snap2.data, 'base64'));
    console.log("Saved verify_step2_wf_modal.png");
  }

  // Click on a waveform card, e.g. 'vertical_bars'
  console.log("Clicking vertical_bars waveform card...");
  const clickRes = await send('Runtime.evaluate', {
    expression: `
      const card = document.querySelector('.wf-style-card[data-wfid="vertical_bars"]');
      if (card) {
        card.click();
        ({ clicked: true, newStyle: currentWaveformConfig.style });
      } else {
        ({ clicked: false });
      }
    `,
    returnByValue: true
  });
  console.log("Card click result:", clickRes.result?.value);
  await new Promise(r => setTimeout(r, 500));

  // Close waveform modal
  await send('Runtime.evaluate', { expression: `window.closeWaveformLibraryModal();` });
  await new Promise(r => setTimeout(r, 500));

  // Test Nudge buttons: nudge arabic up by 4%
  console.log("Testing Nudge Arabic Up...");
  const nudgeRes = await send('Runtime.evaluate', {
    expression: `
      const beforeTop = currentLayoutConfig.arabic.top;
      nudgeLayer('arabic', -4);
      const afterTop = currentLayoutConfig.arabic.top;
      ({ beforeTop, afterTop });
    `,
    returnByValue: true
  });
  console.log("Nudge result:", nudgeRes.result?.value);

  // Test Sadaqah Library modal
  console.log("Testing Sadaqah Library Modal...");
  await send('Runtime.evaluate', { expression: `window.openSadaqahLibraryModal();` });
  await new Promise(r => setTimeout(r, 1000));

  const snap3 = await send('Page.captureScreenshot', { format: 'png' });
  if (snap3 && snap3.data) {
    fs.writeFileSync('/Users/shaddo/.gemini/antigravity/scratch/surah_fatiha/verify_step3_sadaqah_modal.png', Buffer.from(snap3.data, 'base64'));
    console.log("Saved verify_step3_sadaqah_modal.png");
  }

  // Close Sadaqah modal
  await send('Runtime.evaluate', { expression: `window.closeSadaqahLibraryModal();` });
  await new Promise(r => setTimeout(r, 500));

  // Final screenshot of live editor
  const snap4 = await send('Page.captureScreenshot', { format: 'png' });
  if (snap4 && snap4.data) {
    fs.writeFileSync('/Users/shaddo/.gemini/antigravity/scratch/surah_fatiha/verify_step4_final.png', Buffer.from(snap4.data, 'base64'));
    console.log("Saved verify_step4_final.png");
  }

  ws.close();
  chromeProc.kill();
  console.log("Verification finished successfully!");
}

run().catch(console.error);
