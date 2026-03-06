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
  currentSpeaker: "interviewer",

  // AI Copilot
  suggestions: [],

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

  setCurrentSpeaker: (speaker) => set({ currentSpeaker: speaker }),

  setSuggestions: (suggestions) => set({ suggestions }),
  appendSuggestions: (newSugs) =>
    set((s) => ({
      suggestions: [...newSugs, ...s.suggestions].slice(0, 20),
    })),

  setScores: (scores) => set({ scores }),
  setCoverage: (coverage) => set({ coverage }),
  setDecision: (decision) => set({ decision }),

  updateContext: (partial) =>
    set((s) => ({ context: { ...s.context, ...partial } })),

  setRecording: (v) => set({ isRecording: v }),
  setTranscriptionError: (err) => set({ transcriptionError: err }),
  setPartialTranscript: (p) => set({ partialTranscript: p }),
  setSttProvider: (info) => set({ sttProvider: info }),
  setWs: (ws) => set({ ws }),

  reset: () =>
    set({
      sessionId: null,
      status: "preparing",
      roleTitle: "",
      candidateId: null,
      candidateName: "",
      transcript: [],
      currentSpeaker: "interviewer",
      suggestions: [],
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
      ws: null,
    }),
}));

export default useInterviewStore;
