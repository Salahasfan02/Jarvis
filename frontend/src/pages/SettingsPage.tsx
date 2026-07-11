import { useEffect, useState } from "react";
import { api, OllamaModel, pullModel, statsApi } from "../lib/api";
import { listVoices } from "../lib/voice";

function Row(props: { label: string; sub?: string; children: React.ReactNode }) {
  return (
    <div className="row">
      <div>
        <div className="label">{props.label}</div>
        {props.sub && <div className="sub">{props.sub}</div>}
      </div>
      {props.children}
    </div>
  );
}

function Toggle(props: { checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <label className="switch">
      <input type="checkbox" checked={props.checked}
             onChange={(e) => props.onChange(e.target.checked)} />
      <span />
    </label>
  );
}

export function SettingsPage(props: {
  settings: any;
  onPatch: (patch: any) => void;
}) {
  const s = props.settings;
  const [models, setModels] = useState<OllamaModel[]>([]);
  const [pullName, setPullName] = useState("");
  const [pullStatus, setPullStatus] = useState<{ text: string; pct: number } | null>(null);
  const [tools, setTools] = useState<any[]>([]);
  const [voices, setVoices] = useState<SpeechSynthesisVoice[]>([]);
  const [engines, setEngines] = useState<any[]>([]);

  const refreshModels = () => api.models().then((r) => setModels(r.models)).catch(() => {});
  useEffect(() => {
    refreshModels();
    api.tools().then(setTools).catch(() => {});
    statsApi.ttsEngines().then(setEngines).catch(() => {});
    setVoices(listVoices());
    speechSynthesis.onvoiceschanged = () => setVoices(listVoices());
  }, []);

  if (!s) return <div className="page">Loading…</div>;

  const doPull = async () => {
    const name = pullName.trim();
    if (!name) return;
    setPullStatus({ text: "starting…", pct: 0 });
    try {
      await pullModel(name, (e) => {
        if (e.error) setPullStatus({ text: `error: ${e.error}`, pct: 0 });
        else {
          const pct = e.total ? Math.round((e.completed / e.total) * 100) : 0;
          setPullStatus({ text: `${e.status ?? ""} ${pct ? pct + "%" : ""}`, pct });
        }
      });
      setPullStatus({ text: "done ✓", pct: 100 });
      setPullName("");
      refreshModels();
    } catch (e: any) {
      setPullStatus({ text: `failed: ${e.message}`, pct: 0 });
    }
  };

  return (
    <div className="page">
      <div className="page-inner">
        <h1>Settings</h1>

        <div className="panel">
          <h3>AI model</h3>
          <Row label="Active model" sub="Used for all conversations; switch anytime.">
            <select
              value={s.ollama.model}
              onChange={(e) => props.onPatch({ ollama: { model: e.target.value } })}
            >
              {!models.some((m) => m.name.startsWith(s.ollama.model)) && (
                <option value={s.ollama.model}>{s.ollama.model}</option>
              )}
              {models.map((m) => (
                <option key={m.name} value={m.name}>
                  {m.name} {m.details?.parameter_size ? `(${m.details.parameter_size})` : ""}
                </option>
              ))}
            </select>
          </Row>
          <Row label="Vision model" sub="Multimodal model for camera/screen (e.g. llava). Empty = disabled.">
            <input type="text" value={s.ollama.vision_model}
                   placeholder="llava"
                   onChange={(e) => props.onPatch({ ollama: { vision_model: e.target.value } })} />
          </Row>
          <Row label="Embedding model" sub="For semantic memory recall (e.g. nomic-embed-text). Empty = keyword matching.">
            <input type="text" value={s.ollama.embedding_model}
                   placeholder="nomic-embed-text"
                   onChange={(e) => props.onPatch({ ollama: { embedding_model: e.target.value } })} />
          </Row>
          <Row label="Temperature" sub="0 = precise, 1 = creative">
            <input type="number" step={0.1} min={0} max={2} value={s.ollama.temperature}
                   onChange={(e) => props.onPatch({ ollama: { temperature: parseFloat(e.target.value) || 0 } })} />
          </Row>
          <Row label="Context length" sub="Tokens the model can see (higher = more RAM)">
            <input type="number" step={1024} value={s.ollama.num_ctx}
                   onChange={(e) => props.onPatch({ ollama: { num_ctx: parseInt(e.target.value) || 8192 } })} />
          </Row>
          <Row label="GPU layers" sub="-1 lets Ollama decide; 0 forces CPU">
            <input type="number" value={s.ollama.num_gpu}
                   onChange={(e) => props.onPatch({ ollama: { num_gpu: parseInt(e.target.value) } })} />
          </Row>
          <Row label="Keep model in memory" sub="e.g. 5m, 1h, -1 = forever">
            <input type="text" value={s.ollama.keep_alive}
                   onChange={(e) => props.onPatch({ ollama: { keep_alive: e.target.value } })} />
          </Row>
        </div>

        <div className="panel">
          <h3>Installed models</h3>
          {models.map((m) => (
            <Row key={m.name} label={m.name}
                 sub={`${(m.size / 1e9).toFixed(1)} GB ${m.details?.quantization_level ?? ""}`}>
              <button className="btn danger"
                      onClick={() => api.deleteModel(m.name).then(refreshModels)}>
                Remove
              </button>
            </Row>
          ))}
          <Row label="Download a model" sub="Any model from ollama.com/library">
            <div style={{ display: "flex", gap: 8, flexDirection: "column", alignItems: "flex-end" }}>
              <div style={{ display: "flex", gap: 8 }}>
                <input type="text" placeholder="e.g. qwen2.5, mistral, llava"
                       value={pullName} onChange={(e) => setPullName(e.target.value)} />
                <button className="btn primary" onClick={doPull}>Pull</button>
              </div>
              {pullStatus && (
                <div style={{ width: 280 }}>
                  <div className="pull-progress">{pullStatus.text}</div>
                  <div className="progress-bar"><div style={{ width: `${pullStatus.pct}%` }} /></div>
                </div>
              )}
            </div>
          </Row>
        </div>

        <div className="panel">
          <h3>Assistant</h3>
          <Row label="Name">
            <input type="text" value={s.assistant.name}
                   onChange={(e) => props.onPatch({ assistant: { name: e.target.value } })} />
          </Row>
          <Row label="Wake words" sub="Comma-separated">
            <input type="text" value={s.assistant.wake_words.join(", ")}
                   onChange={(e) => props.onPatch({
                     assistant: { wake_words: e.target.value.split(",").map((w: string) => w.trim()).filter(Boolean) },
                   })} />
          </Row>
        </div>

        <div className="panel">
          <h3>Voice</h3>
          <Row label="Voice input" sub="Microphone button & wake word">
            <Toggle checked={s.voice.enabled}
                    onChange={(v) => props.onPatch({ voice: { enabled: v } })} />
          </Row>
          <Row label="Speak responses" sub="Read answers aloud">
            <Toggle checked={s.voice.tts_enabled}
                    onChange={(v) => props.onPatch({ voice: { tts_enabled: v } })} />
          </Row>
          <Row label="Speech engine"
               sub="Browser = built-in voices. Piper = local neural TTS (brew install piper-tts + a voice model). New engines and voice clones plug in via backend/app/speech/engines.py.">
            <select value={s.voice.tts_engine ?? "browser"}
                    onChange={(e) => props.onPatch({ voice: { tts_engine: e.target.value } })}>
              {(engines.length ? engines : [{ id: "browser", name: "Browser voices", available: true, reason: "" }])
                .map((e: any) => (
                  <option key={e.id} value={e.id} disabled={!e.available}>
                    {e.name}{e.available ? "" : ` — ${e.reason}`}
                  </option>
                ))}
            </select>
          </Row>
          {s.voice.tts_engine === "piper" && (
            <Row label="Piper voice model" sub="Path to a .onnx voice, e.g. ~/piper/en_US-lessac-medium.onnx">
              <input type="text" value={s.voice.piper_voice_path ?? ""}
                     placeholder="/path/to/voice.onnx"
                     onChange={(e) => props.onPatch({ voice: { piper_voice_path: e.target.value } })} />
            </Row>
          )}
          <Row label="Voice">
            <select value={s.voice.tts_voice}
                    onChange={(e) => props.onPatch({ voice: { tts_voice: e.target.value } })}>
              <option value="">System default</option>
              {voices.map((v) => <option key={v.name} value={v.name}>{v.name}</option>)}
            </select>
          </Row>
          <Row label="Speech rate">
            <input type="number" step={0.1} min={0.5} max={2} value={s.voice.tts_rate}
                   onChange={(e) => props.onPatch({ voice: { tts_rate: parseFloat(e.target.value) || 1 } })} />
          </Row>
          <Row label="Language" sub="Speech recognition language, e.g. en-US">
            <input type="text" value={s.voice.language}
                   onChange={(e) => props.onPatch({ voice: { language: e.target.value } })} />
          </Row>
        </div>

        <div className="panel">
          <h3>Memory</h3>
          <Row label="Long-term memory" sub="Recall saved facts in every conversation">
            <Toggle checked={s.memory.enabled}
                    onChange={(v) => props.onPatch({ memory: { enabled: v } })} />
          </Row>
          <Row label="Max recalled memories">
            <input type="number" min={1} max={20} value={s.memory.max_recalled}
                   onChange={(e) => props.onPatch({ memory: { max_recalled: parseInt(e.target.value) || 5 } })} />
          </Row>
        </div>

        <div className="panel">
          <h3>Tool permissions</h3>
          <Row label="Tools enabled" sub="Let the assistant use tools at all">
            <Toggle checked={s.tools.enabled}
                    onChange={(v) => props.onPatch({ tools: { enabled: v } })} />
          </Row>
          {tools.map((t) => (
            <Row key={t.name} label={t.name} sub={t.description.slice(0, 90)}>
              {t.risk === "dangerous" ? (
                <span className="sub" style={{ color: "var(--danger)" }}>always asks</span>
              ) : (
                <select
                  value={t.permission}
                  onChange={(e) => props.onPatch({ permissions: { [t.name]: e.target.value === "default" ? (t.risk === "safe" ? "always" : "ask") : e.target.value } })}
                >
                  <option value="default">default ({t.risk === "safe" ? "allow" : "ask"})</option>
                  <option value="always">always allow</option>
                  <option value="ask">ask every time</option>
                  <option value="never">never (disabled)</option>
                </select>
              )}
            </Row>
          ))}
        </div>

        <div className="panel">
          <h3>Appearance</h3>
          <Row label="Theme">
            <select value={s.ui.theme}
                    onChange={(e) => props.onPatch({ ui: { theme: e.target.value } })}>
              <option value="dark">Dark</option>
              <option value="light">Light</option>
              <option value="system">System</option>
            </select>
          </Row>
          <Row label="Glass effect" sub="Translucent panels with blur">
            <Toggle checked={s.ui.glass}
                    onChange={(v) => props.onPatch({ ui: { glass: v } })} />
          </Row>
        </div>
      </div>
    </div>
  );
}
