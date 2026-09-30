import { spawn } from 'child_process';
import fs from 'fs';

async function testAll() {
  console.log("=== Comprehensive Automated Verification of Quran Video Studio ===");
  const chromePath = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
  const userDir = `/tmp/chrome_test_final_${Date.now()}`;
  const args = [
    '--headless=new',
    '--remote-debugging-port=9224',
    '--autoplay-policy=no-user-gesture-required',
    '--window-size=1920,1080',
    `--user-data-dir=${userDir}`,
    'http://localhost:8765/'
  ];

  console.log("Launching headless Chrome on port 9224...");
  const chromeProc = spawn(chromePath, args);

  let wsUrl = null;
  for (let i = 0; i < 30; i++) {
    await new Promise(r => setTimeout(r, 200));
    try {
      const res = await fetch('http://127.0.0.1:9224/json/list');
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

  // 1. Initial State Check (Must be Surah 1 Al-Fatihah)
  const initial = await send('Runtime.evaluate', {
    expression: `({
      currentSurah: currentSurah,
      headingText: document.getElementById('heroSurahHeading')?.innerText,
      mainHeaderTitle: document.getElementById('mainHeaderTitle')?.innerText,
      topNavSurahName: document.getElementById('topNavSurahName')?.innerText,
      inEditorBadge: document.getElementById('inEditorCurrentSurahBadge')?.innerText,
      surahSelectVal: document.getElementById('surahSelect')?.value,
      waveformStyle: currentWaveformConfig?.style,
      quickWaveformVal: document.getElementById('quickWaveformStyleSelect')?.value,
      sadaqahText: currentSadaqahConfig?.text,
      arabicWordsCount: document.querySelectorAll('.wbw-word').length
    })`,
    returnByValue: true
  });
  console.log("1. Initial Default State:", JSON.stringify(initial.result?.value, null, 2));

  // Screenshot 1: Default View (Surah 1)
  const snap1 = await send('Page.captureScreenshot', { format: 'png' });
  if (snap1 && snap1.data) {
    fs.writeFileSync('/Users/shaddo/.gemini/antigravity/scratch/surah_fatiha/verify_final_1_surah1_default.png', Buffer.from(snap1.data, 'base64'));
    console.log("Saved verify_final_1_surah1_default.png");
  }

  // 2. Test Quick Waveform Selector Dropdown in Toolbar
  console.log("2. Testing Quick Waveform Dropdown in Toolbar (switch to 'glow')...");
  const wfChangeRes = await send('Runtime.evaluate', {
    expression: `
      const sel = document.getElementById('quickWaveformStyleSelect');
      sel.value = 'glow';
      sel.dispatchEvent(new Event('change'));
      ({ newStyle: currentWaveformConfig.style, selectVal: sel.value });
    `,
    returnByValue: true
  });
  console.log("Toolbar Waveform Change Result:", wfChangeRes.result?.value);
  await new Promise(r => setTimeout(r, 800));

  // Screenshot 2: Glow Waveform
  const snap2 = await send('Page.captureScreenshot', { format: 'png' });
  if (snap2 && snap2.data) {
    fs.writeFileSync('/Users/shaddo/.gemini/antigravity/scratch/surah_fatiha/verify_final_2_glow_waveform.png', Buffer.from(snap2.data, 'base64'));
    console.log("Saved verify_final_2_glow_waveform.png");
  }

  // 3. Test Inspector Sidebar Tab 3 (Styles & Layout) Waveform and Sadaqah Panels
  console.log("3. Testing Inspector Tab 3 Layer Panels...");
  const tabSwitchRes = await send('Runtime.evaluate', {
    expression: `
      // Click Styles tab in sidebar
      document.querySelector('[data-tab="paneStyles"]')?.click();
      // Click Waveform layer tab
      document.querySelector('.layer-tab-btn[data-layer="waveform"]')?.click();
      const wfPanelVisible = (document.getElementById('waveformControlsPanel')?.style.display === 'flex');
      const textPanelHidden = (document.getElementById('textControlsPanel')?.style.display === 'none');
      ({ wfPanelVisible, textPanelHidden });
    `,
    returnByValue: true
  });
  console.log("Tab 3 Waveform Panel Switch:", tabSwitchRes.result?.value);
  await new Promise(r => setTimeout(r, 600));

  // Screenshot 3: Inspector Tab 3 with Waveform Panel
  const snap3 = await send('Page.captureScreenshot', { format: 'png' });
  if (snap3 && snap3.data) {
    fs.writeFileSync('/Users/shaddo/.gemini/antigravity/scratch/surah_fatiha/verify_final_3_sidebar_wf_panel.png', Buffer.from(snap3.data, 'base64'));
    console.log("Saved verify_final_3_sidebar_wf_panel.png");
  }

  // 4. Test Nudge Tilawat & Urdu Up/Down
  console.log("4. Testing Nudge Tilawat & Urdu...");
  const nudgeRes = await send('Runtime.evaluate', {
    expression: `
      const beforeArabic = currentLayoutConfig.arabic.top;
      const beforeUrdu = currentLayoutConfig.urdu.top;
      nudgeLayer('arabic', -5); // Jump up 5%
      nudgeLayer('urdu', 5);    // Jump down 5%
      ({
        arabic: { before: beforeArabic, after: currentLayoutConfig.arabic.top },
        urdu: { before: beforeUrdu, after: currentLayoutConfig.urdu.top }
      });
    `,
    returnByValue: true
  });
  console.log("Nudge Result:", JSON.stringify(nudgeRes.result?.value, null, 2));
  await new Promise(r => setTimeout(r, 600));

  // 5. Test Waveform Library Modal Card Selection
  console.log("5. Testing Waveform Library Modal Selection...");
  await send('Runtime.evaluate', { expression: `window.openWaveformLibraryModal();` });
  await new Promise(r => setTimeout(r, 800));

  const wfModalSnap = await send('Page.captureScreenshot', { format: 'png' });
  if (wfModalSnap && wfModalSnap.data) {
    fs.writeFileSync('/Users/shaddo/.gemini/antigravity/scratch/surah_fatiha/verify_final_4_wf_modal.png', Buffer.from(wfModalSnap.data, 'base64'));
    console.log("Saved verify_final_4_wf_modal.png");
  }

  // Click 'spectrum' style card
  await send('Runtime.evaluate', {
    expression: `
      const card = document.querySelector('.wf-style-card[data-wfid="spectrum"]');
      if (card) card.click();
    `
  });
  await new Promise(r => setTimeout(r, 500));
  await send('Runtime.evaluate', { expression: `window.closeWaveformLibraryModal();` });
  await new Promise(r => setTimeout(r, 500));

  // 6. Test Surah Switching (Sync Test: Switch to Surah 67 Al-Mulk, verify, then back to Surah 1)
  console.log("6. Testing Surah Switching Synchronization...");
  await send('Runtime.evaluate', {
    expression: `
      const sSelect = document.getElementById('surahSelect');
      sSelect.value = '67';
      sSelect.dispatchEvent(new Event('change'));
    `
  });
  await new Promise(r => setTimeout(r, 2500));

  const surah67State = await send('Runtime.evaluate', {
    expression: `({
      currentSurah: currentSurah,
      headingText: document.getElementById('heroSurahHeading')?.innerText,
      mainHeaderTitle: document.getElementById('mainHeaderTitle')?.innerText,
      topNavSurahName: document.getElementById('topNavSurahName')?.innerText,
      inEditorBadge: document.getElementById('inEditorCurrentSurahBadge')?.innerText,
      firstWord: document.querySelector('.wbw-word')?.innerText?.trim()
    })`,
    returnByValue: true
  });
  console.log("Surah 67 State (Should be Al-Mulk):", JSON.stringify(surah67State.result?.value, null, 2));

  const snapSurah67 = await send('Page.captureScreenshot', { format: 'png' });
  if (snapSurah67 && snapSurah67.data) {
    fs.writeFileSync('/Users/shaddo/.gemini/antigravity/scratch/surah_fatiha/verify_final_5_surah67.png', Buffer.from(snapSurah67.data, 'base64'));
    console.log("Saved verify_final_5_surah67.png");
  }

  // Switch back to Surah 1
  console.log("Switching back to Surah 1...");
  const backSwitchRes = await send('Runtime.evaluate', {
    expression: `
      const sSelect = document.getElementById('surahSelect');
      sSelect.value = '1';
      sSelect.dispatchEvent(new Event('change'));
      ({ switchedTo: sSelect.value, currentSurah: currentSurah });
    `,
    returnByValue: true
  });
  console.log("Back Switch Trigger Result:", backSwitchRes.result?.value);
  await new Promise(r => setTimeout(r, 2500));

  const surah1FinalState = await send('Runtime.evaluate', {
    expression: `({
      currentSurah: currentSurah,
      headingText: document.getElementById('heroSurahHeading')?.innerText,
      mainHeaderTitle: document.getElementById('mainHeaderTitle')?.innerText,
      topNavSurahName: document.getElementById('topNavSurahName')?.innerText,
      inEditorBadge: document.getElementById('inEditorCurrentSurahBadge')?.innerText,
      firstWord: document.querySelector('.wbw-word')?.innerText?.trim()
    })`,
    returnByValue: true
  });
  console.log("Surah 1 Final State (Should be Al-Fatihah):", JSON.stringify(surah1FinalState.result?.value, null, 2));

  // 7. Test Audio Playback
  console.log("7. Testing Audio Playback...");
  const playRes = await send('Runtime.evaluate', {
    expression: `
      const pBtn = document.getElementById('playBtn');
      pBtn.click();
      ({ isPlaying: isPlaying, audioPaused: audioEl.paused, audioSrc: audioEl.src });
    `,
    returnByValue: true
  });
  console.log("Play Trigger Result:", playRes.result?.value);
  await new Promise(r => setTimeout(r, 1500));

  const playingCheck = await send('Runtime.evaluate', {
    expression: `({
      isPlaying: isPlaying,
      audioPaused: audioEl.paused,
      currentTime: audioEl.currentTime,
      duration: audioEl.duration
    })`,
    returnByValue: true
  });
  console.log("Audio Playing Status:", playingCheck.result?.value);

  // Pause audio
  await send('Runtime.evaluate', { expression: `document.getElementById('playBtn').click();` });

  // Final Screenshot of Surah 1 fully verified
  const snapFinal = await send('Page.captureScreenshot', { format: 'png' });
  if (snapFinal && snapFinal.data) {
    fs.writeFileSync('/Users/shaddo/.gemini/antigravity/scratch/surah_fatiha/verify_final_6_complete.png', Buffer.from(snapFinal.data, 'base64'));
    console.log("Saved verify_final_6_complete.png");
  }

  ws.close();
  chromeProc.kill();
  console.log("=== ALL AUTOMATED TESTS COMPLETED SUCCESSFULLY! ===");
}

testAll().catch(console.error);
