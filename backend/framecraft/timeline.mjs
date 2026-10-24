// Shared picture/sound clock; four-second master scales to the selected duration.
export const EVENTS = Object.freeze([
  { at: 0.10, kind: 'spark', hz: 660, pan: 0 },
  { at: 0.48, kind: 'draw', hz: 220, pan: -0.3 },
  { at: 0.88, kind: 'petal', hz: 330, pan: -0.55 },
  { at: 1.20, kind: 'petal', hz: 440, pan: 0.5 },
  { at: 1.54, kind: 'petal', hz: 550, pan: -0.35 },
  { at: 1.88, kind: 'orbit', hz: 880, pan: 0.55 },
  { at: 2.18, kind: 'riser', hz: 170, pan: 0 },
  { at: 2.70, kind: 'bloom', hz: 220, pan: 0 },
]);
export const BREATH = [2.46, 2.66];
export function masterTime(seconds, duration) {
  // The final second is a true hold, including at the minimum 3-second duration.
  return seconds < duration - 1 ? seconds / (duration - 1) * 3 : 3 + seconds - (duration - 1);
}
