import { spawn } from 'child_process';

async function run() {
  console.log("=== Testing Default Settings (No Query Params) in Google Chrome ===");
  const targetUrl = "http://localhost:8765/";
  
  const chromePath = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
  const userDir = `/tmp/chrome_test_profile_${Date.now()}`;
  
  const args = [
    '--headless=new',
    '--disable-gpu',
    '--remote-debugging-port=9226',
    '--autoplay-policy=no-user-gesture-required',
    `--user-data-dir=${userDir}`,
    targetUrl
  ];
  
  const chromeProc = spawn(chromePath, args);
  
  let wsUrl = null;
  for (let i = 0; i < 25; i++) {
    await new Promise(r => setTimeout(r, 400));
    try {
      const res = await fetch('http://127.0.0.1:9226/json/list');
      const list = await res.json();
      const pageTarget = list.find(t => t.type === 'page' && t.url.includes('localhost:8765'));
      if (pageTarget && pageTarget.webSocketDebuggerUrl) {
        wsUrl = pageTarget.webSocketDebuggerUrl;
        break;
      }
    } catch (e) {}
  }
  
  if (!wsUrl) {
    console.error("Failed to connect to target page in Chrome");
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
      callbacks.set(id, (res) => {
        resolve(res.result?.result?.value);
      });
      ws.send(JSON.stringify({ id, method, params }));
    });
  }
  
  // Wait 3 seconds for initial load
  await new Promise(r => setTimeout(r, 3000));
  
  const state = await sendCdp('Runtime.evaluate', {
    expression: `(() => {
      return {
        currentSurah,
        currentReciter,
        currentMode,
        currentAyahIndex,
        currentSpeed,
        surahSelectValue: document.getElementById('surahSelect')?.value,
        reciterSelectValue: document.getElementById('reciterSelect')?.value,
        modeSelectValue: document.getElementById('modeSelect')?.value,
        speedSelectValue: document.getElementById('speedSelect')?.value,
        mainHeaderTitle: document.getElementById('mainHeaderTitle')?.innerText,
        mainHeaderSub: document.getElementById('mainHeaderSub')?.innerText,
        statusBadge: document.getElementById('statusBadge')?.innerText,
        audioSrc: audioEl?.src,
        audioPaused: audioEl?.paused,
        versesCount: loadedVerses?.length
      };
    })()`,
    returnByValue: true
  });
  
  console.log("\n--- Default State Inspection ---");
  console.log(JSON.stringify(state, null, 2));
  
  let passed = 0;
  let failed = 0;
  function assert(cond, name) {
    if (cond) {
      console.log(`✅ [PASS] ${name}`);
      passed++;
    } else {
      console.error(`❌ [FAIL] ${name}`);
      failed++;
    }
  }
  
  assert(state && state.currentSurah === 67, `Default Surah is 67 (Al-Mulk)`);
  assert(state && state.currentReciter === 'husary', `Default Reciter is Mahmoud Khalil Al-Husary`);
  assert(state && state.currentMode === 'alternating', `Default Mode is alternating (Arabic + Urdu)`);
  assert(state && state.currentSpeed === 1.0, `Default Speed is 1.0`);
  assert(state && state.currentAyahIndex === 0, `Default Ayah is 1`);
  assert(state && state.surahSelectValue === '67', `Surah select shows 67`);
  assert(state && state.reciterSelectValue === 'husary', `Reciter select shows husary`);
  assert(state && state.modeSelectValue === 'alternating', `Mode select shows alternating`);
  assert(state && state.speedSelectValue === '1.0', `Speed select shows 1.0`);
  assert(state && state.versesCount === 30, `Loaded all 30 verses of Surah Al-Mulk`);
  assert(state && state.audioSrc && state.audioSrc.includes('Husary_128kbps/067001.mp3'), `Audio source is Husary 067001.mp3`);
  
  // Test clicking play button
  console.log("\n--- Testing Play Button ---");
  await sendCdp('Runtime.evaluate', {
    expression: `(() => {
      document.getElementById('playBtn')?.click();
    })()`
  });
  await new Promise(r => setTimeout(r, 1500));
  
  const playState = await sendCdp('Runtime.evaluate', {
    expression: `(() => {
      return {
        isPlaying: isPlaying,
        audioPaused: audioEl?.paused,
        audioCurrentTime: audioEl?.currentTime,
        playBtnText: document.getElementById('playBtn')?.innerText
      };
    })()`,
    returnByValue: true
  });
  
  console.log("Play State:", playState);
  assert(playState && playState.isPlaying === true, `Audio is playing`);
  assert(playState && playState.playBtnText === '⏸', `Button text changed to pause ⏸`);
  assert(playState && playState.audioPaused === false, `audioEl is unpaused`);
  
  console.log(`\n========================================`);
  console.log(`DEFAULT SETTINGS TEST: ${passed} Passed, ${failed} Failed`);
  console.log(`========================================`);
  
  ws.close();
  chromeProc.kill();
  process.exit(failed > 0 ? 1 : 0);
}

run().catch(e => {
  console.error(e);
  process.exit(1);
});
