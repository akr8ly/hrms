import { useEffect, useMemo, useRef, useState } from "react";

import { API_BASE_URL } from "../api";

const WELCOME_MESSAGE = {
  id: "welcome",
  role: "assistant",
  text: "Hello! I’m your HR assistant. Ask me about leave, payroll, benefits, conduct, security, remote work, or travel policies.",
};

const EMPLOYEE_PROMPTS = [
  "What is the casual leave policy?",
  "Explain the employee benefits policies",
  "What are the remote work rules?",
  "How are travel expenses reimbursed?",
];

const ADMIN_PROMPTS = [
  "Show division-wise employee headcount",
  ...EMPLOYEE_PROMPTS.slice(0, 3),
];

function ChatIcon({ close = false }) {
  return close ? (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M18 6 6 18M6 6l12 12" />
    </svg>
  ) : (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M21 15a2 2 0 0 1-2 2H8l-5 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
      <path d="M8 9h8M8 13h5" />
    </svg>
  );
}

async function readError(response, fallback) {
  try {
    const data = await response.json();
    if (Array.isArray(data.detail)) {
      return data.detail.map((item) => item.msg).join(", ");
    }
    return data.detail || fallback;
  } catch {
    return fallback;
  }
}

function parseEventBlock(block) {
  let event = "message";
  const dataLines = [];
  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
  }
  if (!dataLines.length) return null;
  return { event, data: JSON.parse(dataLines.join("\n")) };
}

function HRChatbotWidget({ token, role }) {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState([WELCOME_MESSAGE]);
  const [question, setQuestion] = useState("");
  const [sessionId, setSessionId] = useState("");
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("Ready");
  const [notice, setNotice] = useState("");
  const messagesRef = useRef(null);
  const inputRef = useRef(null);
  const nextId = useRef(1);
  const prompts = useMemo(
    () => (role === "admin" ? ADMIN_PROMPTS : EMPLOYEE_PROMPTS),
    [role],
  );

  useEffect(() => {
    if (open) inputRef.current?.focus();
  }, [open]);

  useEffect(() => {
    const node = messagesRef.current;
    if (node) node.scrollTop = node.scrollHeight;
  }, [messages, busy]);

  useEffect(() => {
    function closeOnEscape(event) {
      if (event.key === "Escape") setOpen(false);
    }
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, []);

  async function createSession() {
    const response = await fetch(`${API_BASE_URL}/chatbot/sessions`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!response.ok) {
      throw new Error(await readError(response, "Could not start an HR assistant session."));
    }
    const data = await response.json();
    setSessionId(data.session_id);
    return data.session_id;
  }

  function updateAssistant(id, updater) {
    setMessages((current) => current.map((message) => (
      message.id === id ? updater(message) : message
    )));
  }

  async function streamAnswer(text, activeSession, assistantId, canRetry = true) {
    const response = await fetch(`${API_BASE_URL}/chatbot/message/stream`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ session_id: activeSession, question: text }),
    });

    if (response.status === 404 && canRetry) {
      const replacement = await createSession();
      return streamAnswer(text, replacement, assistantId, false);
    }
    if (!response.ok || !response.body) {
      throw new Error(await readError(response, "The HR assistant could not answer right now."));
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let answer = "";

    while (true) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value || new Uint8Array(), { stream: !done }).replace(/\r\n/g, "\n");
      const blocks = buffer.split("\n\n");
      buffer = blocks.pop() || "";

      for (const block of blocks) {
        if (!block.trim()) continue;
        const parsed = parseEventBlock(block);
        if (!parsed) continue;
        if (parsed.event === "status") {
          setStatus(parsed.data.stage === "processing" ? "Reviewing HR resources" : "Checking your request");
        } else if (parsed.event === "token") {
          answer += parsed.data.text || "";
          updateAssistant(assistantId, (message) => ({ ...message, text: answer }));
        } else if (parsed.event === "metadata") {
          updateAssistant(assistantId, (message) => ({
            ...message,
            sources: parsed.data.sources || [],
            tools: parsed.data.tools_used || [],
          }));
        } else if (parsed.event === "error") {
          throw new Error(parsed.data.detail || "The HR assistant could not complete the request.");
        }
      }
      if (done) break;
    }
  }

  async function sendQuestion(text) {
    const cleanQuestion = text.trim();
    if (!cleanQuestion || busy) return;

    const userId = `user-${nextId.current++}`;
    const assistantId = `assistant-${nextId.current++}`;
    setQuestion("");
    setNotice("");
    setBusy(true);
    setStatus("Starting secure session");
    setMessages((current) => [
      ...current,
      { id: userId, role: "user", text: cleanQuestion },
      { id: assistantId, role: "assistant", text: "" },
    ]);

    try {
      const activeSession = sessionId || await createSession();
      await streamAnswer(cleanQuestion, activeSession, assistantId);
      setStatus("Ready");
    } catch (error) {
      updateAssistant(assistantId, (message) => ({
        ...message,
        text: error.message || "Unable to reach the HR assistant.",
        failed: true,
      }));
      setNotice("Please check that the HRMS API and Ollama are running, then try again.");
      setStatus("Unavailable");
    } finally {
      setBusy(false);
    }
  }

  function submit(event) {
    event.preventDefault();
    sendQuestion(question);
  }

  return (
    <div className="hr-chat-widget">
      <section
        className={`chat-drawer ${open ? "open" : ""}`}
        aria-label="HR policy assistant"
        aria-hidden={!open}
      >
        <header className="chat-header">
          <div className="chat-agent-mark">HR</div>
          <div className="chat-header-copy">
            <strong>HR Policy Helpdesk</strong>
            <span><i className={status === "Unavailable" ? "offline" : ""} />{status}</span>
          </div>
          <button className="chat-icon-button" type="button" onClick={() => setOpen(false)} aria-label="Close HR assistant">
            <ChatIcon close />
          </button>
        </header>

        <div className="chat-context-bar">
          <span>Secure workspace</span>
          <span className="chat-role-pill">{role}</span>
        </div>

        <div className="chat-messages" ref={messagesRef} aria-live="polite">
          {messages.map((message) => (
            <article key={message.id} className={`chat-message ${message.role} ${message.failed ? "failed" : ""}`}>
              {message.role === "assistant" && <span className="chat-message-label">HR Assistant</span>}
              <p>{message.text || <span className="chat-typing"><i /><i /><i /></span>}</p>
              {!!message.sources?.length && (
                <div className="chat-sources">
                  <strong>Sources</strong>
                  {message.sources.map((source) => (
                    <span key={source.policy_id}>{source.policy_id} · {source.title}</span>
                  ))}
                </div>
              )}
              {!!message.tools?.length && role === "admin" && (
                <small className="chat-tool-note">Used: {message.tools.join(", ")}</small>
              )}
            </article>
          ))}

          {messages.length === 1 && (
            <div className="chat-suggestions">
              <span>Popular questions</span>
              {prompts.map((prompt) => (
                <button key={prompt} type="button" disabled={busy} onClick={() => sendQuestion(prompt)}>{prompt}</button>
              ))}
            </div>
          )}
        </div>

        {notice && <p className="chat-notice">{notice}</p>}
        <form className="chat-composer" onSubmit={submit}>
          <label htmlFor="hr-chat-input">Ask about HR policies</label>
          <div>
            <textarea
              id="hr-chat-input"
              ref={inputRef}
              rows="1"
              maxLength="1000"
              value={question}
              disabled={busy}
              placeholder="Type your question…"
              onChange={(event) => setQuestion(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  submit(event);
                }
              }}
            />
            <button type="submit" disabled={busy || !question.trim()} aria-label="Send question">
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m22 2-7 20-4-9-9-4Z" /><path d="M22 2 11 13" /></svg>
            </button>
          </div>
          <small>Answers use approved HR policies. Verify critical decisions with HR.</small>
        </form>
      </section>

      <button
        className={`chat-toggle ${open ? "open" : ""}`}
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        aria-label={open ? "Close HR assistant" : "Open HR assistant"}
      >
        <span className="chat-toggle-icon"><ChatIcon close={open} /></span>
        <span>{open ? "Close" : "HR Assistant"}</span>
      </button>
    </div>
  );
}

export default HRChatbotWidget;
