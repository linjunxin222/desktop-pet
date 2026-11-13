/**
 * PetRig — a mesh-warp rig for a single flat illustration.
 *
 * Why: the project has only one PNG per character, and layering stickers on top
 * of it always reads as "paper doll". This rig deforms the artwork itself with a
 * dense vertex grid, so blinking actually closes the painted eyes and the gaze
 * shift moves the painted pupils.
 *
 * Coordinates are normalised: (0,0) top-left, (1,1) bottom-right of the sprite.
 * The warp runs on the CPU (a few thousand vertices per frame) and the GPU only
 * rasterises triangles, which keeps it smooth without any extra asset.
 */

const EYES = [
  { x: 0.415, y: 0.288, rx: 0.055, ry: 0.048 },
  { x: 0.575, y: 0.288, rx: 0.055, ry: 0.048 },
];

const NECK_Y = 0.38;
const GRID_X = 44;
const GRID_Y = 60;

const VERTEX_SHADER = `
attribute vec2 aPos;
attribute vec2 aUv;
varying vec2 vUv;
void main() {
  vUv = aUv;
  gl_Position = vec4(aPos, 0.0, 1.0);
}`;

const FRAGMENT_SHADER = `
precision mediump float;
varying vec2 vUv;
uniform sampler2D uTex;
void main() {
  gl_FragColor = texture2D(uTex, vUv);
}`;

function ellipseWeight(x, y, eye) {
  const dx = (x - eye.x) / eye.rx;
  const dy = (y - eye.y) / eye.ry;
  const d = dx * dx + dy * dy;
  if (d >= 1) return 0;
  const t = 1 - d;
  return t * t;
}

function compile(gl, type, source) {
  const shader = gl.createShader(type);
  gl.shaderSource(shader, source);
  gl.compileShader(shader);
  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
    throw new Error(gl.getShaderInfoLog(shader) || "shader compile failed");
  }
  return shader;
}

class PetRig {
  constructor(canvas) {
    this.canvas = canvas;
    this.gl = canvas.getContext("webgl", {
      alpha: true,
      premultipliedAlpha: true,
      antialias: true,
    });
    this.ready = false;
    this.failed = false;

    this.state = {
      time: 0,
      gazeX: 0,
      gazeY: 0,
      targetGazeX: 0,
      targetGazeY: 0,
      blink: 0,
      poke: 0,
      breathe: 1,
    };

    this.nextBlinkAt = 2.4;
    this.blinkStart = -1;

    // Debug-only hooks for visual regression checks (?blink=1 / ?gaze=1).
    const params = new URLSearchParams(window.location.search);
    this.debugBlink = params.get("blink") === "1" || window.__PET_DEBUG_BLINK__ === true;
    this.debugGaze = params.get("gaze") === "1";

    if (this.gl) {
      try {
        this.#initGl();
      } catch (error) {
        console.error("[rig] webgl init failed", error);
        this.failed = true;
      }
    } else {
      this.failed = true;
    }
  }

  #initGl() {
    const gl = this.gl;
    const program = gl.createProgram();
    gl.attachShader(program, compile(gl, gl.VERTEX_SHADER, VERTEX_SHADER));
    gl.attachShader(program, compile(gl, gl.FRAGMENT_SHADER, FRAGMENT_SHADER));
    gl.linkProgram(program);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
      throw new Error(gl.getProgramInfoLog(program) || "program link failed");
    }
    this.program = program;
    gl.useProgram(program);

    this.positionBuffer = gl.createBuffer();
    this.uvBuffer = gl.createBuffer();
    this.indexBuffer = gl.createBuffer();

    this.aPos = gl.getAttribLocation(program, "aPos");
    this.aUv = gl.getAttribLocation(program, "aUv");
    this.uTex = gl.getUniformLocation(program, "uTex");

    const vertsX = GRID_X + 1;
    const vertsY = GRID_Y + 1;
    const count = vertsX * vertsY;
    this.positions = new Float32Array(count * 2);
    this.uvs = new Float32Array(count * 2);

    const indices = [];
    for (let y = 0; y < GRID_Y; y += 1) {
      for (let x = 0; x < GRID_X; x += 1) {
        const a = y * vertsX + x;
        const b = a + 1;
        const c = a + vertsX;
        const d = c + 1;
        indices.push(a, c, b, b, c, d);
      }
    }
    this.indexCount = indices.length;

    gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, this.indexBuffer);
    gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, new Uint16Array(indices), gl.STATIC_DRAW);

    gl.bindBuffer(gl.ARRAY_BUFFER, this.positionBuffer);
    gl.bufferData(gl.ARRAY_BUFFER, this.positions.byteLength, gl.DYNAMIC_DRAW);

    gl.bindBuffer(gl.ARRAY_BUFFER, this.uvBuffer);
    gl.bufferData(gl.ARRAY_BUFFER, this.uvs, gl.STATIC_DRAW);

    gl.enable(gl.BLEND);
    gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA);
    gl.clearColor(0, 0, 0, 0);
  }

  async load(dataUrl) {
    if (this.failed) return false;
    const image = new Image();
    image.src = dataUrl;
    await image.decode();

    this.image = image;
    const gl = this.gl;
    this.texture = gl.createTexture();
    gl.bindTexture(gl.TEXTURE_2D, this.texture);
    gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, true);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, image);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);

    this.resize();
    this.ready = true;
    return true;
  }

  resize() {
    if (!this.gl || !this.image) return;
    const cssHeight = this.canvas.clientHeight || 330;
    const ratio = this.image.width / this.image.height;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    this.canvas.width = Math.round(cssHeight * ratio * dpr);
    this.canvas.height = Math.round(cssHeight * dpr);
    this.gl.viewport(0, 0, this.canvas.width, this.canvas.height);
  }

  /** cursor: { x, y } in -1..1 relative to the pet's centre. */
  look(cursorX, cursorY) {
    this.state.targetGazeX = Math.max(-1, Math.min(1, cursorX));
    this.state.targetGazeY = Math.max(-1, Math.min(1, cursorY));
  }

  poke() {
    this.state.poke = 1;
  }

  start() {
    if (this.failed) return;
    let last = performance.now();
    const loop = (now) => {
      const dt = Math.min(0.05, (now - last) / 1000);
      last = now;
      this.#update(dt);
      this.#draw();
      requestAnimationFrame(loop);
    };
    requestAnimationFrame(loop);
  }

  #update(dt) {
    const s = this.state;
    s.time += dt;

    const ease = 1 - Math.pow(0.001, dt);
    s.gazeX += (s.targetGazeX - s.gazeX) * ease;
    s.gazeY += (s.targetGazeY - s.gazeY) * ease;

    if (this.debugGaze) {
      s.gazeX = 0.9;
      s.gazeY = -0.2;
    }

    s.poke = Math.max(0, s.poke - dt * 3.2);

    if (s.time > this.nextBlinkAt && this.blinkStart < 0) {
      this.blinkStart = s.time;
    }
    if (this.blinkStart >= 0) {
      const p = (s.time - this.blinkStart) / 0.16;
      if (p >= 1) {
        this.blinkStart = -1;
        s.blink = 0;
        this.nextBlinkAt = s.time + 2.6 + Math.random() * 3.4;
      } else {
        s.blink = Math.sin(Math.PI * p);
      }
    }
    if (this.debugBlink) {
      s.blink = 1;
    }
  }

  #warp(u, v, out) {
    const s = this.state;
    let x = u;
    let y = v;

    const breathe = 1 + 0.012 * Math.sin(s.time * 1.7);
    y = 1 - (1 - v) * breathe;

    const swayAmount = 0.0045 * Math.pow(v, 1.6);
    x += Math.sin(s.time * 0.85) * swayAmount;
    y += Math.sin(s.time * 0.85 + 1.1) * 0.0022 * v;

    const head = Math.max(0, (NECK_Y - v) / NECK_Y) ** 2;
    x += s.gazeX * 0.018 * head;
    y += s.gazeY * 0.010 * head;

    for (const eye of EYES) {
      const weight = ellipseWeight(u, v, eye);
      if (weight <= 0) continue;
      x += s.gazeX * 0.011 * weight;
      y += s.gazeY * 0.007 * weight;
      if (s.blink > 0) {
        const squeeze = 1 - 0.88 * s.blink * weight;
        y = eye.y + (y - eye.y) * squeeze;
        x = eye.x + (x - eye.x) * (1 + 0.06 * s.blink * weight);
      }
    }

    if (s.poke > 0) {
      const squash = 1 - 0.05 * s.poke * Math.min(1, v * 1.6);
      y = 1 - (1 - y) * squash;
      x = 0.5 + (x - 0.5) * (1 + 0.035 * s.poke);
    }

    out[0] = x * 2 - 1;
    out[1] = 1 - y * 2;
  }

  #draw() {
    if (!this.ready || !this.gl) return;
    const gl = this.gl;
    const vertsX = GRID_X + 1;
    const vertsY = GRID_Y + 1;
    const out = [0, 0];

    for (let iy = 0; iy < vertsY; iy += 1) {
      const v = iy / GRID_Y;
      for (let ix = 0; ix < vertsX; ix += 1) {
        const u = ix / GRID_X;
        const index = (iy * vertsX + ix) * 2;
        this.#warp(u, v, out);
        this.positions[index] = out[0];
        this.positions[index + 1] = out[1];
        this.uvs[index] = u;
        this.uvs[index + 1] = v;
      }
    }

    gl.clear(gl.COLOR_BUFFER_BIT);
    gl.useProgram(this.program);

    gl.bindBuffer(gl.ARRAY_BUFFER, this.positionBuffer);
    gl.bufferSubData(gl.ARRAY_BUFFER, 0, this.positions);
    gl.enableVertexAttribArray(this.aPos);
    gl.vertexAttribPointer(this.aPos, 2, gl.FLOAT, false, 0, 0);

    gl.bindBuffer(gl.ARRAY_BUFFER, this.uvBuffer);
    gl.bufferSubData(gl.ARRAY_BUFFER, 0, this.uvs);
    gl.enableVertexAttribArray(this.aUv);
    gl.vertexAttribPointer(this.aUv, 2, gl.FLOAT, false, 0, 0);

    gl.activeTexture(gl.TEXTURE0);
    gl.bindTexture(gl.TEXTURE_2D, this.texture);
    gl.uniform1i(this.uTex, 0);

    gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, this.indexBuffer);
    gl.drawElements(gl.TRIANGLES, this.indexCount, gl.UNSIGNED_SHORT, 0);
  }
}

window.PetRig = PetRig;
