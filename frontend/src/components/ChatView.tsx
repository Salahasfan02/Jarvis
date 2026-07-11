import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import rehypeHighlight from "rehype-highlight";
import remarkGfm from "remark-gfm";
import { Message } from "../lib/api";

export interface ToolChipInfo {
  name: string;
  status: "running" | "done" | "denied";
  result?: string;
}

export interface ConfirmRequest {
  id: string;
  tool: string;
  arguments: any;
  risk: string;
}

function Bubble({ content }: { content: string }) {
  return (
    <div className="bubble">
      <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]}>
        {content}
      </ReactMarkdown>
    </div>
  );
}

export function ChatView(props: {
  messages: Message[];
  streaming: string | null;          // partial assistant text while generating
  chips: ToolChipInfo[];             // tool activity for the in-flight turn
  agentName: string | null;
  busy: boolean;
  onEdit: (msg: Message) => void;
  onRegenerate: (msg: Message) => void;
  onCopy: (text: string) => void;
  onSuggestion: (text: string) => void;
  assistantName: string;
}) {
  const endRef = useRef<HTMLDivElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const [pinned, setPinned] = useState(true);

  useEffect(() => {
    if (pinned) endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [props.messages.length, props.streaming, props.chips.length, pinned]);

  const onScroll = () => {
    const el = scrollRef.current;
    if (el) setPinned(el.scrollHeight - el.scrollTop - el.clientHeight < 120);
  };

  if (props.messages.length === 0 && !props.streaming && !props.busy) {
    return (
      <div className="empty-state">
        <div className="orb" />
        <h2>How can I help, sir?</h2>
        <div>Ask anything, or try one of these</div>
        <div className="suggestions">
          {[
            "What's on my screen right now?",
            "Search the web for today's AI news",
            "Open Safari",
            "Organize the files on my Desktop",
            "Remember that I prefer TypeScript",
            "Draft an email to my professor",
          ].map((s) => (
            <button key={s} onClick={() => props.onSuggestion(s)}>{s}</button>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="chat-scroll" ref={scrollRef} onScroll={onScroll}>
      <div className="chat-inner">
        {props.messages.map((m, i) => (
          <div key={m.id} className={`msg ${m.role}`}>
            {m.meta?.tools?.map((t, j) => (
              <span key={j} className="chip">🛠 {t.name}</span>
            ))}
            <Bubble content={m.content} />
            <div className="msg-meta msg-actions">
              {m.meta?.agent && m.role === "assistant" && <span>{m.meta.agent}</span>}
              <button onClick={() => props.onCopy(m.content)}>copy</button>
              {m.role === "user" && (
                <button onClick={() => props.onEdit(m)}>edit</button>
              )}
              {m.role === "assistant" && i === props.messages.length - 1 && !props.busy && (
                <button onClick={() => props.onRegenerate(m)}>regenerate</button>
              )}
            </div>
          </div>
        ))}

        {(props.streaming !== null || props.chips.length > 0) && (
          <div className="msg assistant">
            {props.agentName && <div className="msg-meta">{props.agentName}</div>}
            {props.chips.map((c, i) => (
              <span key={i} className={`chip ${c.status === "denied" ? "denied" : ""}`}>
                {c.status === "running" ? <span className="spinner" /> : c.status === "denied" ? "⛔" : "✓"}
                {c.name}
              </span>
            ))}
            {props.streaming ? (
              <Bubble content={props.streaming} />
            ) : (
              <div className="bubble"><span className="spinner" style={{ display: "inline-block", width: 12, height: 12, borderRadius: "50%", border: "2px solid var(--accent-soft)", borderTopColor: "var(--accent)", animation: "spin 0.8s linear infinite" }} /></div>
            )}
          </div>
        )}
        <div ref={endRef} />
      </div>
    </div>
  );
}

export function ConfirmModal(props: {
  request: ConfirmRequest;
  onResolve: (approved: boolean, remember: boolean) => void;
}) {
  const [remember, setRemember] = useState(false);
  const { request } = props;
  return (
    <div className="modal-backdrop">
      <div className="modal">
        <h3>
          Permission needed
          <span className={`risk ${request.risk}`}>{request.risk}</span>
        </h3>
        <div style={{ fontSize: 14 }}>
          {props.request.tool === "run_command" || request.risk === "dangerous"
            ? "Jarvis wants to run a potentially destructive action:"
            : "Jarvis wants to use a tool that affects your system:"}
        </div>
        <pre>{request.tool}({JSON.stringify(request.arguments, null, 2)})</pre>
        <div className="actions">
          {request.risk !== "dangerous" && (
            <label className="remember">
              <input type="checkbox" checked={remember}
                     onChange={(e) => setRemember(e.target.checked)} />
              always allow {request.tool}
            </label>
          )}
          <button className="btn" onClick={() => props.onResolve(false, false)}>Deny</button>
          <button className="btn primary" onClick={() => props.onResolve(true, remember)}>Allow</button>
        </div>
      </div>
    </div>
  );
}
