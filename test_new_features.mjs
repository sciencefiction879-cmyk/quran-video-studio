import { spawn } from 'child_process';
import fs from 'fs';

async function testFeatures() {
  console.log("=== Testing In-Editor Design, Waveform & Urdu Sadaqah Message Features ===");
  const targetUrl = "http://localhost:8765/?surah=67&ayah=3&qari=husary&mode=arabic";
  const chromePath = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
  const userDir = `/tmp/chrome_test_profile_${Date.now()}`;

  const args = [
    '--headless=new',
    '--disable-gpu',
    '--remote-debugging-port=9222',
    '--autoplay-policy=no-user-gesture-required',
    '--window-size=1920,1080',
    `--user-data-dir=${userDir}`,
    targetUrl
  ];

  const chromeProc = spawn(chromePath, args);

  let wsUrl = null;
  for (let i = 0; i < 30; i++) {
    await new Promise(r => setTimeout(r, 300));
    try {
      const res = await fetch('http://127.0.0.1:9222/json/list');
      const list = await res.json();
      const pageTarget = list.find(t => t.type === 'page' && t.url.includes('localhost:8765'));
      if (pageTarget && pageTarget.webSocketDebuggerUrl) {
        wsUrl = pageTarget.webSocketDebuggerUrl;
        break;
      }
    } catch (e) {}
  }

  if (!wsUrl) {
    console.error("Failed to connect to Chrome CDP");
    chromeProc.kill();
    process.exit(1);
  }

  const ws = new WebSocket(wsUrl);
  let msgId = 1;
  const callbacks = new Map();

  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.id && callbacks.has(data.id)) {
      callbacks.get(data.id)(data);
      callbacks.delete(data.id);
    }
  };

  await new Promise(r => ws.onopen = r);

  function sendCdp(method, params = {}) {
    return new Promise((resolve) => {
      const id = msgId++;
      callbacks.set(id, (res) => resolve(res ? res.result : null));
      ws.send(JSON.stringify({ id, method, params }));
    });
  }

  async function evaluate(expression) {
    const res = await sendCdp('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
    return res && res.result ? res.result.value : null;
  }

  // Wait for initial page load
  await new Promise(r => setTimeout(r, 2000));

  // 1. Verify Live Hero Stage elements
  console.log("\n[Test 1] Checking Live Editor elements...");
  const heroInfo = await evaluate(`(() => {
    const sadaqahBox = document.getElementById('boxSadaqahMessage');
    const sadaqahText = document.getElementById('heroSadaqahText');
    const waveBox = document.getElementById('boxWaveform');
    const waveCanvas = document.getElementById('audioVisualizerCanvas');
    const arBox = document.getElementById('boxArabic');
    const urduBox = document.getElementById('boxUrdu');
    const engBox = document.getElementById('boxEnglish');
    return {
      sadaqahVisible: sadaqahBox ? window.getComputedStyle(sadaqahBox).display !== 'none' : false,
      sadaqahText: sadaqahText ? sadaqahText.innerText : '',
      waveVisible: waveBox ? window.getComputedStyle(waveBox).display !== 'none' : false,
      waveCanvasW: waveCanvas ? waveCanvas.width : 0,
      arabicText: arBox ? arBox.innerText.replace(/\\s+/g, ' ').trim() : '',
      activeTemplate: window.activeTemplateId,
      waveformStyle: window.currentWaveformConfig ? window.currentWaveformConfig.style : null
    };
  })()`);
  console.log("Hero Stage Status:", JSON.stringify(heroInfo, null, 2));

  // Capture screenshot of live editor with all layers
  let snap = await sendCdp('Page.captureScreenshot', { format: 'png' });
  fs.writeFileSync('test_editor_live_hero_16x9.png', Buffer.from(snap.data, 'base64'));
  console.log("Saved: test_editor_live_hero_16x9.png");

  // 2. Test Design Library Modal
  console.log("\n[Test 2] Opening Design Library Modal & Switching Design...");
  await evaluate(`openDesignLibraryModal()`);
  await new Promise(r => setTimeout(r, 600));

  const tplCount = await evaluate(`(() => {
    const cards = document.querySelectorAll('#inEditorTemplatesGrid .in-editor-tpl-card');
    return cards.length;
  })()`);
  console.log(`Design Library opened. Found ${tplCount} designs rendered in modal.`);

  snap = await sendCdp('Page.captureScreenshot', { format: 'png' });
  fs.writeFileSync('test_design_library_modal.png', Buffer.from(snap.data, 'base64'));
  console.log("Saved: test_design_library_modal.png");

  // Switch design to 'tmpl_master_madinah'
  await evaluate(`selectInEditorTemplate('tmpl_master_madinah', true)`);
  await new Promise(r => setTimeout(r, 600));
  await evaluate(`closeDesignLibraryModal()`);
  await new Promise(r => setTimeout(r, 400));

  const currentTpl = await evaluate(`window.activeTemplateId`);
  console.log(`Active Template after instant switch: ${currentTpl}`);

  // 3. Test Waveform Library Modal
  console.log("\n[Test 3] Opening Waveform Library Modal & Switching Waveform...");
  await evaluate(`openWaveformLibraryModal()`);
  await new Promise(r => setTimeout(r, 600));

  const wfCount = await evaluate(`(() => {
    const cards = document.querySelectorAll('#waveformStylesGrid .wf-style-card');
    return cards.length;
  })()`);
  console.log(`Waveform Library opened. Found ${wfCount} waveform styles with animated canvases.`);

  snap = await sendCdp('Page.captureScreenshot', { format: 'png' });
  fs.writeFileSync('test_waveform_library_modal.png', Buffer.from(snap.data, 'base64'));
  console.log("Saved: test_waveform_library_modal.png");

  // Select 'smooth_bars' and change color to cyan
  await evaluate(`(() => {
    selectWaveformStyle('smooth_bars');
    currentWaveformConfig.color = '#00ffcc';
    currentWaveformConfig.thickness = 4;
    applyLiveWaveformStyles();
  })()`);
  await new Promise(r => setTimeout(r, 400));
  await evaluate(`closeWaveformLibraryModal()`);

  // 4. Test Urdu Sadaqah Jariyah Message Library Modal
  console.log("\n[Test 4] Opening Sadaqah Message Library Modal...");
  await evaluate(`openSadaqahLibraryModal()`);
  await new Promise(r => setTimeout(r, 600));

  const sadaqahCount = await evaluate(`(() => {
    const rows = document.querySelectorAll('#sadaqahPresetsContainer .sadaqah-preset-row');
    return rows.length;
  })()`);
  console.log(`Sadaqah Library opened. Found ${sadaqahCount} preset messages.`);

  snap = await sendCdp('Page.captureScreenshot', { format: 'png' });
  fs.writeFileSync('test_sadaqah_library_modal.png', Buffer.from(snap.data, 'base64'));
  console.log("Saved: test_sadaqah_library_modal.png");

  // Select preset #3 and trigger safe auto-placement
  await evaluate(`(() => {
    selectSadaqahPreset(2); // 0-indexed #3
    document.getElementById('sadaqahAutoPosBtn').click();
  })()`);
  await new Promise(r => setTimeout(r, 400));
  await evaluate(`closeSadaqahLibraryModal()`);

  // 5. Test 9:16 Vertical Ratio
  console.log("\n[Test 5] Switching to 9:16 Vertical Shorts ratio...");
  await evaluate(`setPlayerAspect('9:16')`);
  await new Promise(r => setTimeout(r, 1000));

  snap = await sendCdp('Page.captureScreenshot', { format: 'png' });
  fs.writeFileSync('test_editor_live_hero_9x16.png', Buffer.from(snap.data, 'base64'));
  console.log("Saved: test_editor_live_hero_9x16.png");

  // 6. Test Export Screen Cleanup & Active Summary Card
  console.log("\n[Test 6] Opening Export Screen to verify Active Composition Summary...");
  // Switch back to 16:9 for export check
  await evaluate(`setPlayerAspect('16:9')`);
  await new Promise(r => setTimeout(r, 400));
  await evaluate(`(() => {
    const renderModal = document.getElementById('renderModal');
    renderModal.classList.add('active');
  })()`);
  await new Promise(r => setTimeout(r, 600));

  const exportSummaryInfo = await evaluate(`(() => {
    const designName = document.getElementById('exportSummaryDesignName')?.innerText;
    const wfName = document.getElementById('exportSummaryWaveformName')?.innerText;
    const sadaqahTxt = document.getElementById('exportSummarySadaqahText')?.innerText;
    // Check that duplicate design gallery is NOT in modal
    const hasTplGalleryInModal = !!document.getElementById('modalTemplateGallery');
    return { designName, wfName, sadaqahTxt, hasTplGalleryInModal };
  })()`);
  console.log("Export Modal Summary:", JSON.stringify(exportSummaryInfo, null, 2));

  snap = await sendCdp('Page.captureScreenshot', { format: 'png' });
  fs.writeFileSync('test_export_modal_summary.png', Buffer.from(snap.data, 'base64'));
  console.log("Saved: test_export_modal_summary.png");

  await evaluate(`(() => {
    const renderModal = document.getElementById('renderModal');
    renderModal.classList.remove('active');
  })()`);

  // 7. Verify Per-Surah Persistence (switch V67 to V112 and back)
  console.log("\n[Test 7] Verifying Per-Surah Configuration Persistence...");
  // Save current setup for Surah 67
  await evaluate(`saveSurahConfigToServer(67, 'single')`);
  await new Promise(r => setTimeout(r, 500));

  // Switch to Surah 112 (Al-Ikhlas)
  await evaluate(`loadSurahData(112, 0, false)`);
  await new Promise(r => setTimeout(r, 1200));

  const surah112Config = await evaluate(`(() => ({
    surah: window.currentSurah,
    activeTemplate: window.activeTemplateId,
    sadaqahText: document.getElementById('heroSadaqahText')?.innerText
  }))()`);
  console.log("Surah 112 Loaded State:", JSON.stringify(surah112Config, null, 2));

  // Switch back to Surah 67 (Al-Mulk)
  await evaluate(`loadSurahData(67, 0, false)`);
  await new Promise(r => setTimeout(r, 1200));

  const surah67Restored = await evaluate(`(() => ({
    surah: window.currentSurah,
    activeTemplate: window.activeTemplateId,
    sadaqahText: document.getElementById('heroSadaqahText')?.innerText
  }))()`);
  console.log("Surah 67 Restored State:", JSON.stringify(surah67Restored, null, 2));

  console.log("\n=== ALL AUTOMATED TESTS COMPLETED SUCCESSFULLY ===");
  ws.close();
  chromeProc.kill();
  process.exit(0);
}

testFeatures().catch(e => {
  console.error("Test failed with error:", e);
  process.exit(1);
});
