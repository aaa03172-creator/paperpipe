import { create } from "zustand";

type ThemeMode = "dark" | "light" | "system";

interface AppStore {
  themeMode: ThemeMode;
  resolvedTheme: "dark" | "light";
  searchQuery: string;
  terminalOpen: boolean;
  activeClaimId: string | null;
  selectedPersonaId: string;
  mockMode: boolean;
  mockReasons: string[];
  hydrateTheme: () => void;
  setThemeMode: (mode: ThemeMode) => void;
  setSearchQuery: (query: string) => void;
  setTerminalOpen: (open: boolean) => void;
  toggleTerminal: () => void;
  setActiveClaimId: (claimId: string | null) => void;
  setSelectedPersonaId: (personaId: string) => void;
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
  resolvedTheme: "dark",
  searchQuery: "",
  terminalOpen: false,
  activeClaimId: "claim-1",
  selectedPersonaId: "default",
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
  setSelectedPersonaId: (personaId) => set({ selectedPersonaId: personaId }),
  markMockMode: (reason) =>
    set((state) => ({
      mockMode: true,
      mockReasons: reason ? Array.from(new Set([...state.mockReasons, reason])) : state.mockReasons,
    })),
  clearMockMode: () => set({ mockMode: false, mockReasons: [] }),
}));
