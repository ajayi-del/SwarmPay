"use client";

/**
 * AudioPlayer — Reusable base64 audio playback button.
 * Used for REGIS probe responses and sovereignty events.
 * Returns null when no audio is available (graceful degradation).
 */

interface AudioPlayerProps {
  audioB64: string | null | undefined;
  agentName: string;
  label?: string;
}

export default function AudioPlayer({ audioB64, agentName, label }: AudioPlayerProps) {
  if (!audioB64) return null;

  const play = () => {
    try {
      const src = `data:audio/mpeg;base64,${audioB64}`;
      new Audio(src).play().catch(() => {});
    } catch {
      // ignore — audio not critical
    }
  };

  return (
    <button
      onClick={play}
      title={`Play ${agentName} voice`}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 4,
        padding: "2px 8px",
        borderRadius: 4,
        border: "1px solid rgba(245,158,11,0.3)",
        background: "rgba(245,158,11,0.08)",
        color: "#F59E0B",
        fontSize: 10,
        fontFamily: "monospace",
        letterSpacing: "0.06em",
        cursor: "pointer",
        flexShrink: 0,
      }}
    >
      ▶ {label ?? `Hear ${agentName}`}
    </button>
  );
}
