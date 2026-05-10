import { create } from "zustand";
import type { ReasoningPersonaId } from "../lib/types";

type ThemeMode = "dark" | "light" | "system";
type ReasoningSelection = ReasoningPersonaId | "auto";

interface AppStore {
  themeMode: ThemeMode;
  resolvedTheme: "dark" | "light";
  searchQuery: string;
  terminalOpen: boolean;
  activeClaimId: string | null;
  selectedReasoningPersona: ReasoningSelection;
  selectedProfileId: string;
  mockMode: boolean;
  mockReasons: string[];
  hydrateTheme: () => void;
  setThemeMode: (mode: ThemeMode) => void;
  setSearchQuery: (query: string) => void;
  setTerminalOpen: (open: boolean) => void;
  toggleTerminal: () => void;
  setActiveClaimId: (claimId: string | null) => void;
  setSelectedReasoningPersona: (personaId: ReasoningSelection) => void;
  setSelectedProfileId: (profileId: string) => void;
  markMockMode: (reason?: string) => void;
  clearMockMode: () => void;
}

function resolveTheme(mode: ThemeMode): "dark" | "light" {
  if (mode === "system") {
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }
  return mode;
}

function applyTheme(theme: "dark" | "light") {
  document.documentElement.setAttribute("data-theme", theme);
}

export const useAppStore = create<AppStore>((set, get) => ({
  themeMode: "dark",
  resolvedTheme: resolveTheme("dark"),
  searchQuery: "",
  terminalOpen: false,
  activeClaimId: "claim-1",
  selectedReasoningPersona: "auto",
  selectedProfileId: "",
  mockMode: false,
  mockReasons: [],
  hydrateTheme: () => {
    const stored = window.localStorage.getItem("pp-theme") as ThemeMode | null;
    const mode = stored === "light" || stored === "dark" || stored === "system" ? stored : "dark";
    const resolved = resolveTheme(mode);
    applyTheme(resolved);
    set({ themeMode: mode, resolvedTheme: resolved });

    if (mode === "system") {
      const media = window.matchMedia("(prefers-color-scheme: dark)");
      const handler = () => {
        const currentMode = get().themeMode;
        if (currentMode !== "system") {
          return;
        }
        const currentResolved = resolveTheme("system");
        applyTheme(currentResolved);
        set({ resolvedTheme: currentResolved });
      };
      media.addEventListener("change", handler);
    }
  },
  setThemeMode: (mode) => {
    window.localStorage.setItem("pp-theme", mode);
    const resolved = resolveTheme(mode);
    applyTheme(resolved);
    set({ themeMode: mode, resolvedTheme: resolved });
  },
  setSearchQuery: (query) => set({ searchQuery: query }),
  setTerminalOpen: (open) => set({ terminalOpen: open }),
  toggleTerminal: () => set((state) => ({ terminalOpen: !state.terminalOpen })),
  setActiveClaimId: (claimId) => set({ activeClaimId: claimId }),
  setSelectedReasoningPersona: (personaId) => set({ selectedReasoningPersona: personaId }),
  setSelectedProfileId: (profileId) => set({ selectedProfileId: profileId }),
  markMockMode: (reason) =>
    set((state) => ({
      mockMode: true,
      mockReasons: reason ? Array.from(new Set([...state.mockReasons, reason])) : state.mockReasons,
    })),
  clearMockMode: () => set({ mockMode: false, mockReasons: [] }),
}));
