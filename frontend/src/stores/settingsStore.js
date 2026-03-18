import { create } from "zustand";

const STORAGE_KEY = "ic_settings";

function loadFromStorage() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw);
    return typeof parsed === "object" && parsed !== null ? parsed : {};
  } catch {
    return {};
  }
}

function saveToStorage(state) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch (e) {
    console.warn("[settingsStore] Failed to persist:", e);
  }
}

const defaults = {
  interviewerShortcutKey: "i",
};

const useSettingsStore = create((set, get) => {
  const stored = loadFromStorage();
  const initialState = { ...defaults, ...stored };

  return {
    interviewerShortcutKey: initialState.interviewerShortcutKey ?? defaults.interviewerShortcutKey,

    setInterviewerShortcutKey: (key) => {
      const k = typeof key === "string" ? key : String(key ?? defaults.interviewerShortcutKey);
      set({ interviewerShortcutKey: k });
      saveToStorage({ ...loadFromStorage(), interviewerShortcutKey: k });
    },
  };
});

export default useSettingsStore;
