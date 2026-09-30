import { spawn } from 'child_process';
import fs from 'fs';

async function verifyHeroCard() {
  console.log("=== Verifying Live Hero Card for Surah 67 Ayah 3 ===");
  const targetUrl = "http://localhost:8765/?surah=67&ayah=3&qari=husary&mode=arabic";
  const chromePath = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
  const userDir = `/tmp/chrome_test_profile_${Date.now()}`;

  const args = [
    '--headless=new',
    '--disable-gpu',
    '--remote-debugging-port=9222',
    '--autoplay-policy=no-user-gesture-required',
    `--window-size=1920,1080`,
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
      callbacks.set(id, (res) => resolve(res.result));
      ws.send(JSON.stringify({ id, method, params }));
    });
  }

  await sendCdp("Page.enable");
  await sendCdp("Runtime.enable");

  // Wait 3.5 seconds for all Quran API data and templates to load and render
  await new Promise(r => setTimeout(r, 3500));

  // Ensure Surah 67 Ayah 3 is loaded and master template is selected
  await sendCdp("Runtime.evaluate", {
    expression: `
      (async () => {
        if (typeof selectTemplate === 'function') {
          await selectTemplate('tmpl_master_madinah');
        }
        if (typeof loadAyah === 'function') {
          loadAyah(2, 'arabic', false); // index 2 is Ayah 3
        }
      })()
    `,
    awaitPromise: true
  });

  await new Promise(r => setTimeout(r, 1200));

  // Capture screenshot of #heroCard
  const evalRes = await sendCdp("Runtime.evaluate", {
    expression: `
      (() => {
        const el = document.getElementById('heroCard');
        if (!el) return null;
        const rect = el.getBoundingClientRect();
        return { x: rect.x, y: rect.y, width: rect.width, height: rect.height };
      })()
    `,
    returnByValue: true
  });

  const clip = evalRes.value;
  console.log("Hero Card Clip:", clip);

  const snap = await sendCdp("Page.captureScreenshot", {
    format: "png",
    clip: clip ? {
      x: clip.x,
      y: clip.y,
      width: clip.width,
      height: clip.height,
      scale: 1
    } : undefined
  });

  const outPath = "/Users/shaddo/.gemini/antigravity/scratch/surah_fatiha/verify_hero_surah67_ayah3.png";
  fs.writeFileSync(outPath, Buffer.from(snap.data, 'base64'));
  console.log(`Saved screenshot to ${outPath}`);

  // Also copy to artifacts directory
  const artifactPath = "/Users/shaddo/.gemini/antigravity/brain/718824dd-35a2-4dc3-8b1d-27be14de4d07/verify_hero_surah67_ayah3.png";
  fs.copyFileSync(outPath, artifactPath);
  console.log(`Copied to artifact at ${artifactPath}`);

  ws.close();
  chromeProc.kill();
  process.exit(0);
}

verifyHeroCard().catch(err => {
  console.error("Error:", err);
  process.exit(1);
});
