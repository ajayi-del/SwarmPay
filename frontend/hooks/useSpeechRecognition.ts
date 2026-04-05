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
  onResult: (text: string) => void,       // called with FINAL transcript
  onInterim?: (text: string) => void,     // optional: called with live partial text
): UseSpeechRecognitionReturn {
  const [state, setState] = useState<SpeechState>("idle");
  const [transcript, setTranscript] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [supported, setSupported] = useState(false);
  const recognitionRef = useRef<AnyRecognition | null>(null);

  const stateRef = useRef<SpeechState>("idle");
  const setStateSync = useCallback((s: SpeechState) => {
    stateRef.current = s;
    setState(s);
  }, []);

  useEffect(() => {
    setSupported(
      typeof window !== "undefined" &&
        ("SpeechRecognition" in window || "webkitSpeechRecognition" in window),
    );
  }, []);

  const start = useCallback(() => {
    if (!supported) {
      setError("Speech recognition not supported. Use Chrome on localhost or HTTPS.");
      setStateSync("error");
      return;
    }

    if (recognitionRef.current) {
      try { recognitionRef.current.abort(); } catch (_) { /* ignore */ }
    }

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    const recognition: AnyRecognition = new SR();

    recognition.continuous      = true;    // keep listening until stop() is called
    recognition.interimResults  = true;
    recognition.lang            = "en-US";
    recognition.maxAlternatives = 1;

    recognition.onstart = () => {
      setStateSync("listening");
      setError(null);
      setTranscript("");
    };

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    recognition.onresult = (event: any) => {
      let interim = "";
      let final   = "";

      for (let i = event.resultIndex; i < event.results.length; i++) {
        const t = event.results[i][0].transcript;
        if (event.results[i].isFinal) {
          final += t;
        } else {
          interim += t;
        }
      }

      // Show live text in textarea as user speaks
      if (interim && onInterim) onInterim(interim);

      if (final) {
        setTranscript(final);
        setStateSync("processing");
        onResult(final);
        setTimeout(() => setStateSync("idle"), 600);
      }
    };

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    recognition.onerror = (event: any) => {
      let msg: string;
      switch (event.error) {
        case "not-allowed":
          msg = "Microphone access denied. Allow it in your browser settings.";
          break;
        case "network":
          msg = "Network error — speech recognition needs internet access.";
          break;
        case "no-speech":
          msg = "No speech detected. Try speaking again.";
          break;
        case "audio-capture":
          msg = "No microphone found or it is in use by another app.";
          break;
        default:
          msg = `Speech error: ${event.error}`;
      }
      setError(msg);
      setStateSync("error");
      setTimeout(() => { if (stateRef.current === "error") setStateSync("idle"); }, 4000);
    };

    recognition.onend = () => {
      if (stateRef.current === "listening") setStateSync("idle");
    };

    try {
      recognition.start();
      recognitionRef.current = recognition;
    } catch (err) {
      setError(`Could not start microphone: ${err}`);
      setStateSync("error");
    }
  }, [supported, onResult, onInterim, setStateSync]);

  const stop = useCallback(() => {
    if (recognitionRef.current) {
      try { recognitionRef.current.stop(); } catch (_) { /* ignore */ }
    }
    if (stateRef.current === "listening") setStateSync("idle");
  }, [setStateSync]);

  return { state, transcript, start, stop, supported, error };
}
