// avatar_renderer.js — ES Module, no bundler
// Three.js importmap must be in the HTML before this script is loaded.

import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { RectAreaLightUniformsLib } from 'three/addons/lights/RectAreaLightUniformsLib.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { VRMLoaderPlugin, VRMUtils } from '@pixiv/three-vrm';

// ── Emotion presets ──────────────────────────────────────────────────────────
const EMOTIONS = {
  neutral: {},
  happy: {
    mouthSmileLeft: 0.55, mouthSmileRight: 0.55,
    cheekSquintLeft: 0.25, cheekSquintRight: 0.25,
    browInnerUp: 0.1
  },
  thinking: {
    browInnerUp: 0.5, browDownLeft: 0.18,
    eyeLookUpLeft: 0.25, eyeLookUpRight: 0.25,
    mouthPucker: 0.15
  },
  concerned: {
    browInnerUp: 0.4, browDownLeft: 0.35, browDownRight: 0.25,
    mouthFrownLeft: 0.3, mouthFrownRight: 0.3
  },
  listening: {
    browInnerUp: 0.12,
    mouthSmileLeft: 0.08, mouthSmileRight: 0.08
  },
  surprised: {
    eyeWideLeft: 0.75, eyeWideRight: 0.75,
    browOuterUpLeft: 0.5, browOuterUpRight: 0.5,
    browInnerUp: 0.65, jawOpen: 0.22
  }
};

// Channels that are driven by lipsync (do not stomp during speech)
const LIPSYNC_CHANNELS = new Set([
  'jawOpen', 'jawForward', 'jawLeft', 'jawRight',
  'mouthClose', 'mouthFunnel', 'mouthPucker',
  'mouthLeft', 'mouthRight',
  'mouthRollUpper', 'mouthRollLower',
  'mouthShrugUpper', 'mouthShrugLower',
  'mouthSmileLeft', 'mouthSmileRight',
  'mouthFrownLeft', 'mouthFrownRight',
  'mouthDimpleLeft', 'mouthDimpleRight',
  'mouthStretchLeft', 'mouthStretchRight',
  'mouthLowerDownLeft', 'mouthLowerDownRight',
  'mouthUpperUpLeft', 'mouthUpperUpRight',
  'mouthPressLeft', 'mouthPressRight',
]);

// All channels that emotion presets can touch (for reset)
const EMOTION_CHANNELS = new Set(
  Object.values(EMOTIONS).flatMap(e => Object.keys(e))
);

// ── lerp helper ──────────────────────────────────────────────────────────────
function lerp(a, b, t) { return a + (b - a) * t; }

// ── AvatarRenderer ───────────────────────────────────────────────────────────
class AvatarRenderer {
  constructor(canvasEl, avatarUrl) {
    this._canvas = canvasEl;
    this._disposed = false;
    this._isSpeaking = false;

    // Blendshape state
    this.morphMap = new Map();   // name -> [{mesh, index}, ...] (multi-mesh)
    this.currentBS = {};
    this.targetBS = {};

    // Idle animation state
    this._clock = new THREE.Clock();
    this._blinkTimer = this._nextBlinkDelay();
    this._blinkPhase = 'idle'; // 'idle' | 'closing' | 'opening'
    this._blinkT = 0;
    this._blinkDur = 0.15; // seconds for half-blink

    // Setup RectAreaLight library
    RectAreaLightUniformsLib.init();

    // Scene
    this._scene = new THREE.Scene();
    this._scene.background = new THREE.Color('#020c12');

    // Camera — full body view, character centered
    this._camera = new THREE.PerspectiveCamera(35, 1, 0.01, 100);
    this._camera.position.set(0, 1.0, 2.4);
    this._camera.lookAt(0, 1.0, 0);

    // Renderer
    this._renderer = new THREE.WebGLRenderer({
      canvas: canvasEl,
      antialias: true,
      alpha: true,
    });
    this._renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this._renderer.outputColorSpace = THREE.SRGBColorSpace;
    this._renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this._renderer.toneMappingExposure = 1.1;
    this._renderer.shadowMap.enabled = true;

    // PBR environment (neutral studio — makes skin/hair look correct)
    const pmrem = new THREE.PMREMGenerator(this._renderer);
    pmrem.compileEquirectangularShader();
    this._scene.environment = pmrem.fromScene(new RoomEnvironment()).texture;
    pmrem.dispose();

    // Sci-fi accent lights on top of the neutral env
    const dirLight = new THREE.DirectionalLight(0x00d4ff, 0.6);
    dirLight.position.set(0.5, 3, 2);
    this._scene.add(dirLight);

    const fillLight = new THREE.DirectionalLight(0x334455, 0.3);
    fillLight.position.set(-1.5, 1, 1);
    this._scene.add(fillLight);

    // Model group (holds the loaded avatar)
    this._modelGroup = new THREE.Group();
    this._scene.add(this._modelGroup);

    // Animation mixer for body animations
    this._mixer = null;
    this._animClock = new THREE.Clock();
    this._bodyActions = {};        // key → AnimationAction
    this._currentBodyState = null;
    this._lastAnimSwitch = 0; // debounce rapid state changes

    // Camera base Z (set by _frameModel, used by zoom)
    this._baseCamZ = 2.4;

    // Current emotion target for smooth VRM lerp
    this._emotionTarget = 'neutral';

    // Persistent user rotation (mouse drag accumulates here, doesn't snap back)
    this._userRotY = 0;

    // Jaw bone fallback (for models without morph targets)
    this._jawBone = null;
    this._jawRestRotX = 0;
    this._jawTarget = 0;
    this._jawCurrent = 0;

    // Audio context (created lazily on first speech to satisfy autoplay policy)
    this._audioCtx = null;

    // Current audio source (for stopping)
    this._audioSource = null;

    // Resize observer
    this._ro = new ResizeObserver(() => this._onResize());
    this._ro.observe(canvasEl.parentElement || canvasEl);
    this._onResize();

    // Mouse controls — orbit + zoom
    this._mouse = { down: false, x: 0, y: 0, rotX: 0, rotY: 0, zoom: 0 };
    this._bindMouseControls(canvasEl);

    // Loading label (DOM, not Three.js)
    this._loadingLabel = this._makeLoadingLabel();

    // Start render loop
    this._raf = requestAnimationFrame(this._loop.bind(this));

    // Load avatar
    if (avatarUrl) this.loadAvatar(avatarUrl);
  }

  // ── Loading label ───────────────────────────────────────────────────────────
  _makeLoadingLabel() {
    const el = document.createElement('div');
    el.style.cssText = [
      'position:absolute', 'inset:0', 'display:flex',
      'align-items:center', 'justify-content:center',
      'font-family:monospace', 'font-size:11px',
      'letter-spacing:.2em', 'color:#00d4ff',
      'pointer-events:none', 'z-index:10',
      'background:transparent',
    ].join(';');
    el.textContent = 'LOADING AVATAR...';
    el.style.display = 'none';

    const parent = this._canvas.parentElement;
    if (parent) parent.appendChild(el);
    return el;
  }

  _showLoading(show) {
    if (this._loadingLabel) {
      this._loadingLabel.style.display = show ? 'flex' : 'none';
    }
  }

  // ── Resize ──────────────────────────────────────────────────────────────────
  _onResize() {
    const parent = this._canvas.parentElement || this._canvas;
    const w = parent.clientWidth  || this._canvas.clientWidth  || 640;
    const h = parent.clientHeight || this._canvas.clientHeight || 640;
    this._renderer.setSize(w, h, false);
    this._camera.aspect = w / h;
    this._camera.updateProjectionMatrix();
  }

  // ── GLB Loading ─────────────────────────────────────────────────────────────
  loadAvatar(url) {
    const finalUrl = url;

    // Clear previous model
    while (this._modelGroup.children.length) {
      const child = this._modelGroup.children[0];
      this._modelGroup.remove(child);
    }
    this.morphMap.clear();
    this.currentBS = {};
    this.targetBS = {};

    this._showLoading(true);
    this._vrm = null;

    const loader = new GLTFLoader();
    loader.register(parser => new VRMLoaderPlugin(parser));

    loader.load(
      finalUrl,
      (gltf) => {
        const vrm = gltf.userData.vrm;

        if (vrm) {
          // ── VRM model ──────────────────────────────────────────────────────
          VRMUtils.removeUnnecessaryJoints(gltf.scene);
          this._vrm = vrm;
          const model = vrm.scene;

          model.traverse((node) => {
            if (node.isMesh) {
              node.castShadow = true;
              node.frustumCulled = false;
              if (node.material) node.material.envMapIntensity = 0.3;
            }
          });

          model.visible = false;
          this._modelGroup.add(model);
          this._setupVRMPose(vrm);
          this._frameVRMBust(model);   // portrait crop: shoulders up
          this._setVRMEmotion('neutral');
          requestAnimationFrame(() => { model.visible = true; });
          this._showLoading(false);
          const allExpr = Object.keys(vrm.expressionManager?.expressionMap ?? {});
          console.log('[Avatar] VRM loaded — ALL expressions:', allExpr);
        } else {
          // ── GLB model (legacy) ─────────────────────────────────────────────
          const model = gltf.scene;
          model.traverse((node) => {
            if (node.isMesh) {
              node.castShadow = true;
              if (node.material) node.material.envMapIntensity = 0.4;
            }
          });

          this._modelGroup.add(model);
          this._setupMorphTargets();
          this._findHeadBone(model);
          this._findJawBone(model);
          this._initBodyAnims(model);
          this._frameModel(model);
          this._showLoading(false);
        }
      },
      () => {},
      (err) => {
        console.error('[AvatarRenderer] load error:', err);
        if (this._loadingLabel) {
          this._loadingLabel.textContent = 'AVATAR LOAD FAILED';
          this._loadingLabel.style.color = '#ff3355';
          this._loadingLabel.style.display = 'flex';
        }
      }
    );
  }

  // ── Mouse controls ──────────────────────────────────────────────────────────
  _bindMouseControls(canvas) {
    const m = this._mouse;

    canvas.style.cursor = 'grab';

    canvas.addEventListener('mousedown', (e) => {
      m.down = true; m.x = e.clientX; m.y = e.clientY;
      canvas.style.cursor = 'grabbing';
    });
    window.addEventListener('mouseup', () => {
      m.down = false;
      canvas.style.cursor = 'grab';
    });
    window.addEventListener('mousemove', (e) => {
      if (!m.down) return;
      const dx = e.clientX - m.x;
      const dy = e.clientY - m.y;
      m.x = e.clientX; m.y = e.clientY;
      m.rotY += dx * 0.005;   // horizontal drag → Y rotation
      m.rotX += dy * 0.005;   // vertical drag   → X rotation
      m.rotX = Math.max(-0.6, Math.min(0.6, m.rotX)); // clamp vertical
    });
    canvas.addEventListener('wheel', (e) => {
      e.preventDefault();
      m.zoom += e.deltaY * 0.001;
      m.zoom = Math.max(-0.6, Math.min(0.8, m.zoom)); // clamp zoom range
    }, { passive: false });

    // Touch support
    let _lastTouchDist = 0;
    canvas.addEventListener('touchstart', (e) => {
      if (e.touches.length === 1) { m.down = true; m.x = e.touches[0].clientX; m.y = e.touches[0].clientY; }
      if (e.touches.length === 2) _lastTouchDist = Math.hypot(e.touches[0].clientX - e.touches[1].clientX, e.touches[0].clientY - e.touches[1].clientY);
    });
    canvas.addEventListener('touchend', () => { m.down = false; });
    canvas.addEventListener('touchmove', (e) => {
      e.preventDefault();
      if (e.touches.length === 1 && m.down) {
        const dx = e.touches[0].clientX - m.x;
        const dy = e.touches[0].clientY - m.y;
        m.x = e.touches[0].clientX; m.y = e.touches[0].clientY;
        m.rotY += dx * 0.005; m.rotX += dy * 0.005;
        m.rotX = Math.max(-0.6, Math.min(0.6, m.rotX));
      }
      if (e.touches.length === 2) {
        const d = Math.hypot(e.touches[0].clientX - e.touches[1].clientX, e.touches[0].clientY - e.touches[1].clientY);
        m.zoom += (_lastTouchDist - d) * 0.003;
        m.zoom = Math.max(-0.6, Math.min(0.8, m.zoom));
        _lastTouchDist = d;
      }
    }, { passive: false });
  }

  _findHeadBone(model) {
    // No-op: lipsync is handled via morph target blendshapes (jawOpen etc.)
  }

  _findJawBone(model) {
    const candidates = ['jaw', 'mandible', 'lower_jaw', 'jawbone', 'jaw_master',
                        'cc_base_jawroot', 'lowerjaw', 'chin', 'mixamorig:jaw',
                        'mixamo.com/jaw'];
    this._jawBone = null;

    model.traverse((node) => {
      if (this._jawBone) return;
      const lname = node.name.toLowerCase();
      if (candidates.some(c => lname.includes(c.toLowerCase()))) {
        this._jawBone = node;
        this._jawRestRotX = node.rotation.x;
        console.log('[Avatar] Jaw bone found:', node.name);
      }
    });

    if (!this._jawBone) {
      // Fallback: use Head bone with tiny rotation to simulate mouth movement
      model.traverse((node) => {
        if (!this._jawBone && node.name === 'Head') {
          this._jawBone = node;
          this._jawRestRotX = node.rotation.x;
          this._jawIsHead = true;
          console.log('[Avatar] Using Head bone as jaw fallback');
        }
      });
    }

    if (!this._jawBone) {
      console.log('[Avatar] No jaw bone found — jaw animation disabled');
    }
  }

  // ── Bust/portrait frame — shoulders to top of head ─────────────────────────
  _frameVRMBust(model) {
    const box = new THREE.Box3().setFromObject(model);
    const size = box.getSize(new THREE.Vector3());
    const H = size.y;

    // Center model, face toward camera (VRM default faces +Z, camera is at +Z)
    this._modelGroup.position.set(
      -(box.min.x + size.x / 2),
      -box.min.y,
      -(box.min.z + size.z / 2)
    );
    this._userRotY = Math.PI;  // face toward camera from first frame

    // Bust region: shoulders (~78% H) to crown (100% H)
    const shoulderY = H * 0.78;
    const crownY    = H * 1.00;
    const bustH     = crownY - shoulderY;           // ~0.22 × H
    const targetY   = shoulderY + bustH * 0.45;     // slightly below neck center

    const fovRad = (this._camera.fov * Math.PI) / 180;
    const dist   = (bustH * 1.7) / (2 * Math.tan(fovRad / 2)); // zoomed out

    this._camera.near = dist * 0.01;
    this._camera.far  = dist * 20;
    this._baseCamZ    = dist;

    this._camera.position.set(0, targetY, dist);
    this._camera.lookAt(0, targetY, 0);
    this._camera.updateProjectionMatrix();

    console.log('[Avatar] Bust frame — H:', H.toFixed(2),
      'targetY:', targetY.toFixed(2), 'dist:', dist.toFixed(2));
  }

  // ── Auto-frame model to camera ─────────────────────────────────────────────
  _frameModel(model) {
    const box = new THREE.Box3().setFromObject(model);
    const center = box.getCenter(new THREE.Vector3());
    const size   = box.getSize(new THREE.Vector3());

    // Center X/Z, sit model at Y=0
    this._modelGroup.position.set(-center.x, -box.min.y, -center.z);

    const modelHeight = size.y;
    const targetY     = modelHeight * 0.5;
    const fovRad      = (this._camera.fov * Math.PI) / 180;

    // Head fills ~55% of frame height — gives breathing room on all sides
    const dist = modelHeight / (0.55 * 2 * Math.tan(fovRad / 2));

    // Expand clipping planes to fit any scale model
    this._camera.near = dist * 0.001;
    this._camera.far  = dist * 10;

    this._camera.position.set(0, targetY, dist);
    this._camera.lookAt(0, targetY, 0);
    this._camera.updateProjectionMatrix();

    // Reset zoom clamp relative to new dist
    this._baseCamZ = dist;

    console.log('[Avatar] Framed model — height:', modelHeight.toFixed(2),
                'center-y:', targetY.toFixed(2), 'cam-z:', dist.toFixed(2));
  }

  // ── Body animation system ───────────────────────────────────────────────────
  _initBodyAnims(avatarModel) {
    if (this._mixer) { this._mixer.stopAllAction(); this._mixer = null; }
    this._bodyActions = {};
    this._currentBodyState = null;
    this._mixer = new THREE.AnimationMixer(avatarModel);

    // State → animation file mapping (two states only: idle + speaking)
    const ANIM_DEFS = [
      { key: 'idle',     url: '/models/idle.glb' },
      { key: 'speaking', url: '/models/konusma.glb' },
    ];

    const loader = new GLTFLoader();

    const prepareClip = (gltf) => {
      if (!gltf.animations?.length) return null;
      const clip = gltf.animations[0].clone();
      clip.tracks = clip.tracks.filter(t => {
        // Keep only bone tracks — strip face morph tracks so they don't fight blendshapes
        const isMorph = t.name.includes('morphTargetInfluences');
        if (isMorph) return false;
        // Normalize armature prefix (e.g. Armature_3 → Armature)
        t.name = t.name.replace(/^Armature_\d+\./, 'Armature.');
        return true;
      });
      return clip;
    };

    const loadClip = (def) => {
      loader.load(def.url, (gltf) => {
        const clip = prepareClip(gltf);
        if (!clip) return;
        const action = this._mixer.clipAction(clip);
        action.setLoop(THREE.LoopRepeat, Infinity);
        this._bodyActions[def.key] = action;

        // Auto-start idle as soon as it's ready
        if (def.key === 'idle' && !this._currentBodyState) {
          action.play();
          this._currentBodyState = 'idle';
        }
      }, undefined, () => {
        // GLB not found — fall back to old animation.glb for idle only
        if (def.key === 'idle') {
          loader.load('/public/animation.glb', (gltf) => {
            const clip = prepareClip(gltf);
            if (!clip) return;
            const action = this._mixer.clipAction(clip);
            action.setLoop(THREE.LoopRepeat, Infinity);
            action.play();
            this._bodyActions['idle'] = action;
            this._currentBodyState = 'idle';
          }, undefined, () => {});
        }
      });
    };

    for (const def of ANIM_DEFS) loadClip(def);
  }

  // ── Body animation state switcher ───────────────────────────────────────────
  setBodyAnim(stateName) {
    if (!this._mixer) return;

    const key = stateName === 'speaking' ? 'speaking' : 'idle';
    if (this._currentBodyState === key) return;

    // Debounce: ignore rapid flips (SPEAKING↔LISTENING within 500ms)
    const now = performance.now();
    if (now - this._lastAnimSwitch < 500) return;

    const from = this._bodyActions[this._currentBodyState];
    const to   = this._bodyActions[key];
    if (!to) return;

    if (!to.isRunning()) {
      to.reset();
      to.play();
    }
    if (from && from !== to) {
      from.crossFadeTo(to, 0.5, true);
    }
    this._currentBodyState = key;
    this._lastAnimSwitch = now;
  }

  // ── Morph target setup ──────────────────────────────────────────────────────
  _setupMorphTargets() {
    this.morphMap.clear();
    this.currentBS = {};
    this.targetBS = {};

    this._modelGroup.traverse((node) => {
      if (node.isMesh && node.morphTargetDictionary) {
        for (const [name, index] of Object.entries(node.morphTargetDictionary)) {
          if (!this.morphMap.has(name)) this.morphMap.set(name, []);
          this.morphMap.get(name).push({ mesh: node, index });
        }
      }
    });

    // Initialise all to zero
    for (const name of this.morphMap.keys()) {
      this.currentBS[name] = 0;
      this.targetBS[name] = 0;
    }

    console.log('[Avatar] Morph targets found:', this.morphMap.size, [...this.morphMap.keys()].slice(0,10));
  }

  // ── Blendshape control ──────────────────────────────────────────────────────
  setBlendshapes(values) {
    if (this._vrm) {
      const em = this._vrm.expressionManager;
      if (!em) return;

      // Direct ARKit → VRM PascalCase mapping (model has all 52 clips)
      // Blog note: JawOpen and MouthClose must be set together
      const jaw = values.jawOpen ?? 0;
      for (const [name, value] of Object.entries(values)) {
        const vrmName = name.charAt(0).toUpperCase() + name.slice(1);
        em.setValue(vrmName, Math.min(1, Math.max(0, value)));
      }
      // MouthClose balances JawOpen to prevent broken-looking mouth
      em.setValue('MouthClose', Math.min(1, jaw * 0.15));
      return;
    }
    // GLB morph target path
    for (const [name, value] of Object.entries(values)) {
      this.targetBS[name] = value;
      if (!(name in this.currentBS)) this.currentBS[name] = 0;
    }
    if (this._jawBone && 'jawOpen' in values) {
      this._jawTarget = values.jawOpen;
    }
  }

  // ── Emotion control ─────────────────────────────────────────────────────────
  setEmotion(name) {
    if (this._vrm) {
      this._setVRMEmotion(name);
      return;
    }
    // GLB morph target path
    const preset = EMOTIONS[name] || EMOTIONS.neutral;
    for (const ch of EMOTION_CHANNELS) {
      if (!this._isSpeaking || !LIPSYNC_CHANNELS.has(ch)) this.targetBS[ch] = 0;
    }
    for (const [ch, val] of Object.entries(preset)) {
      if (!this._isSpeaking || !LIPSYNC_CHANNELS.has(ch)) this.targetBS[ch] = val;
    }
  }

  _setVRMEmotion(name) {
    // Store target — applied gradually in render loop to avoid snapping
    this._emotionTarget = name;
  }

  _applyVRMEmotion(em, name, speaking) {
    // Channels owned by lipsync — never touch during speech
    const LIPSYNC_OWNED = new Set([
      'JawOpen','MouthClose','MouthFunnel','MouthPucker',
      'MouthShrugUpper','MouthShrugLower','MouthLowerDownLeft','MouthLowerDownRight',
      'MouthUpperUpLeft','MouthUpperUpRight','MouthStretchLeft','MouthStretchRight',
      'MouthRollLower','MouthRollUpper','MouthLeft','MouthRight',
      'aa','oh','ou','ih','ee',
    ]);

    // Channels we control for emotion (upper face only during speech)
    const ALL_EMOTION = [
      'happy','angry','sad','relaxed','Surprised','neutral',
      'BrowInnerUp','BrowDownLeft','BrowDownRight',
      'BrowOuterUpLeft','BrowOuterUpRight',
      'EyeWideLeft','EyeWideRight','EyeSquintLeft','EyeSquintRight',
      'CheekSquintLeft','CheekSquintRight',
      // mouth only when NOT speaking
      'MouthSmileLeft','MouthSmileRight',
      'MouthFrownLeft','MouthFrownRight',
    ];

    // Build target values
    const targets = {};
    for (const k of ALL_EMOTION) targets[k] = 0;

    switch (name) {
      case 'happy':
        targets['BrowInnerUp']      = 0.15;
        targets['BrowOuterUpLeft']  = 0.1;
        targets['BrowOuterUpRight'] = 0.1;
        targets['CheekSquintLeft']  = 0.35;
        targets['CheekSquintRight'] = 0.35;
        if (!speaking) {
          targets['happy']           = 0.6;
          targets['MouthSmileLeft']  = 0.45;
          targets['MouthSmileRight'] = 0.45;
        }
        break;
      case 'thinking':
        targets['BrowInnerUp']    = 0.45;
        targets['BrowDownLeft']   = 0.25;
        targets['EyeSquintLeft']  = 0.2;
        targets['EyeSquintRight'] = 0.1;
        break;
      case 'concerned':
        targets['sad']           = 0.35;
        targets['BrowInnerUp']   = 0.4;
        targets['BrowDownLeft']  = 0.3;
        targets['BrowDownRight'] = 0.2;
        if (!speaking) {
          targets['MouthFrownLeft']  = 0.2;
          targets['MouthFrownRight'] = 0.2;
        }
        break;
      case 'surprised':
        targets['Surprised']         = 0.6;
        targets['EyeWideLeft']       = 0.6;
        targets['EyeWideRight']      = 0.6;
        targets['BrowOuterUpLeft']   = 0.5;
        targets['BrowOuterUpRight']  = 0.5;
        targets['BrowInnerUp']       = 0.55;
        break;
      case 'listening':
        targets['relaxed']           = 0.25;
        targets['BrowInnerUp']       = 0.08;
        break;
      case 'angry':
        targets['angry']           = 0.5;
        targets['BrowDownLeft']    = 0.55;
        targets['BrowDownRight']   = 0.55;
        targets['EyeSquintLeft']   = 0.3;
        targets['EyeSquintRight']  = 0.3;
        break;
      default:
        targets['neutral'] = 0.05;
        break;
    }

    // Smooth lerp toward targets (skip lipsync-owned channels during speech)
    const speed = 0.12;
    for (const [k, target] of Object.entries(targets)) {
      if (speaking && LIPSYNC_OWNED.has(k)) continue;
      const cur = em.getValue(k) ?? 0;
      em.setValue(k, cur + (target - cur) * speed);
    }
  }

  // ── Idle animations ─────────────────────────────────────────────────────────
  _updateIdle(dt, elapsed) {
    // Note: body movement comes from GLB animation clips via _mixer.
    // No programmatic rotation.y override here — that would fight user rotation.

    // Auto-blink
    this._blinkTimer -= dt;
    if (this._blinkPhase === 'idle' && this._blinkTimer <= 0) {
      this._blinkPhase = 'closing';
      this._blinkT = 0;
    }

    if (this._blinkPhase === 'closing') {
      this._blinkT += dt / this._blinkDur;
      const v = Math.min(1, this._blinkT);
      this._setBlink(v);
      if (this._blinkT >= 1) { this._blinkPhase = 'opening'; this._blinkT = 0; }
    } else if (this._blinkPhase === 'opening') {
      this._blinkT += dt / this._blinkDur;
      const v = Math.max(0, 1 - this._blinkT);
      this._setBlink(v);
      if (this._blinkT >= 1) {
        this._setBlink(0);
        this._blinkPhase = 'idle';
        this._blinkTimer = this._nextBlinkDelay();
      }
    }
  }

  // ── VRM pose & idle ─────────────────────────────────────────────────────────
  _setupVRMPose(vrm) {
    const h = vrm.humanoid;
    if (!h) return;

    // Normalized bones persist through vrm.update() — correct API for poses
    const set = (name, x = 0, y = 0, z = 0) => {
      const bone = h.getNormalizedBoneNode(name);
      if (bone) bone.rotation.set(x, y, z);
    };

    set('leftUpperArm',  0, 0,  1.15);
    set('rightUpperArm', 0, 0, -1.15);
    set('leftLowerArm',  0, 0,  0.15);
    set('rightLowerArm', 0, 0, -0.15);
    set('leftHand',      0, 0,  0.1);
    set('rightHand',     0, 0, -0.1);
    set('chest',        -0.04, 0, 0);
    set('spine',         0.02, 0, 0);

    // Apply pose immediately so model reveals without T-pose
    vrm.update(0);

    // Cache normalized bone refs for idle animation
    this._vrmBones = {};
    for (const name of ['spine','chest','neck','head','leftUpperArm','rightUpperArm']) {
      this._vrmBones[name] = h.getNormalizedBoneNode(name);
    }
  }

  _updateVRMIdle(vrm, elapsed) {
    const b = this._vrmBones;
    if (!b) return;

    const breath  = Math.sin(elapsed * 1.55) * 0.06;
    const headY   = Math.sin(elapsed * 0.35) * 0.08;
    const headX   = Math.sin(elapsed * 0.50) * 0.04;
    const armSway = Math.sin(elapsed * 0.40) * 0.04;

    if (b.chest) b.chest.rotation.x = -0.04 + breath;
    if (b.spine) b.spine.rotation.x =  0.02 - breath * 0.4;
    if (b.head)  { b.head.rotation.y = headY; b.head.rotation.x = headX; }
    if (b.neck)  b.neck.rotation.y = headY * 0.4;
    if (b.leftUpperArm)  b.leftUpperArm.rotation.z  =  1.15 + armSway;
    if (b.rightUpperArm) b.rightUpperArm.rotation.z = -1.15 - armSway;
  }

  _setBlink(v) {
    if (this._vrm) {
      const em = this._vrm.expressionManager;
      if (!em) return;
      // Try 'blink' first, fall back to separate left/right
      em.setValue('EyeBlinkLeft', v);
      em.setValue('EyeBlinkRight', v);
    } else {
      this.targetBS['eyeBlinkLeft']  = v;
      this.targetBS['eyeBlinkRight'] = v;
    }
  }

  _nextBlinkDelay() {
    return 3 + Math.random() * 3;
  }

  // ── Render loop ─────────────────────────────────────────────────────────────
  _loop(timestamp) {
    if (this._disposed) return;
    this._raf = requestAnimationFrame(this._loop.bind(this));

    const dt = this._clock.getDelta();
    const elapsed = this._clock.elapsedTime;

    if (this._mixer) this._mixer.update(this._animClock.getDelta());
    if (this._vrm) {
      this._updateVRMIdle(this._vrm, elapsed);
      const em = this._vrm.expressionManager;
      if (em && this._emotionTarget) {
        this._applyVRMEmotion(em, this._emotionTarget, this._isSpeaking);
      }
      this._vrm.update(dt);
    }

    this._updateIdle(dt, elapsed);

    // Mouse rotation — Y is persistent (character stays at dragged angle)
    const m = this._mouse;
    this._userRotY += m.rotY;
    m.rotY *= 0.85;   // inertia decay
    m.rotX *= 0.85;

    this._modelGroup.rotation.y = this._userRotY;
    this._modelGroup.rotation.x = m.rotX;   // X springs back to 0 naturally

    // Zoom: move camera along its Z axis
    const baseZ = this._baseCamZ ?? 2.4;
    this._camera.position.z = baseZ + m.zoom * (baseZ / 2.4);

    // Jaw bone rotation fallback
    if (this._jawBone) {
      this._jawCurrent = lerp(this._jawCurrent, this._jawTarget, Math.min(1, dt * 14));
      this._jawBone.rotation.x = this._jawRestRotX + this._jawCurrent * 0.32;
    }

    // Lerp currentBS toward targetBS
    const lerpFactor = Math.min(1, dt * 8);
    for (const [name, entries] of this.morphMap) {
      const target = this.targetBS[name] ?? 0;
      const current = this.currentBS[name] ?? 0;
      const next = lerp(current, target, lerpFactor);
      this.currentBS[name] = next;
      for (const e of entries) {
        e.mesh.morphTargetInfluences[e.index] = next;
      }
    }

    this._renderer.render(this._scene, this._camera);
  }

  // ── Speech / LipSync ────────────────────────────────────────────────────────
  async playSpeech(audio_b64, blendshapes, n_frames, fps, emotion) {
    // Stop any previous speech
    this._stopSpeech();
    this._isSpeaking = true;

    // Lazy-create AudioContext
    if (!this._audioCtx) {
      this._audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    }
    if (this._audioCtx.state === 'suspended') {
      await this._audioCtx.resume();
    }

    // Decode base64 WAV → ArrayBuffer
    const binary = atob(audio_b64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
    const arrayBuffer = bytes.buffer;

    let audioBuffer;
    try {
      audioBuffer = await this._audioCtx.decodeAudioData(arrayBuffer);
    } catch (err) {
      console.error('[AvatarRenderer] Audio decode error:', err);
      this._isSpeaking = false;
      return;
    }

    // Start playback
    const source = this._audioCtx.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(this._audioCtx.destination);
    source.start(0);
    this._audioSource = source;

    // Step through blendshape frames
    const frameDuration = 1000 / fps; // ms
    const startTime = performance.now();
    let frameIndex = 0;

    await new Promise((resolve) => {
      const tick = (now) => {
        if (this._disposed || !this._isSpeaking) {
          resolve();
          return;
        }

        const elapsed = now - startTime;
        const expectedFrame = Math.floor(elapsed / frameDuration);

        while (frameIndex <= expectedFrame && frameIndex < n_frames) {
          const frame = {};
          for (const [channel, frames] of Object.entries(blendshapes)) {
            if (frames && frameIndex < frames.length) {
              frame[channel] = frames[frameIndex];
            }
          }
          this.setBlendshapes(frame);
          frameIndex++;
        }

        if (frameIndex < n_frames) {
          requestAnimationFrame(tick);
        } else {
          resolve();
        }
      };
      requestAnimationFrame(tick);
    });

    // Wait for audio to finish (if not already done)
    const remainingAudio = audioBuffer.duration - (performance.now() - startTime) / 1000;
    if (remainingAudio > 0) {
      await new Promise(r => setTimeout(r, remainingAudio * 1000));
    }

    // Reset mouth channels to zero
    this._resetLipsyncChannels();
    this._isSpeaking = false;

    // Apply final emotion
    if (emotion) this.setEmotion(emotion);
  }

  _stopSpeech() {
    if (this._audioSource) {
      try { this._audioSource.stop(); } catch (_) {}
      this._audioSource = null;
    }
    this._isSpeaking = false;
  }

  _resetLipsyncChannels() {
    for (const ch of LIPSYNC_CHANNELS) {
      this.targetBS[ch] = 0;
    }
    this._jawTarget = 0;
  }

  // ── Dispose ─────────────────────────────────────────────────────────────────
  dispose() {
    this._disposed = true;
    cancelAnimationFrame(this._raf);
    this._stopSpeech();
    if (this._audioCtx) {
      this._audioCtx.close();
      this._audioCtx = null;
    }
    this._ro.disconnect();
    this._renderer.dispose();
    if (this._loadingLabel && this._loadingLabel.parentElement) {
      this._loadingLabel.parentElement.removeChild(this._loadingLabel);
    }
  }
}

export { AvatarRenderer };
