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

  useEffect(() => {
    setSupported(
      typeof window !== "undefined" &&
      ("SpeechRecognition" in window || "webkitSpeechRecognition" in window)
    );
  }, []);

  const start = useCallback(() => {
    if (!supported) {
      setError("Speech recognition not supported in this browser. Try Chrome.");
      setState("error");
      return;
    }

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    const recognition: AnyRecognition = new SR();

    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.lang = "en-US";
    recognition.maxAlternatives = 1;

    recognition.onstart = () => {
      setState("listening");
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
        setState("processing");
        onResult(current);
        setTimeout(() => setState("idle"), 600);
      }
    };

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    recognition.onerror = (event: any) => {
      const msg = event.error === "not-allowed"
        ? "Microphone access denied. Allow it in browser settings."
        : `Speech error: ${event.error}`;
      setError(msg);
      setState("error");
      setTimeout(() => setState("idle"), 3000);
    };

    recognition.onend = () => {
      if (state === "listening") setState("idle");
    };

    recognition.start();
    recognitionRef.current = recognition;
  }, [supported, onResult, state]);

  const stop = useCallback(() => {
    recognitionRef.current?.stop();
    setState("idle");
  }, []);

  return { state, transcript, start, stop, supported, error };
}
