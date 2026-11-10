const petScreen = document.querySelector("#pet-screen");
const houseScreen = document.querySelector("#house-screen");
const bubble = document.querySelector("#speech-bubble");
const character = document.querySelector("#character");
const characterButton = document.querySelector("#character-button");

const replies = [
  "嗯？你叫我吗？",
  "今天也一起加油吧！",
  "我在这里陪着你。",
  "嘿嘿，被你发现我在发呆啦。",
];
let replyIndex = 0;

function showHouse() {
  petScreen.hidden = true;
  houseScreen.hidden = false;
}

function showDesktopPet() {
  houseScreen.hidden = true;
  petScreen.hidden = false;
}

function react(message = replies[replyIndex % replies.length]) {
  bubble.textContent = message;
  replyIndex += 1;
  character.classList.remove("is-happy");
  void character.offsetWidth;
  character.classList.add("is-happy");
}

characterButton.addEventListener("click", () => react());
document.querySelector("#wave-button").addEventListener("click", () => react("收到你的挥手啦！"));
document.querySelector("#house-button").addEventListener("click", showHouse);
document.querySelector("#back-button").addEventListener("click", showDesktopPet);
document.querySelector("#return-button").addEventListener("click", showDesktopPet);
document.querySelector("#close-button").addEventListener("click", () => window.desktopPet?.close());

document.querySelector("#stage").addEventListener("contextmenu", (event) => {
  event.preventDefault();
  showHouse();
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !houseScreen.hidden) showDesktopPet();
});
