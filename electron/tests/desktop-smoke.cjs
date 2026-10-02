// Run against a locally launched packaged app with --remote-debugging-port=9227.
// Uses synthetic overlay text only; never starts audio or calls AI providers.
const assert = require("node:assert/strict");

const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
async function targets() {
  return (await fetch("http://127.0.0.1:9227/json/list")).json();
}
async function connect(target) {
  const socket = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => {
    socket.addEventListener("open", resolve, { once: true });
    socket.addEventListener("error", reject, { once: true });
  });
  let id = 0;
  const pending = new Map();
  socket.addEventListener("message", ({ data }) => {
    const msg = JSON.parse(data);
    const callbacks = pending.get(msg.id);
    if (!callbacks) return;
    pending.delete(msg.id);
    if (msg.error) callbacks.reject(new Error(msg.error.message));
    else callbacks.resolve(msg.result);
  });
  return {
    async evaluate(expression) {
      const result = await new Promise((resolve, reject) => {
        const key = ++id;
        pending.set(key, { resolve, reject });
        socket.send(JSON.stringify({ id: key, method: "Runtime.evaluate",
          params: { expression, awaitPromise: true, returnByValue: true } }));
      });
      if (result.exceptionDetails) throw new Error(result.exceptionDetails.text);
      return result.result?.value;
    },
    close() { socket.close(); },
  };
}

async function waitFor(predicate) {
  for (let i = 0; i < 40; i++) {
    let value;
    try { value = await predicate(); } catch { /* App may still be starting. */ }
    if (value) return value;
    await delay(250);
  }
  throw new Error("Desktop smoke check timed out");
}

async function main() {
  const page = await waitFor(async () => (await targets()).find((t) => t.type === "page" && t.url.startsWith("app://interviewcopilot") && !t.url.includes("overlay")));
  const primary = await connect(page);
  let overlay;
  try {
    await waitFor(() => primary.evaluate("document.readyState === 'complete' && !!window.electronAPI && document.querySelector('#root').childElementCount > 0"));
    assert.equal(await primary.evaluate("window.electronAPI.getVersion()"), "1.0.0");
    assert.equal(await primary.evaluate("document.querySelector('#root').childElementCount > 0"), true);
    await primary.evaluate("window.electronAPI.openOverlay()");
    const target = await waitFor(async () => (await targets()).find((t) => t.url.includes("#/overlay")));
    overlay = await connect(target);
    await waitFor(() => overlay.evaluate("document.querySelector('#root').childElementCount > 0"));
    const events = [
      { type: "reset" }, { type: "capturing", value: true },
      { type: "question_detected", text: "Test question", request_id: "smoke-1" },
      { type: "ai_suggestion", token: "Synthetic ", provider: "gemini", request_id: "smoke-1" },
      { type: "ai_suggestion", token: "answer", provider: "gemini", request_id: "smoke-1" },
      { type: "ai_complete", full_text: "Synthetic answer", provider: "gemini", request_id: "smoke-1" },
    ];
    await primary.evaluate(`(${JSON.stringify(events)}).forEach(msg => window.electronAPI.pushOverlayUpdate(msg))`);
    await waitFor(() => overlay.evaluate("document.body.innerText.includes('Synthetic answer')"));
    overlay.close();
    await primary.evaluate("window.electronAPI.closeOverlay()");
    await primary.evaluate("window.electronAPI.openOverlay()");
    const reopened = await waitFor(async () => (await targets()).find((t) => t.url.includes("#/overlay")));
    overlay = await connect(reopened);
    await waitFor(() => overlay.evaluate("document.body.innerText.includes('Synthetic answer')"));
    console.log("PASS: packaged UI, preload bridge, overlay route, streamed answer, and reopen state");
  } finally {
    await primary.evaluate("window.electronAPI.closeOverlay()").catch(() => {});
    overlay?.close();
    primary.close();
  }
}

main().then(() => process.exit(0), (err) => { console.error(err.message); process.exit(1); });
