"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { sendChatMessage, getChatStatus, ChatMessage } from "../lib/api";

// Minimal shape for the Web Speech API's SpeechRecognition -- not in default TS lib.
interface SpeechRecognitionResultLike {
  isFinal: boolean;
  0: { transcript: string };
}
interface SpeechRecognitionEventLike {
  resultIndex: number;
  results: ArrayLike<SpeechRecognitionResultLike>;
}
interface SpeechRecognitionLike extends EventTarget {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  start: () => void;
  stop: () => void;
  onresult: ((e: SpeechRecognitionEventLike) => void) | null;
  onend: (() => void) | null;
  onerror: (() => void) | null;
}

function getSpeechRecognitionCtor(): (new () => SpeechRecognitionLike) | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as {
    SpeechRecognition?: new () => SpeechRecognitionLike;
    webkitSpeechRecognition?: new () => SpeechRecognitionLike;
  };
  return w.SpeechRecognition || w.webkitSpeechRecognition || null;
}

function speechSupported() {
  return typeof window !== "undefined" && "speechSynthesis" in window;
}

export default function ChatWidget() {
  const [open, setOpen] = useState(false);
  const [checked, setChecked] = useState(false);
  const [available, setAvailable] = useState(true);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [unavailableMsg, setUnavailableMsg] = useState<string | null>(null);

  const [listening, setListening] = useState(false);
  const [voiceReplies, setVoiceReplies] = useState(false);
  const [micSupported, setMicSupported] = useState(false);

  const scrollRef = useRef<HTMLDivElement>(null);
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);

  useEffect(() => {
    setMicSupported(!!getSpeechRecognitionCtor());
  }, []);

  useEffect(() => {
    if (open && !checked) {
      getChatStatus().then((s) => {
        setAvailable(s.available);
        setChecked(true);
      });
    }
  }, [open, checked]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, loading]);

  // Stop mic + any speech playback when the widget is closed.
  useEffect(() => {
    if (!open) {
      recognitionRef.current?.stop();
      setListening(false);
      if (speechSupported()) window.speechSynthesis.cancel();
    }
  }, [open]);

  const speak = useCallback((text: string) => {
    if (!speechSupported()) return;
    window.speechSynthesis.cancel();
    const clean = text.replace(/\n{2,}---[\s\S]*$/, "").trim(); // skip reading the safety footer aloud
    const utterance = new SpeechSynthesisUtterance(clean);
    utterance.rate = 1.0;
    window.speechSynthesis.speak(utterance);
  }, []);

  const handleSend = useCallback(
    async (overrideText?: string) => {
      const text = (overrideText ?? input).trim();
      if (!text || loading) return;
      setInput("");
      const nextHistory = [...messages, { role: "user" as const, content: text }];
      setMessages(nextHistory);
      setLoading(true);
      setUnavailableMsg(null);
      try {
        const res = await sendChatMessage(text, messages);
        if (res.available && res.reply) {
          setMessages((m) => [...m, { role: "assistant", content: res.reply! }]);
          if (voiceReplies) speak(res.reply);
        } else {
          setUnavailableMsg(
            res.error || "The AI assistant is currently unavailable. Core CKD prediction is unaffected."
          );
        }
      } catch {
        setUnavailableMsg("The AI assistant is currently unavailable. Core CKD prediction is unaffected.");
      } finally {
        setLoading(false);
      }
    },
    [input, loading, messages, voiceReplies, speak]
  );

  function toggleListening() {
    const Ctor = getSpeechRecognitionCtor();
    if (!Ctor) return;

    if (listening) {
      recognitionRef.current?.stop();
      setListening(false);
      return;
    }

    const recognition = new Ctor();
    recognition.lang = "en-US";
    recognition.continuous = false;
    recognition.interimResults = true;

    recognition.onresult = (e: SpeechRecognitionEventLike) => {
      let finalTranscript = "";
      let interimTranscript = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const r = e.results[i];
        if (r.isFinal) finalTranscript += r[0].transcript;
        else interimTranscript += r[0].transcript;
      }
      if (finalTranscript) {
        setInput("");
        handleSend(finalTranscript.trim());
      } else {
        setInput(interimTranscript);
      }
    };
    recognition.onerror = () => setListening(false);
    recognition.onend = () => setListening(false);

    recognitionRef.current = recognition;
    setListening(true);
    recognition.start();
  }

  return (
    <div className="fixed bottom-5 right-5 z-50">
      {open && (
        <div className="mb-3 w-80 sm:w-96 h-[28rem] bg-[var(--surface)] border border-[var(--line)] rounded-xl shadow-xl flex flex-col overflow-hidden">
          <div className="px-4 py-3 border-b border-[var(--line)] bg-[var(--primary)] text-white flex items-center justify-between gap-2">
            <div className="min-w-0">
              <div className="font-[family-name:var(--font-display)] font-semibold text-sm">
                Kidney Health Assistant
              </div>
              <div className="text-[10px] opacity-80">Educational only — not a doctor</div>
            </div>
            <div className="flex items-center gap-1 shrink-0">
              {speechSupported() && (
                <button
                  onClick={() => setVoiceReplies((v) => !v)}
                  title={voiceReplies ? "Turn off spoken replies" : "Read replies aloud"}
                  aria-pressed={voiceReplies}
                  className={`w-7 h-7 rounded-full flex items-center justify-center text-sm transition-colors ${
                    voiceReplies ? "bg-white/25" : "hover:bg-white/15"
                  }`}
                >
                  {voiceReplies ? "🔊" : "🔈"}
                </button>
              )}
              <button onClick={() => setOpen(false)} className="text-white/80 hover:text-white text-lg leading-none px-1">
                ×
              </button>
            </div>
          </div>

          <div ref={scrollRef} className="flex-1 overflow-y-auto p-3 space-y-3">
            {messages.length === 0 && !unavailableMsg && (
              <p className="text-xs text-[var(--ink-soft)]">
                Ask about your screening result, lab values (like creatinine or GFR), or general CKD education.
                {micSupported && " Tap the mic to speak your question."}
              </p>
            )}
            {messages.map((m, i) => (
              <div
                key={i}
                className={`group text-sm rounded-lg px-3 py-2 max-w-[85%] whitespace-pre-wrap flex items-start gap-2 ${
                  m.role === "user"
                    ? "bg-[var(--primary)] text-white ml-auto"
                    : "bg-[var(--bg)] border border-[var(--line)]"
                }`}
              >
                <span className="flex-1">{m.content}</span>
                {m.role === "assistant" && speechSupported() && (
                  <button
                    onClick={() => speak(m.content)}
                    title="Read this reply aloud"
                    className="text-xs opacity-40 hover:opacity-100 shrink-0 leading-none mt-0.5"
                  >
                    🔊
                  </button>
                )}
              </div>
            ))}
            {loading && <div className="text-xs text-[var(--ink-soft)]">Thinking…</div>}
            {unavailableMsg && (
              <div className="text-xs text-[var(--risk-medium)] bg-[var(--risk-medium)]/8 border border-[var(--risk-medium)]/30 rounded-lg p-3">
                {unavailableMsg}
              </div>
            )}
          </div>

          <div className="p-3 border-t border-[var(--line)] flex gap-2">
            {micSupported && (
              <button
                type="button"
                onClick={toggleListening}
                title={listening ? "Stop listening" : "Speak your question"}
                aria-pressed={listening}
                className={`shrink-0 w-9 h-9 rounded-lg border flex items-center justify-center text-sm transition-colors ${
                  listening
                    ? "bg-[var(--risk-high)] border-[var(--risk-high)] text-white animate-pulse"
                    : "border-[var(--line)] hover:border-[var(--primary)]"
                }`}
              >
                🎙️
              </button>
            )}
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSend()}
              placeholder={listening ? "Listening…" : "Ask a question…"}
              className="flex-1 text-sm border border-[var(--line)] rounded-lg px-3 py-2 min-w-0"
            />
            <button
              onClick={() => handleSend()}
              disabled={loading}
              className="text-sm font-medium px-3 py-2 rounded-lg bg-[var(--primary)] text-white disabled:opacity-60 shrink-0"
            >
              Send
            </button>
          </div>
        </div>
      )}

      <button
        onClick={() => setOpen((v) => !v)}
        className="w-14 h-14 rounded-full bg-[var(--primary)] text-white shadow-lg flex items-center justify-center text-xl hover:bg-[var(--primary-dark)] transition-colors"
        aria-label="Open kidney health assistant"
      >
        {open ? "×" : "💬"}
      </button>
    </div>
  );
}
