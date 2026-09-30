import { spawn } from 'child_process';

async function run() {
  console.log("=== Testing Target URL in Google Chrome via CDP ===");
  const targetUrl = "http://localhost:8765/?surah=67&qari=husary&mode=alternating&ayah=1&speed=1";
  
  const chromePath = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
  const userDir = `/tmp/chrome_test_profile_${Date.now()}`;
  
  const args = [
    '--headless=new',
    '--disable-gpu',
    '--remote-debugging-port=9222',
    '--autoplay-policy=no-user-gesture-required',
    `--user-data-dir=${userDir}`,
    targetUrl
  ];
  
  const chromeProc = spawn(chromePath, args);
  
  let wsUrl = null;
  for (let i = 0; i < 25; i++) {
    await new Promise(r => setTimeout(r, 400));
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
    console.error("Failed to connect to target page in Chrome");
    chromeProc.kill();
    process.exit(1);
  }
  
  console.log("Connected to Chrome Target Page via WebSocket:", wsUrl);
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
  
  // Wait 3 seconds for initial Surah 67 & options to load and stabilize
  await new Promise(r => setTimeout(r, 3000));
  
  // Evaluate state in page
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
        audioCurrentTime: audioEl?.currentTime,
        audioReadyState: audioEl?.readyState,
        isPlaying: isPlaying,
        versesCount: loadedVerses?.length
      };
    })()`,
    returnByValue: true
  });
  
  console.log("\n--- Chrome Initial State Inspection ---");
  console.log(JSON.stringify(state, null, 2));
  
  let testsPassed = 0;
  let testsFailed = 0;
  
  function assert(cond, name) {
    if (cond) {
      console.log(`✅ [PASS] ${name}`);
      testsPassed++;
    } else {
      console.error(`❌ [FAIL] ${name}`);
      testsFailed++;
    }
  }
  
  assert(state && state.currentSurah === 67, `Current Surah is 67 (got ${state?.currentSurah})`);
  assert(state && state.currentReciter === 'husary', `Current Reciter is husary (got ${state?.currentReciter})`);
  assert(state && state.currentMode === 'alternating', `Current Mode is alternating (got ${state?.currentMode})`);
  assert(state && state.currentAyahIndex === 0, `Current Ayah is 1 (index 0) (got ${state?.currentAyahIndex})`);
  assert(state && state.currentSpeed === 1.0, `Current Speed is 1.0 (got ${state?.currentSpeed})`);
  assert(state && state.surahSelectValue === '67', `Surah select element displays 67 (got ${state?.surahSelectValue})`);
  assert(state && state.reciterSelectValue === 'husary', `Reciter select element displays husary (got ${state?.reciterSelectValue})`);
  assert(state && state.modeSelectValue === 'alternating', `Mode select element displays alternating (got ${state?.modeSelectValue})`);
  assert(state && state.versesCount === 30, `Loaded 30 verses of Surah Al-Mulk (got ${state?.versesCount})`);
  assert(state && state.audioSrc && state.audioSrc.includes('Husary_128kbps/067001.mp3'), `Audio element loaded Husary 067001.mp3 (got ${state?.audioSrc})`);
  
  // Test Clicking Play
  console.log("\n--- Testing Playback Trigger ---");
  await sendCdp('Runtime.evaluate', {
    expression: `(() => {
      document.getElementById('playBtn')?.click();
    })()`
  });
  
  // Wait 1.5 seconds for audio playback to advance
  await new Promise(r => setTimeout(r, 1500));
  
  const playState = await sendCdp('Runtime.evaluate', {
    expression: `(() => {
      return {
        audioPaused: audioEl?.paused,
        audioCurrentTime: audioEl?.currentTime,
        isPlaying: isPlaying,
        playBtnText: document.getElementById('playBtn')?.innerText
      };
    })()`,
    returnByValue: true
  });
  
  console.log("Playback Check:", playState);
  assert(playState && playState.isPlaying === true, `Player is playing (isPlaying = ${playState?.isPlaying})`);
  assert(playState && playState.playBtnText === '⏸', `Play button icon changed to pause ⏸ (got ${playState?.playBtnText})`);
  assert(playState && playState.audioPaused === false, `audioEl.paused is false`);
  
  // Test Alternating Mode Transition to Urdu Translation
  console.log("\n--- Testing Alternating Mode (Arabic -> Urdu Transition) ---");
  await sendCdp('Runtime.evaluate', {
    expression: `(() => {
      audioEl.dispatchEvent(new Event('ended'));
    })()`
  });
  
  await new Promise(r => setTimeout(r, 1000));
  
  const altState = await sendCdp('Runtime.evaluate', {
    expression: `(() => {
      return {
        playbackPhase,
        currentAyahIndex,
        audioSrc: audioEl?.src,
        statusBadge: document.getElementById('statusBadge')?.innerText
      };
    })()`,
    returnByValue: true
  });
  
  console.log("Alternating Check:", altState);
  assert(altState && altState.playbackPhase === 'urdu', `Playback switched to Urdu translation phase (got ${altState?.playbackPhase})`);
  assert(altState && altState.audioSrc && altState.audioSrc.includes('urdu_shamshad_ali_khan_46kbps/067001.mp3'), `Audio src switched to Urdu audio (got ${altState?.audioSrc})`);
  
  // Test Transition from Urdu back to Arabic of Ayah 2
  console.log("\n--- Testing Alternating Mode (Urdu -> Next Ayah Arabic Transition) ---");
  await sendCdp('Runtime.evaluate', {
    expression: `(() => {
      audioEl.dispatchEvent(new Event('ended'));
    })()`
  });
  
  await new Promise(r => setTimeout(r, 1000));
  
  const nextState = await sendCdp('Runtime.evaluate', {
    expression: `(() => {
      return {
        playbackPhase,
        currentAyahIndex,
        audioSrc: audioEl?.src,
        statusBadge: document.getElementById('statusBadge')?.innerText
      };
    })()`,
    returnByValue: true
  });
  
  console.log("Next Ayah Check:", nextState);
  assert(nextState && nextState.playbackPhase === 'arabic', `Playback returned to Arabic for next Ayah (got ${nextState?.playbackPhase})`);
  assert(nextState && nextState.currentAyahIndex === 1, `Ayah index advanced to 1 (verse 2) (got ${nextState?.currentAyahIndex})`);
  assert(nextState && nextState.audioSrc && nextState.audioSrc.includes('Husary_128kbps/067002.mp3'), `Audio src loaded Ayah 2 Husary 067002.mp3 (got ${nextState?.audioSrc})`);
  
  console.log(`\n========================================`);
  console.log(`TEST RESULTS: ${testsPassed} Passed, ${testsFailed} Failed`);
  console.log(`========================================`);
  
  ws.close();
  chromeProc.kill();
  process.exit(testsFailed > 0 ? 1 : 0);
}

run().catch(err => {
  console.error("Test execution error:", err);
  process.exit(1);
});
