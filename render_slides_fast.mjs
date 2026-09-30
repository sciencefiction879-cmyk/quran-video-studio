#!/usr/bin/env node
/**
 * render_slides_fast.mjs
 * High-Speed Headless Chrome Slide & WBW Renderer using Chrome DevTools Protocol (CDP).
 * Capable of capturing 20+ synchronized word-by-word slides per second.
 */

import { spawn } from 'child_process';
import fs from 'fs';
import path from 'path';

async function main() {
  const manifestPath = process.argv[2];
  if (!manifestPath || !fs.existsSync(manifestPath)) {
    console.error("Usage: node render_slides_fast.mjs <manifest.json>");
    process.exit(1);
  }

  const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
  const width = manifest.width || 1920;
  const height = manifest.height || 1080;
  const items = manifest.items || [];

  const chromeCandidates = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium-browser"
  ];
  const chromePath = chromeCandidates.find(c => fs.existsSync(c)) || chromeCandidates[0];

  const debugPort = 9400 + Math.floor(Math.random() * 500);
  const userDir = `/tmp/quran_chrome_prof_${Date.now()}_${debugPort}`;

  const chromeArgs = [
    '--headless=new',
    '--disable-gpu',
    '--hide-scrollbars',
    '--disable-dev-shm-usage',
    '--no-sandbox',
    '--mute-audio',
    `--remote-debugging-port=${debugPort}`,
    `--user-data-dir=${userDir}`,
    `--window-size=${width},${height}`
  ];

  const chromeProc = spawn(chromePath, chromeArgs);

  // Clean up on exit
  function cleanup() {
    try { chromeProc.kill(); } catch (e) {}
    try { fs.rmSync(userDir, { recursive: true, force: true }); } catch (e) {}
  }
  process.on('exit', cleanup);
  process.on('SIGINT', () => { cleanup(); process.exit(1); });
  process.on('SIGTERM', () => { cleanup(); process.exit(1); });

  // Connect to Chrome target
  let wsUrl = null;
  for (let i = 0; i < 80; i++) {
    await new Promise(r => setTimeout(r, 100));
    try {
      const res = await fetch(`http://127.0.0.1:${debugPort}/json/new`, { method: "PUT" });
      const target = await res.json();
      if (target && target.webSocketDebuggerUrl) {
        wsUrl = target.webSocketDebuggerUrl;
        break;
      }
    } catch (e) {}
  }

  if (!wsUrl) {
    console.error("Failed to connect to Chrome debugging target on port", debugPort);
    cleanup();
    process.exit(1);
  }

  const ws = new WebSocket(wsUrl);
  let msgId = 1;
  const pending = new Map();
  ws.onmessage = (e) => {
    try {
      const d = JSON.parse(e.data);
      if (d.id && pending.has(d.id)) {
        const handler = pending.get(d.id);
        pending.delete(d.id);
        handler(d.result || d);
      }
    } catch (err) {}
  };
  ws.onerror = (err) => {
    console.error("[CDP] WebSocket error:", err.message || err);
  };
  ws.onclose = () => {
    for (const [id, cb] of pending.entries()) {
      try { cb({ error: { message: "CDP WebSocket disconnected" } }); } catch (e) {}
    }
    pending.clear();
  };
  await new Promise(r => ws.onopen = r);

  const sendCdp = (method, params = {}, timeoutMs = 25000) => new Promise((resolve, reject) => {
    const cur = msgId++;
    const timer = setTimeout(() => {
      if (pending.has(cur)) {
        pending.delete(cur);
        resolve({ error: { message: `CDP command ${method} timed out after ${timeoutMs}ms` } });
      }
    }, timeoutMs);

    pending.set(cur, (res) => {
      clearTimeout(timer);
      resolve(res);
    });

    try {
      ws.send(JSON.stringify({ id: cur, method, params }));
    } catch (e) {
      clearTimeout(timer);
      pending.delete(cur);
      resolve({ error: { message: e.message } });
    }
  });

  await sendCdp("Page.enable");

  let totalTasks = 0;
  for (const item of items) {
    if (item.type === 'wbw') {
      if (item.base_out) totalTasks++;
      if (item.word_outs) totalTasks += item.word_outs.length;
    } else if (item.type === 'urdu_wbw') {
      if (item.word_outs) totalTasks += item.word_outs.length;
    } else {
      totalTasks++;
    }
  }

  let completedTasks = 0;
  const reportProgress = (msg, outPath) => {
    completedTasks++;
    console.log(JSON.stringify({
      type: "progress",
      completed: completedTasks,
      total: totalTasks,
      message: msg,
      file: outPath
    }));
  };

  const force = manifest.force !== false;

  for (let i = 0; i < items.length; i++) {
    const item = items[i];
    const navUrl = item.url;
    await sendCdp("Page.navigate", { url: navUrl }, 15000);

    // Wait for slideReady (up to 2.5s)
    for (let wait = 0; wait < 50; wait++) {
      await new Promise(r => setTimeout(r, 50));
      const res = await sendCdp("Runtime.evaluate", { expression: "Boolean(window.slideReady)", returnByValue: true }, 4000);
      if (res?.result?.value) break;
    }

    if (item.type === 'wbw') {
      if (item.base_out) {
        if (force || !fs.existsSync(item.base_out) || fs.statSync(item.base_out).size < 10000) {
          await sendCdp("Runtime.evaluate", { expression: "window.highlightWord(-1)", returnByValue: true }, 4000);
          const shot = await sendCdp("Page.captureScreenshot", { format: "png" }, 20000);
          if (shot && shot.data) {
            fs.writeFileSync(item.base_out, Buffer.from(shot.data, "base64"));
          }
        }
        reportProgress("Base slide captured", item.base_out);
      }

      if (item.word_outs && Array.isArray(item.word_outs)) {
        for (const [wIdx, outPath] of item.word_outs) {
          if (force || !fs.existsSync(outPath) || fs.statSync(outPath).size < 10000) {
            await sendCdp("Runtime.evaluate", { expression: `window.highlightWord(${wIdx})`, returnByValue: true }, 4000);
            const shot = await sendCdp("Page.captureScreenshot", { format: "png" }, 20000);
            if (shot && shot.data) {
              fs.writeFileSync(outPath, Buffer.from(shot.data, "base64"));
            }
          }
          reportProgress(`Word ${wIdx} captured`, outPath);
        }
      }
    } else if (item.type === 'urdu_wbw') {
      if (item.word_outs && Array.isArray(item.word_outs)) {
        for (const [wIdx, outPath] of item.word_outs) {
          if (force || !fs.existsSync(outPath) || fs.statSync(outPath).size < 10000) {
            await sendCdp("Runtime.evaluate", { expression: `window.highlightUrduWord(${wIdx})`, returnByValue: true }, 4000);
            const shot = await sendCdp("Page.captureScreenshot", { format: "png" }, 20000);
            if (shot && shot.data) {
              fs.writeFileSync(outPath, Buffer.from(shot.data, "base64"));
            }
          }
          reportProgress(`Urdu Word ${wIdx} captured`, outPath);
        }
      }
    } else {
      if (item.out) {
        if (force || !fs.existsSync(item.out) || fs.statSync(item.out).size < 10000) {
          const shot = await sendCdp("Page.captureScreenshot", { format: "png" }, 20000);
          if (shot && shot.data) {
            fs.writeFileSync(item.out, Buffer.from(shot.data, "base64"));
          }
        }
        reportProgress("Slide captured", item.out);
      }
    }

    // Periodic memory cleanup to keep Chrome snappy
    if (completedTasks > 0 && completedTasks % 120 === 0) {
      await sendCdp("HeapProfiler.collectGarbage", {}, 4000).catch(() => null);
    }
  }

  try { ws.close(); } catch (e) {}
  cleanup();
  console.log(JSON.stringify({ type: "done", completed: completedTasks, total: totalTasks }));
  process.exit(0);
}

main().catch(err => {
  console.error("Fatal error in render_slides_fast:", err);
  process.exit(1);
});
