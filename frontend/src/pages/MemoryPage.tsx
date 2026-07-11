import { useEffect, useState } from "react";
import { api } from "../lib/api";

export function MemoryPage() {
  const [memories, setMemories] = useState<any[]>([]);
  const [draft, setDraft] = useState("");
  const [editing, setEditing] = useState<string | null>(null);
  const [editText, setEditText] = useState("");

  const refresh = () => api.memories().then(setMemories).catch(() => {});
  useEffect(() => { refresh(); }, []);

  return (
    <div className="page">
      <div className="page-inner">
        <h1>Memory</h1>
        <div className="panel">
          <h3>Add a memory</h3>
          <div style={{ display: "flex", gap: 8 }}>
            <input type="text" className="search" style={{ flex: 1 }}
                   placeholder="e.g. I prefer dark roast coffee"
                   value={draft} onChange={(e) => setDraft(e.target.value)}
                   onKeyDown={(e) => {
                     if (e.key === "Enter" && draft.trim()) {
                       api.addMemory(draft.trim()).then(() => { setDraft(""); refresh(); });
                     }
                   }} />
            <button className="btn primary"
                    onClick={() => draft.trim() && api.addMemory(draft.trim()).then(() => { setDraft(""); refresh(); })}>
              Save
            </button>
          </div>
        </div>
        <div className="panel">
          <h3>{memories.length} memories</h3>
          {memories.length === 0 && (
            <div className="sub">Nothing yet. Say “remember that …” in chat, or add one above.</div>
          )}
          {memories.map((m) => (
            <div className="row" key={m.id}>
              {editing === m.id ? (
                <input type="text" style={{ flex: 1 }} className="search" value={editText}
                       autoFocus
                       onChange={(e) => setEditText(e.target.value)}
                       onKeyDown={(e) => {
                         if (e.key === "Enter") {
                           api.editMemory(m.id, editText).then(() => { setEditing(null); refresh(); });
                         }
                         if (e.key === "Escape") setEditing(null);
                       }} />
              ) : (
                <div>
                  <div className="label">{m.content}</div>
                  <div className="sub">{m.category} · {new Date(m.created_at * 1000).toLocaleDateString()}</div>
                </div>
              )}
              <div style={{ display: "flex", gap: 6 }}>
                <button className="btn" onClick={() => { setEditing(m.id); setEditText(m.content); }}>Edit</button>
                <button className="btn danger" onClick={() => api.deleteMemory(m.id).then(refresh)}>Delete</button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
