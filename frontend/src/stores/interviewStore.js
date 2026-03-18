import { create } from "zustand";

const useInterviewStore = create((set, get) => ({
  // Session
  sessionId: null,
  status: "preparing", // preparing | active | completed
  roleTitle: "",
  candidateId: null,
  candidateName: "",

  // Transcript
  transcript: [],
  currentSpeaker: "candidate",

  // AI Copilot
  suggestions: [],
  suggestionSeq: 1,
  pinnedSuggestionIds: [],
  customGuidanceActive: false,

  // Evaluation
  scores: [],
  coverage: null,
  decision: null,

  // Context
  context: {
    companyValues: "",
    projectBackground: "",
    candidateProfile: null,
    customNotes: "",
  },

  // Recording
  isRecording: false,

  // Transcription errors (surfaced from backend)
  transcriptionError: null, // { error, count } or null

  // Partial transcript (in-progress from streaming ASR)
  partialTranscript: null, // { speaker, text, time } or null

  // STT provider info
  sttProvider: null, // { provider, status } or null
  sttHealthy: null, // from pong payload; true | false | null

  // WebSocket
  ws: null,

  // ---- Actions ----

  setSession: (id, data = {}) =>
    set({ sessionId: id, ...data }),

  setStatus: (status) => set({ status }),
  setRoleTitle: (roleTitle) => set({ roleTitle }),
  setCandidateId: (id) => set({ candidateId: id }),
  setCandidateName: (name) => set({ candidateName: name }),

  addTranscript: (entry) =>
    set((s) => ({ transcript: [...s.transcript, entry] })),
  setTranscript: (entries) => set({ transcript: entries || [] }),
  updateTranscriptRefined: (id, text) =>
    set((s) => ({
      transcript: s.transcript.map((e) => (e.id === id ? { ...e, text } : e)),
    })),

  setCurrentSpeaker: (speaker) => set({ currentSpeaker: speaker }),

  setSuggestions: (suggestions) =>
    set((s) => {
      const base = s.suggestionSeq;
      const normalized = (suggestions || []).map((item, idx) => ({
        ...item,
        _localId: item?._localId ?? base + idx,
      }));
      return {
        suggestions: normalized,
        suggestionSeq: base + normalized.length,
      };
    }),
  appendSuggestions: (newSugs) =>
    set((s) => ({
      suggestions: (newSugs || [])
        .map((item, idx) => ({
          ...item,
          _localId: item?._localId ?? (s.suggestionSeq + idx),
        }))
        .concat(s.suggestions)
        .slice(0, 20),
      suggestionSeq: s.suggestionSeq + (newSugs || []).length,
    })),
  pinSuggestion: (id) =>
    set((s) => ({
      pinnedSuggestionIds: s.pinnedSuggestionIds.includes(id)
        ? s.pinnedSuggestionIds
        : [id, ...s.pinnedSuggestionIds],
    })),
  unpinSuggestion: (id) =>
    set((s) => ({
      pinnedSuggestionIds: s.pinnedSuggestionIds.filter((x) => x !== id),
    })),
  togglePinSuggestion: (id) =>
    set((s) => ({
      pinnedSuggestionIds: s.pinnedSuggestionIds.includes(id)
        ? s.pinnedSuggestionIds.filter((x) => x !== id)
        : [id, ...s.pinnedSuggestionIds],
    })),
  dismissSuggestion: (id) =>
    set((s) => ({
      suggestions: s.suggestions.filter((item) => item._localId !== id),
      pinnedSuggestionIds: s.pinnedSuggestionIds.filter((x) => x !== id),
    })),
  setCustomGuidanceActive: (active) => set({ customGuidanceActive: !!active }),

  setScores: (scores) => set({ scores }),
  setCoverage: (coverage) => set({ coverage }),
  setDecision: (decision) => set({ decision }),

  updateContext: (partial) =>
    set((s) => ({ context: { ...s.context, ...partial } })),

  setRecording: (v) => set({ isRecording: v }),
  setTranscriptionError: (err) => set({ transcriptionError: err }),
  setPartialTranscript: (p) => set({ partialTranscript: p }),
  setSttProvider: (info) => set({ sttProvider: info }),
  setSttHealthy: (v) => set({ sttHealthy: v }),
  setWs: (ws) => set({ ws }),

  reset: () =>
    set({
      sessionId: null,
      status: "preparing",
      roleTitle: "",
      candidateId: null,
      candidateName: "",
      transcript: [],
      currentSpeaker: "candidate",
      suggestions: [],
      suggestionSeq: 1,
      pinnedSuggestionIds: [],
      customGuidanceActive: false,
      scores: [],
      coverage: null,
      decision: null,
      context: {
        companyValues: "",
        projectBackground: "",
        candidateProfile: null,
        customNotes: "",
      },
      isRecording: false,
      transcriptionError: null,
      partialTranscript: null,
      sttProvider: null,
      sttHealthy: null,
      ws: null,
    }),
}));

export default useInterviewStore;
