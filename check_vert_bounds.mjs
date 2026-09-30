import { spawn } from 'child_process';
import fs from 'fs';

async function checkBounds() {
  const targetUrl = "http://localhost:8765/?surah=67&ayah=3&qari=husary&mode=arabic";
  const chromePath = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
  const userDir = `/tmp/chrome_bounds_${Date.now()}`;

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

  await new Promise(r => setTimeout(r, 2500));

  const bounds = await sendCdp("Runtime.evaluate", {
    expression: `
      (async () => {
        if (typeof selectTemplate === 'function') {
          await selectTemplate('tmpl_master_madinah');
        }
        const vertBtn = document.getElementById('playerAspect9x16Btn');
        if (vertBtn) vertBtn.click();
        if (typeof loadAyah === 'function') {
          loadAyah(2, 'arabic', false);
        }

        await new Promise(r => setTimeout(r, 500));

        const getInfo = (id) => {
          const el = document.getElementById(id);
          if (!el) return null;
          const r = el.getBoundingClientRect();
          const cs = window.getComputedStyle(el);
          return {
            id,
            rect: { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) },
            display: cs.display,
            visibility: cs.visibility,
            opacity: cs.opacity,
            top: el.style.top,
            left: el.style.left,
            width: el.style.width,
            height: el.style.height,
            textLen: (el.innerText || '').length,
            sampleText: (el.innerText || '').slice(0, 40)
          };
        };

        return {
          heroCard: getInfo('heroCard'),
          container: getInfo('heroLayoutContainer'),
          banner: getInfo('boxSurahBanner'),
          arabic: getInfo('boxArabic'),
          urdu: getInfo('boxUrdu'),
          english: getInfo('boxEnglish')
        };
      })()
    `,
    awaitPromise: true,
    returnByValue: true
  });

  console.log("=== BOUNDS INFO ===");
  console.log(JSON.stringify(bounds.result ? bounds.result.value : bounds, null, 2));

  ws.close();
  chromeProc.kill();
  process.exit(0);
}

checkBounds().catch(err => {
  console.error("Error:", err);
  process.exit(1);
});
