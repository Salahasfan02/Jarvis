import { useEffect, useRef, useState } from "react";
import { statsApi, SystemStats } from "../lib/api";
import { voiceBus } from "../lib/voice";
import { Core, CoreMode } from "../components/Core";

function Meter({ label, value, detail }: { label: string; value: number; detail?: string }) {
  return (
    <div className="meter">
      <div className="meter-head">
        <span>{label}</span>
        <span>{detail ?? `${Math.round(value)}%`}</span>
      </div>
      <div className="progress-bar"><div style={{ width: `${Math.min(100, value)}%` }} /></div>
    </div>
  );
}

export function DashboardPage(props: {
  busy: boolean;
  listening: boolean;
  assistantName: string;
  onCommand: (text: string) => void;
}) {
  const [stats, setStats] = useState<SystemStats | null>(null);
  const [ctx, setCtx] = useState<any>(null);
  const [speaking, setSpeaking] = useState(false);
  const [command, setCommand] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const onSpeak = (e: Event) => setSpeaking((e as CustomEvent).detail);
    voiceBus.addEventListener("speaking", onSpeak);
    return () => voiceBus.removeEventListener("speaking", onSpeak);
  }, []);

  useEffect(() => {
    let alive = true;
    const poll = async () => {
      try {
        const s = await statsApi.stats();
        if (alive) setStats(s);
      } catch { if (alive) setStats(null); }
      try {
        const c = await statsApi.context();
        if (alive) setCtx(c);
      } catch { /* context off */ }
    };
    poll();
    const t = setInterval(poll, 4000);
    return () => { alive = false; clearInterval(t); };
  }, []);

  const mode: CoreMode = speaking ? "speaking" : props.busy ? "thinking"
    : props.listening ? "listening" : "idle";
  const statusText = { speaking: "SPEAKING", thinking: "PROCESSING",
    listening: "LISTENING", idle: "ONLINE" }[mode];

  return (
    <div className="dashboard">
      <div className="dash-center">
        <Core mode={mode} />
        <div className={`core-status ${mode}`}>{statusText}</div>
        <div className="core-sub">
          {stats?.ollama_up
            ? `${stats.active_model} · local · secure`
            : "AI engine offline — start Ollama"}
        </div>
        <form
          className="command-bar"
          onSubmit={(e) => {
            e.preventDefault();
            if (command.trim()) {
              props.onCommand(command.trim());
              setCommand("");
            }
          }}
        >
          <input
            ref={inputRef}
            placeholder={`Give ${props.assistantName} a command…`}
            value={command}
            onChange={(e) => setCommand(e.target.value)}
          />
        </form>
      </div>

      <div className="dash-right">
        <div className="hud-panel">
          <h4>System</h4>
          {stats ? (
            <>
              <Meter label="CPU" value={stats.cpu_percent} />
              <Meter label="Memory" value={stats.memory_percent}
                     detail={`${stats.memory_used_gb} / ${stats.memory_total_gb} GB`} />
              {stats.loaded_models.map((m) => (
                <Meter key={m.name} label={`Model · ${m.name}`} value={m.gpu_percent}
                       detail={`${m.size_gb} GB · ${m.gpu_percent}% GPU`} />
              ))}
              {stats.loaded_models.length === 0 && (
                <div className="hud-dim">no model loaded (loads on first message)</div>
              )}
            </>
          ) : (
            <div className="hud-dim">backend offline</div>
          )}
        </div>

        <div className="hud-panel">
          <h4>Tool activity</h4>
          {stats?.running_tools.length ? (
            stats.running_tools.map((t) => (
              <div key={t} className="hud-row"><span className="spinner" /> {t}</div>
            ))
          ) : (
            <div className="hud-dim">idle</div>
          )}
          {(stats?.recent_activity ?? []).slice(0, 5).map((e, i) => (
            <div key={i} className="hud-row dim">
              {e.event.replace(/_/g, " ")} {e.tool ?? ""}
            </div>
          ))}
        </div>

        <div className="hud-panel">
          <h4>Context</h4>
          {ctx?.enabled ? (
            <>
              {ctx.degraded && <div className="hud-dim">⚠ {ctx.degraded}</div>}
              <div className="hud-row">App: {ctx.frontmost_app || "—"}</div>
              <div className="hud-row">Browser: {ctx.browser} · {ctx.tabs?.length ?? 0} tabs</div>
              {ctx.music?.running && ctx.music.track && (
                <div className="hud-row">
                  ♪ {ctx.music.state}: {ctx.music.track} — {ctx.music.artist}
                </div>
              )}
              {(ctx.tabs ?? []).slice(0, 4).map((t: any) => (
                <div key={t.index} className="hud-row dim">{t.title?.slice(0, 38)}</div>
              ))}
            </>
          ) : (
            <div className="hud-dim">context awareness off</div>
          )}
        </div>
      </div>
    </div>
  );
}
