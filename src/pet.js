/**
 * PetBody — 桌面物理与状态机。
 *
 * 状态：idle / walk / climb / crawl / fall / drag / sit / happy
 * 边界：工作区底边是地面，左右是墙，顶边可以倒挂（crawl）。
 *
 * 现在没有逐帧素材，所以每个状态用「程序化近似」表现：
 * 位移 + 倾斜 + 挤压 + 翻转。等 assets/actions/<state>/ 里有帧以后，
 * 由 sprite.js 接管，这里只负责物理。
 */

const PET_W = 260;
const PET_H = 330;

const GRAVITY = 2400;
const WALK_SPEED = 46;
const CLIMB_SPEED = 62;
const CRAWL_SPEED = 40;
const AIR_DRAG = 0.999;

class PetBody {
  constructor({ pet, figure, rig }) {
    this.pet = pet;
    this.figure = figure;
    this.rig = rig;

    this.width = PET_W;
    this.height = PET_H;
    this.x = 0;
    this.y = 0;
    this.vx = 0;
    this.vy = 0;

    this.state = "idle";
    this.stateTime = 0;
    this.dir = -1;

    this.viewW = window.innerWidth;
    this.viewH = window.innerHeight;

    this.dragging = false;
    this.dragOffset = { x: 0, y: 0 };
    this.lastPointer = { x: 0, y: 0, t: 0 };

    this.onStateChange = null;

    this.resume();
    this.#bindDrag();
  }

  resize(width, height) {
    this.viewW = width;
    this.viewH = height;
    this.#clamp();
    this.#apply();
  }

  get groundY() {
    return this.viewH - this.height;
  }

  resume(placement) {
    if (placement && Number.isFinite(placement.x) && Number.isFinite(placement.y)) {
      this.x = placement.x;
      this.y = placement.y;
      this.#clamp();
    } else {
      this.x = this.viewW - this.width - 24;
      this.y = this.groundY;
    }
    this.#apply();
  }

  start() {
    let last = performance.now();
    const loop = (now) => {
      const dt = Math.min(0.05, (now - last) / 1000);
      last = now;
      this.#step(dt);
      this.#apply();
      requestAnimationFrame(loop);
    };
    requestAnimationFrame(loop);
  }

  poke() {
    this.#enter("happy");
    this.rig?.poke();
  }

  #enter(state) {
    if (this.state === state) return;
    this.state = state;
    this.stateTime = 0;
    this.onStateChange?.(state);
  }

  #bindDrag() {
    this.figure.addEventListener("pointerdown", (event) => {
      if (event.button !== 0) return;
      this.dragging = true;
      this.dragOffset = { x: event.clientX - this.x, y: event.clientY - this.y };
      this.lastPointer = { x: event.clientX, y: event.clientY, t: performance.now() };
      this.vx = 0;
      this.vy = 0;
      this.#enter("drag");
    });

    window.addEventListener("pointermove", (event) => {
      if (!this.dragging) return;
      this.x = event.clientX - this.dragOffset.x;
      this.y = event.clientY - this.dragOffset.y;
      const now = performance.now();
      const dt = Math.max(8, now - this.lastPointer.t) / 1000;
      this.vx = (event.clientX - this.lastPointer.x) / dt;
      this.vy = (event.clientY - this.lastPointer.y) / dt;
      this.lastPointer = { x: event.clientX, y: event.clientY, t: now };
    });

    window.addEventListener("pointerup", () => {
      if (!this.dragging) return;
      this.dragging = false;
      this.#enter("fall");
    });
  }

  #clamp() {
    this.x = Math.max(0, Math.min(this.viewW - this.width, this.x));
    this.y = Math.max(-this.height * 0.35, Math.min(this.groundY, this.y));
  }

  #step(dt) {
    this.stateTime += dt;

    switch (this.state) {
      case "idle": {
        if (this.stateTime > 4 + Math.random() * 5) {
          this.dir = Math.random() < 0.5 ? -1 : 1;
          this.#enter("walk");
        }
        break;
      }
      case "walk": {
        this.x += this.dir * WALK_SPEED * dt;
        if (this.x <= 0 || this.x >= this.viewW - this.width) {
          this.x = Math.max(0, Math.min(this.viewW - this.width, this.x));
          this.#enter("climb");
        }
        break;
      }
      case "climb": {
        this.y -= CLIMB_SPEED * dt;
        if (this.y <= 0) {
          this.y = 0;
          this.dir = -this.dir;
          this.#enter("crawl");
        }
        break;
      }
      case "crawl": {
        this.x += this.dir * CRAWL_SPEED * dt;
        if (this.x <= 0 || this.x >= this.viewW - this.width) {
          this.x = Math.max(0, Math.min(this.viewW - this.width, this.x));
          this.#enter("fall");
        }
        break;
      }
      case "fall": {
        this.vy += GRAVITY * dt;
        this.x += this.vx * dt * AIR_DRAG;
        this.y += this.vy * dt;
        this.#clamp();
        if (this.y >= this.groundY) {
          this.y = this.groundY;
          this.vy = 0;
          this.vx = 0;
          this.#enter(Math.random() < 0.35 ? "sit" : "idle");
        }
        break;
      }
      case "drag": {
        // 位置由 pointermove 直接给，这里只做轻微悬空摆动
        break;
      }
      case "sit": {
        if (this.stateTime > 3 + Math.random() * 4) this.#enter("idle");
        break;
      }
      case "happy": {
        if (this.stateTime > 1.1) this.#enter("idle");
        break;
      }
      default:
        this.#enter("idle");
    }
  }

  #apply() {
    const bob = this.state === "walk" ? Math.sin(this.stateTime * 9) * 3 : 0;
    let rotate = 0;
    let scaleX = 1;
    let scaleY = 1;

    if (this.state === "crawl") rotate = 180;
    if (this.state === "climb") rotate = this.dir * 6;
    if (this.state === "fall") {
      scaleY = 1.04;
      scaleX = 0.97;
    }
    if (this.state === "sit") scaleY = 0.93;
    if (this.state === "happy") {
      scaleY = 1 + Math.sin(this.stateTime * 18) * 0.03;
    }
    if (this.state === "drag") rotate = Math.sin(this.stateTime * 6) * 8;

    const facing = this.dir >= 0 ? 1 : -1;
    this.pet.style.transform = `translate3d(${this.x}px, ${this.y + bob}px, 0)`;
    this.figure.style.transform = `rotate(${rotate}deg) scale(${scaleX * facing}, ${scaleY})`;
  }

  currentState() {
    return this.state;
  }
}

window.PetBody = PetBody;
