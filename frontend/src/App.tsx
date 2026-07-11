import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ChatView, ConfirmModal, ConfirmRequest, ToolChipInfo } from "./components/ChatView";
import { Page, Sidebar } from "./components/Sidebar";
import { api, Conversation, Message } from "./lib/api";
import { speak, speechSupported, stopSpeaking, VoiceEngine } from "./lib/voice";
import { ChatEvent, ChatSocket } from "./lib/ws";
import { DashboardPage } from "./pages/DashboardPage";
import { DevPage } from "./pages/DevPage";
import { MemoryPage } from "./pages/MemoryPage";
import { RegistryPage } from "./pages/RegistryPage";
import { SettingsPage } from "./pages/SettingsPage";

export default function App() {
  const [page, setPage] = useState<Page>("core");
  const [collapsed, setCollapsed] = useState(false);
  const [settings, setSettings] = useState<any>(null);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [streaming, setStreaming] = useState<string | null>(null);
  const [chips, setChips] = useState<ToolChipInfo[]>([]);
  const [agentName, setAgentName] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirm, setConfirm] = useState<ConfirmRequest | null>(null);
  const [input, setInput] = useState("");
  const [voiceState, setVoiceState] = useState<"idle" | "listening" | "waiting-wake">("idle");
  const [interim, setInterim] = useState("");
  const [ollamaUp, setOllamaUp] = useState(false);

  const socket = useMemo(() => new ChatSocket(), []);
  const activeIdRef = useRef(activeId);
  activeIdRef.current = activeId;
  const settingsRef = useRef(settings);
  settingsRef.current = settings;
  const streamBuf = useRef("");
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const refreshConversations = useCallback(
    (q = "") => api.conversations(q).then(setConversations).catch(() => {}),
    []
  );

  const send = useCallback((text: string, convId?: string | null) => {
    const content = text.trim();
    if (!content) return;
    stopSpeaking();
    const target = convId !== undefined ? convId : activeIdRef.current;
    setMessages((m) => [
      ...m,
      { id: `local-${Date.now()}`, role: "user", content, meta: {}, created_at: Date.now() / 1000 },
    ]);
    setBusy(true);
    setChips([]);
    setAgentName(null);
    streamBuf.current = "";
    setStreaming(null);
    setInput("");
    setPage("chat");
    socket.chat(target, content);
  }, [socket]);

  // ---- websocket events ----
  useEffect(() => {
    socket.onEvent = (e: ChatEvent) => {
      switch (e.type) {
        case "conversation":
          if (activeIdRef.current !== e.conversation_id) {
            setActiveId(e.conversation_id);
            refreshConversations();
          }
          break;
        case "agent":
          setAgentName(e.agent.name);
          break;
        case "token":
          streamBuf.current += e.content;
          setStreaming(streamBuf.current);
          break;
        case "tool_start":
          setChips((c) => [...c.filter((x) => !(x.name === e.name && x.status === "running")),
                           { name: e.name, status: "running" }]);
          break;
        case "tool_result": {
          const status: ToolChipInfo["status"] = e.denied ? "denied" : "done";
          setChips((c) => {
            const updated: ToolChipInfo[] = c.map((x) =>
              x.name === e.name && x.status === "running"
                ? { ...x, status, result: e.result }
                : x
            );
            if (!c.some((x) => x.name === e.name)) {
              updated.push({ name: e.name, status, result: e.result });
            }
            return updated;
          });
          break;
        }
        case "confirm_request":
          setConfirm({ id: e.id, tool: e.tool, arguments: e.arguments, risk: e.risk });
          break;
        case "done": {
          setBusy(false);
          setStreaming(null);
          setChips([]);
          setAgentName(null);
          const id = activeIdRef.current;
          if (id) api.messages(id).then(setMessages).catch(() => {});
          const st = settingsRef.current;
          if (st?.voice?.tts_enabled && e.content) {
            speak(e.content, st.voice.tts_rate, st.voice.tts_voice);
          }
          break;
        }
        case "title":
          refreshConversations();
          break;
        case "stopped":
          setBusy(false);
          setStreaming(null);
          setChips([]);
          break;
        case "error":
          setBusy(false);
          setStreaming(null);
          setChips([]);
          setMessages((m) => [
            ...m,
            { id: `err-${Date.now()}`, role: "assistant", content: `⚠️ ${e.message}`, meta: {}, created_at: Date.now() / 1000 },
          ]);
          break;
      }
    };
    socket.connect();
  }, [socket, refreshConversations]);

  // ---- initial load + status polling ----
  useEffect(() => {
    api.settings().then(setSettings).catch(() => {});
    refreshConversations();
    const poll = () => api.status().then((s) => setOllamaUp(s.ollama_up)).catch(() => setOllamaUp(false));
    poll();
    const t = setInterval(poll, 5000);
    return () => clearInterval(t);
  }, [refreshConversations]);

  // ---- voice ----
  const voice = useMemo(() => {
    if (!speechSupported) return null;
    return new VoiceEngine({
      language: "en-US",
      wakeWords: ["jarvis"],
      onTranscript: (text) => send(text),
      onInterim: setInterim,
      onWake: () => stopSpeaking(),
      onStateChange: setVoiceState,
    });
  }, [send]);

  useEffect(() => {
    if (voice && settings) {
      voice.update({
        language: settings.voice?.language ?? "en-US",
        wakeWords: settings.assistant?.wake_words ?? ["jarvis"],
      });
    }
  }, [voice, settings]);

  // ---- theme ----
  useEffect(() => {
    const theme = settings?.ui?.theme ?? "dark";
    const dark = theme === "system"
      ? window.matchMedia("(prefers-color-scheme: dark)").matches
      : theme === "dark";
    document.documentElement.dataset.theme = dark ? "dark" : "light";
  }, [settings]);

  const patchSettings = (patch: any) => {
    setSettings((s: any) => {
      const next = structuredClone(s);
      deepMerge(next, patch);
      return next;
    });
    api.updateSettings(patch).then(setSettings).catch(() => {});
  };

  const openConversation = (id: string) => {
    setActiveId(id);
    setPage("chat");
    api.messages(id).then(setMessages).catch(() => {});
  };

  const newChat = () => {
    setActiveId(null);
    setMessages([]);
    setPage("chat");
    stopSpeaking();
    inputRef.current?.focus();
  };

  const deleteConversation = (id: string) => {
    api.deleteConversation(id).then(() => {
      refreshConversations();
      if (id === activeId) newChat();
    });
  };

  const editMessage = (m: Message) => {
    if (!activeId) return;
    api.truncate(activeId, m.id).then(() => {
      api.messages(activeId).then(setMessages);
      setInput(m.content);
      inputRef.current?.focus();
    });
  };

  const regenerate = (_m: Message) => {
    if (!activeId) return;
    const lastUser = [...messages].reverse().find((x) => x.role === "user");
    if (!lastUser) return;
    api.truncate(activeId, lastUser.id).then(() => {
      setMessages((msgs) => msgs.slice(0, msgs.findIndex((x) => x.id === lastUser.id)));
      send(lastUser.content, activeId);
    });
  };

  const onComposerKey = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (!busy) send(input);
    }
  };

  const voiceEnabled = settings?.voice?.enabled !== false && speechSupported;

  return (
    <div className={`app ${settings?.ui?.glass !== false ? "glass" : ""}`}>
      <Sidebar
        conversations={conversations}
        activeId={activeId}
        page={page}
        busy={busy}
        ollamaUp={ollamaUp}
        model={settings?.ollama?.model ?? ""}
        collapsed={collapsed}
        onToggleCollapse={() => setCollapsed((c) => !c)}
        onNewChat={newChat}
        onSelect={openConversation}
        onDelete={deleteConversation}
        onSearch={(q) => refreshConversations(q)}
        onPage={setPage}
      />

      <div className="main">
        {page === "chat" && (
          <>
            <ChatView
              messages={messages}
              streaming={busy ? streaming ?? "" : null}
              chips={chips}
              agentName={agentName}
              busy={busy}
              onEdit={editMessage}
              onRegenerate={regenerate}
              onCopy={(t) => navigator.clipboard.writeText(t)}
              onSuggestion={(s) => send(s)}
              assistantName={settings?.assistant?.name ?? "Jarvis"}
            />
            <div className="composer-wrap">
              <div className="composer">
                {voiceEnabled && (
                  <button
                    className={`icon-btn ${voiceState === "listening" ? "recording" : ""}`}
                    title="Push to talk"
                    onClick={() => voiceState === "idle" ? voice?.startListening() : voice?.stop()}
                  >
                    🎤
                  </button>
                )}
                {voiceEnabled && (
                  <button
                    className={`icon-btn ${voiceState === "waiting-wake" ? "wake-on" : ""}`}
                    title={`Wake word ("${(settings?.assistant?.wake_words ?? ["jarvis"])[0]}")`}
                    onClick={() => voiceState === "waiting-wake" ? voice?.stop() : voice?.startWakeWord()}
                  >
                    👂
                  </button>
                )}
                <textarea
                  ref={inputRef}
                  rows={1}
                  placeholder={busy ? "Thinking…" : `Message ${settings?.assistant?.name ?? "Jarvis"}…`}
                  value={input}
                  onChange={(e) => {
                    setInput(e.target.value);
                    e.target.style.height = "auto";
                    e.target.style.height = Math.min(e.target.scrollHeight, 180) + "px";
                  }}
                  onKeyDown={onComposerKey}
                />
                {busy ? (
                  <button className="icon-btn" title="Stop" onClick={() => socket.stop()}>■</button>
                ) : (
                  <button className="icon-btn primary" title="Send" disabled={!input.trim()}
                          onClick={() => send(input)}>↑</button>
                )}
              </div>
              <div className="voice-hint">
                {voiceState === "waiting-wake" && !interim && `Listening for "${(settings?.assistant?.wake_words ?? ["jarvis"])[0]}"…`}
                {(voiceState === "listening" || interim) && (interim || "Listening…")}
              </div>
            </div>
          </>
        )}
        {page === "core" && (
          <DashboardPage
            busy={busy}
            listening={voiceState !== "idle"}
            assistantName={settings?.assistant?.name ?? "Jarvis"}
            onCommand={(text) => send(text)}
          />
        )}
        {page === "settings" && <SettingsPage settings={settings} onPatch={patchSettings} />}
        {page === "memory" && <MemoryPage />}
        {page === "dev" && <DevPage />}
        {page === "registry" && <RegistryPage />}
      </div>

      {confirm && (
        <ConfirmModal
          request={confirm}
          onResolve={(approved, remember) => {
            socket.confirm(confirm.id, approved, confirm.tool, remember);
            setConfirm(null);
          }}
        />
      )}
    </div>
  );
}

function deepMerge(base: any, patch: any) {
  for (const k of Object.keys(patch)) {
    if (patch[k] && typeof patch[k] === "object" && !Array.isArray(patch[k]) && base[k]) {
      deepMerge(base[k], patch[k]);
    } else {
      base[k] = patch[k];
    }
  }
}
