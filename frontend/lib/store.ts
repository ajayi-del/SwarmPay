import { create } from "zustand";

interface SwarmStore {
  taskId: string | null;
  phase: "idle" | "submitted" | "decomposed" | "running" | "done";
  setTaskId: (id: string) => void;
  setPhase: (p: SwarmStore["phase"]) => void;
  reset: () => void;
}

export const useSwarmStore = create<SwarmStore>((set) => ({
  taskId: null,
  phase: "idle",
  setTaskId: (id) => set({ taskId: id }),
  setPhase: (phase) => set({ phase }),
  reset: () => set({ taskId: null, phase: "idle" }),
}));
