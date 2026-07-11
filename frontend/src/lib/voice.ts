/** Voice engine built on the Web Speech API (works in Chrome/Electron).
 *
 * Modes:
 *  - push-to-talk: startListening() -> one utterance -> onTranscript
 *  - wake word:    startWakeWord()  -> continuous recognition; when a wake
 *                  word is heard, the following speech becomes the command.
 */

const SR: any =
  (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

export const speechSupported = !!SR;

export interface VoiceOptions {
  language: string;
  wakeWords: string[];
  onTranscript: (text: string) => void;   // final command text
  onInterim: (text: string) => void;      // live partial text
  onWake: () => void;
  onStateChange: (state: "idle" | "listening" | "waiting-wake") => void;
  onPermissionDenied?: () => void;        // mic blocked — stop auto-restarting
}

export class VoiceEngine {
  private rec: any = null;
  private opts: VoiceOptions;
  private mode: "off" | "ptt" | "wake" = "off";
  private awake = false;

  constructor(opts: VoiceOptions) {
    this.opts = opts;
  }

  update(opts: Partial<VoiceOptions>) {
    Object.assign(this.opts, opts);
  }

  private build(continuous: boolean) {
    const rec = new SR();
    rec.lang = this.opts.language || "en-US";
    rec.continuous = continuous;
    rec.interimResults = true;
    return rec;
  }

  startListening() {
    this.stop();
    this.mode = "ptt";
    const rec = this.build(false);
    let finalText = "";
    rec.onresult = (ev: any) => {
      let interim = "";
      for (let i = ev.resultIndex; i < ev.results.length; i++) {
        const t = ev.results[i][0].transcript;
        if (ev.results[i].isFinal) finalText += t;
        else interim += t;
      }
      this.opts.onInterim(finalText + interim);
    };
    rec.onend = () => {
      this.mode = "off";
      this.opts.onStateChange("idle");
      if (finalText.trim()) this.opts.onTranscript(finalText.trim());
      else this.opts.onInterim("");
    };
    rec.onerror = () => {
      this.mode = "off";
      this.opts.onStateChange("idle");
    };
    this.rec = rec;
    rec.start();
    this.opts.onStateChange("listening");
  }

  startWakeWord() {
    this.stop();
    this.mode = "wake";
    this.awake = false;
    const rec = this.build(true);
    let command = "";
    let commandTimer: any = null;

    const finishCommand = () => {
      const text = command.trim();
      command = "";
      this.awake = false;
      this.opts.onStateChange("waiting-wake");
      if (text) this.opts.onTranscript(text);
    };

    rec.onresult = (ev: any) => {
      for (let i = ev.resultIndex; i < ev.results.length; i++) {
        const t: string = ev.results[i][0].transcript;
        if (!this.awake) {
          const lower = t.toLowerCase();
          const wake = this.opts.wakeWords.find((w) => lower.includes(w.toLowerCase()));
          if (wake) {
            this.awake = true;
            this.opts.onWake();
            this.opts.onStateChange("listening");
            // Anything said after the wake word in the same result counts.
            const after = lower.split(wake.toLowerCase()).slice(1).join(" ").trim();
            if (after && ev.results[i].isFinal) command += after + " ";
          }
        } else {
          if (ev.results[i].isFinal) command += t + " ";
          this.opts.onInterim(command + (ev.results[i].isFinal ? "" : t));
          clearTimeout(commandTimer);
          commandTimer = setTimeout(finishCommand, 1800);
        }
      }
    };
    rec.onend = () => {
      if (this.mode === "wake") {
        try { rec.start(); } catch { /* restarting too fast is fine to ignore */ }
      }
    };
    rec.onerror = (e: any) => {
      if (e.error === "not-allowed" || e.error === "service-not-allowed") {
        this.mode = "off";
        this.opts.onStateChange("idle");
        this.opts.onPermissionDenied?.();
      }
    };
    this.rec = rec;
    rec.start();
    this.opts.onStateChange("waiting-wake");
  }

  stop() {
    this.mode = "off";
    if (this.rec) {
      this.rec.onend = null;
      try { this.rec.stop(); } catch { /* already stopped */ }
      this.rec = null;
    }
    this.opts.onStateChange("idle");
  }

  get active() {
    return this.mode !== "off";
  }
}

// ---- text to speech ---------------------------------------------------------
//
// Speaking state + live amplitude are broadcast on `voiceBus` so the dashboard
// core visualization can react to speech:
//   voiceBus events: "speaking" (detail: boolean), "amplitude" (detail: 0..1)

export const voiceBus = new EventTarget();

function emitSpeaking(on: boolean) {
  voiceBus.dispatchEvent(new CustomEvent("speaking", { detail: on }));
}
function emitAmplitude(a: number) {
  voiceBus.dispatchEvent(new CustomEvent("amplitude", { detail: a }));
}

let currentAudio: HTMLAudioElement | null = null;
let ampTimer: any = null;

function cleanText(text: string): string {
  return text
    .replace(/```[\s\S]*?```/g, " code block omitted. ")
    .replace(/[*_#`>|]/g, "")
    .slice(0, 2500);
}

export async function speak(text: string, rate = 1.0, voiceName = "") {
  stopSpeaking();
  const clean = cleanText(text);
  if (!clean.trim()) return;

  // Try the server-side engine first (Piper etc.); it returns null/JSON when
  // the browser should synthesize instead.
  try {
    const { serverTts } = await import("./api");
    const blob = await serverTts(clean);
    if (blob) {
      playWavReactive(blob, rate);
      return;
    }
  } catch {
    /* backend unreachable — fall through to browser voices */
  }

  const u = new SpeechSynthesisUtterance(clean);
  u.rate = rate;
  if (voiceName) {
    const v = speechSynthesis.getVoices().find((v) => v.name === voiceName);
    if (v) u.voice = v;
  }
  u.onstart = () => {
    emitSpeaking(true);
    // Browser TTS gives no audio stream — simulate a lively amplitude.
    ampTimer = setInterval(() => emitAmplitude(0.35 + Math.random() * 0.5), 90);
  };
  const end = () => {
    clearInterval(ampTimer);
    emitAmplitude(0);
    emitSpeaking(false);
  };
  u.onend = end;
  u.onerror = end;
  speechSynthesis.speak(u);
}

/** Play a WAV with a real audio-reactive analyser driving the visualizer. */
function playWavReactive(blob: Blob, rate: number) {
  const url = URL.createObjectURL(blob);
  const audio = new Audio(url);
  audio.playbackRate = rate;
  currentAudio = audio;

  const ctx = new AudioContext();
  const source = ctx.createMediaElementSource(audio);
  const analyser = ctx.createAnalyser();
  analyser.fftSize = 256;
  source.connect(analyser);
  analyser.connect(ctx.destination);
  const data = new Uint8Array(analyser.frequencyBinCount);

  let raf = 0;
  const tick = () => {
    analyser.getByteFrequencyData(data);
    let sum = 0;
    for (let i = 0; i < data.length; i++) sum += data[i];
    emitAmplitude(Math.min(1, (sum / data.length / 255) * 2.2));
    raf = requestAnimationFrame(tick);
  };

  audio.onplay = () => {
    emitSpeaking(true);
    tick();
  };
  const end = () => {
    cancelAnimationFrame(raf);
    emitAmplitude(0);
    emitSpeaking(false);
    URL.revokeObjectURL(url);
    ctx.close().catch(() => {});
    currentAudio = null;
  };
  audio.onended = end;
  audio.onerror = end;
  audio.play().catch(end);
}

export function stopSpeaking() {
  speechSynthesis.cancel();
  if (currentAudio) {
    currentAudio.pause();
    currentAudio.src = "";
    currentAudio = null;
  }
  clearInterval(ampTimer);
  emitAmplitude(0);
  emitSpeaking(false);
}

export function listVoices(): SpeechSynthesisVoice[] {
  return speechSynthesis.getVoices();
}
