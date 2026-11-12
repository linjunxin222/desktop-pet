const api = window.desktopPet;

const petEl = document.querySelector("#pet");
const petFigure = document.querySelector("#pet-figure");
const bubble = document.querySelector("#speech-bubble");
const character = document.querySelector("#character");

const replies = [
  "嗯？你叫我吗？",
  "今天也一起加油吧！",
  "我在这里陪着你。",
  "嘿嘿，被你发现我在发呆啦。",
];

const HIT_SELECTORS = ["#pet-figure", "#speech-bubble", "#quick-actions"];

let replyIndex = 0;
let visits = 1;
let rig = null;
let body = null;
let lastPayload = "";
let lastPublishAt = 0;

function visible(element) {
  return element && !element.hidden && element.getBoundingClientRect().width > 0;
}

function collectHitRegions() {
  if (body?.state === "drag") {
    // 拖拽时要接住整个窗口，否则光标一离开她就收不到 pointermove
    return [{ x: 0, y: 0, w: window.innerWidth, h: window.innerHeight }];
  }
  const regions = [];
  for (const selector of HIT_SELECTORS) {
    const element = document.querySelector(selector);
    if (!visible(element)) continue;
    const rect = element.getBoundingClientRect();
    regions.push({
      x: Math.round(rect.left),
      y: Math.round(rect.top),
      w: Math.round(rect.width),
      h: Math.round(rect.height),
    });
  }
  return regions;
}

function publishHitRegions(force = false) {
  const now = performance.now();
  if (!force && now - lastPublishAt < 110) return;
  lastPublishAt = now;
  const payload = JSON.stringify(collectHitRegions());
  if (payload === lastPayload) return;
  lastPayload = payload;
  api?.reportHitRegions(JSON.parse(payload));
}

function react(message) {
  bubble.textContent = message ?? replies[replyIndex % replies.length];
  replyIndex += 1;
  body?.poke();
  api?.saveState({ replyIndex });
}

function greet() {
  bubble.textContent = visits > 1 ? "我回来啦。" : "嗨，我来陪你啦！";
}

document.querySelector("#character-button").addEventListener("click", (event) => {
  event.stopPropagation();
  react();
});
document.querySelector("#wave-button").addEventListener("click", () => react("收到你的挥手啦！"));
document.querySelector("#close-button").addEventListener("click", () => api?.close());

document.querySelector("#stage").addEventListener("contextmenu", (event) => {
  event.preventDefault();
});

window.addEventListener("pointermove", (event) => {
  if (!rig) return;
  const rect = petFigure.getBoundingClientRect();
  const centerX = rect.left + rect.width / 2;
  const centerY = rect.top + rect.height * 0.3;
  rig.look((event.clientX - centerX) / 190, (event.clientY - centerY) / 190);
});

window.addEventListener("pointerleave", () => rig?.look(0, 0));

window.addEventListener("resize", () => {
  body?.resize(window.innerWidth, window.innerHeight);
  lastPayload = "";
  publishHitRegions(true);
});

setInterval(() => publishHitRegions(), 120);

setInterval(() => {
  if (!body) return;
  api?.saveState({ x: Math.round(body.x), y: Math.round(body.y), state: body.state });
}, 2500);

async function boot() {
  const state = (await api?.getState()) ?? null;
  if (state?.pet) {
    replyIndex = Number.isFinite(state.pet.replyIndex) ? state.pet.replyIndex : 0;
    visits = Number.isFinite(state.pet.visits) ? state.pet.visits : 1;
  }

  if (window.PetRig && window.CHARACTER_TEXTURE) {
    rig = new window.PetRig(character);
    const ok = await rig.load(window.CHARACTER_TEXTURE);
    if (ok) rig.start();
    else character.hidden = true;
  }

  if (window.PetBody) {
    body = new window.PetBody({ pet: petEl, figure: petFigure, rig });
    body.resize(window.innerWidth, window.innerHeight);
    if (state?.pet) body.resume({ x: state.pet.x, y: state.pet.y });
    body.start();
  }

  greet();
  publishHitRegions(true);
}

void boot();
