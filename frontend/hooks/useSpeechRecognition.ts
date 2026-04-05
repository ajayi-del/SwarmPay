"use client";

import { useState, useRef, useCallback, useEffect } from "react";

export type SpeechState = "idle" | "listening" | "processing" | "error";

interface UseSpeechRecognitionReturn {
  state: SpeechState;
  transcript: string;
  start: () => void;
  stop: () => void;
  supported: boolean;
  error: string | null;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type AnyRecognition = any;

export function useSpeechRecognition(
  onResult: (text: string) => void
): UseSpeechRecognitionReturn {
  const [state, setState] = useState<SpeechState>("idle");
  const [transcript, setTranscript] = useState("");
  const [error, setError] = useState<string | null>(null);
  const recognitionRef = useRef<AnyRecognition | null>(null);
  const [supported, setSupported] = useState(false);

  // Track state in a ref so callbacks always read current value (avoids stale closure)
  const stateRef = useRef<SpeechState>("idle");
  const setStateSync = useCallback((s: SpeechState) => {
    stateRef.current = s;
    setState(s);
  }, []);

  useEffect(() => {
    setSupported(
      typeof window !== "undefined" &&
      ("SpeechRecognition" in window || "webkitSpeechRecognition" in window)
    );
  }, []);

  const start = useCallback(() => {
    if (!supported) {
      setError("Speech recognition not supported. Try Chrome on HTTPS.");
      setStateSync("error");
      return;
    }

    // Stop any existing session first
    if (recognitionRef.current) {
      try { recognitionRef.current.stop(); } catch (_) { /* ignore */ }
    }

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    const recognition: AnyRecognition = new SR();

    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.lang = "en-US";
    recognition.maxAlternatives = 1;

    recognition.onstart = () => {
      setStateSync("listening");
      setError(null);
      setTranscript("");
    };

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    recognition.onresult = (event: any) => {
      const current = Array.from(event.results as ArrayLike<{ [idx: number]: { transcript: string }; isFinal: boolean }>)
        .map((r) => r[0].transcript)
        .join("");
      setTranscript(current);

      const results = event.results as ArrayLike<{ isFinal: boolean }>;
      if ((results as { [idx: number]: { isFinal: boolean }; length: number })[results.length - 1]?.isFinal) {
        setStateSync("processing");
        onResult(current);
        setTimeout(() => setStateSync("idle"), 600);
      }
    };

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    recognition.onerror = (event: any) => {
      let msg: string;
      if (event.error === "not-allowed") {
        msg = "Microphone access denied. Allow it in browser settings.";
      } else if (event.error === "network") {
        msg = "Network error. Speech recognition requires internet access.";
      } else if (event.error === "no-speech") {
        msg = "No speech detected. Try again.";
      } else {
        msg = `Speech error: ${event.error}`;
      }
      setError(msg);
      setStateSync("error");
      setTimeout(() => setStateSync("idle"), 3000);
    };

    // Use stateRef (not state) to avoid stale closure
    recognition.onend = () => {
      if (stateRef.current === "listening") {
        setStateSync("idle");
      }
    };

    recognition.start();
    recognitionRef.current = recognition;
  }, [supported, onResult, setStateSync]);

  const stop = useCallback(() => {
    if (recognitionRef.current) {
      try { recognitionRef.current.stop(); } catch (_) { /* ignore */ }
    }
    setStateSync("idle");
  }, [setStateSync]);

  return { state, transcript, start, stop, supported, error };
}
