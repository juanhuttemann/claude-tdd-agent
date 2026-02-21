// Shared mutable state
export const state = {
  evtSource: null,
  currentCard: null,
  currentToolList: null,
  toolCount: 0,
  isAnimating: false,
  skipAnimation: false,
  animationQueue: [],
  cachedSummary: null,
  currentBrowsePath: null,
  currentDirEntries: [],
  pipelineStartedAt: null,
  timerInterval: null,
};
