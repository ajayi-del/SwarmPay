import { create } from "zustand";

export type AppMode = "kingdom" | "office";

interface ModeStore {
  mode: AppMode;
  toggle: () => void;
}

export const useModeStore = create<ModeStore>((set) => ({
  mode: "kingdom",
  toggle: () =>
    set((s) => ({ mode: s.mode === "kingdom" ? "office" : "kingdom" })),
}));
