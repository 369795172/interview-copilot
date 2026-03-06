/**
 * AudioWorklet processor for PCM16 @ 16kHz mono streaming.
 * Captures raw audio, resamples to 16kHz, applies energy-based VAD,
 * and posts PCM16 (Int16Array) buffers every ~200ms (3200 bytes).
 */

const TARGET_RATE = 16000;
const PACKET_SAMPLES = 3200; // 200ms @ 16kHz
const VAD_ENERGY_THRESHOLD = 0.005;
const VAD_SILENCE_FRAMES = 15; // ~3s of consecutive silence before gating

class AudioProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this._buffer = new Float32Array(0);
    this._ratio = 1;
    this._initialized = false;
    this._silenceCount = 0;
  }

  process(inputs) {
    const input = inputs[0];
    if (!input || !input[0] || input[0].length === 0) return true;

    const samples = input[0]; // mono channel

    if (!this._initialized) {
      this._ratio = sampleRate / TARGET_RATE;
      this._initialized = true;
    }

    // Accumulate
    const merged = new Float32Array(this._buffer.length + samples.length);
    merged.set(this._buffer);
    merged.set(samples, this._buffer.length);
    this._buffer = merged;

    // Downsample + emit when we have enough for a packet
    const neededInput = Math.ceil(PACKET_SAMPLES * this._ratio);
    while (this._buffer.length >= neededInput) {
      const chunk = this._buffer.slice(0, neededInput);
      this._buffer = this._buffer.slice(neededInput);

      // Linear interpolation downsample
      const resampled = new Float32Array(PACKET_SAMPLES);
      for (let i = 0; i < PACKET_SAMPLES; i++) {
        const srcIdx = i * this._ratio;
        const lo = Math.floor(srcIdx);
        const hi = Math.min(lo + 1, chunk.length - 1);
        const frac = srcIdx - lo;
        resampled[i] = chunk[lo] * (1 - frac) + chunk[hi] * frac;
      }

      // Energy-based VAD
      let energy = 0;
      for (let i = 0; i < resampled.length; i++) {
        energy += resampled[i] * resampled[i];
      }
      energy /= resampled.length;

      if (energy < VAD_ENERGY_THRESHOLD) {
        this._silenceCount++;
        if (this._silenceCount > VAD_SILENCE_FRAMES) continue;
      } else {
        this._silenceCount = 0;
      }

      // Convert float32 [-1, 1] to PCM16
      const pcm16 = new Int16Array(PACKET_SAMPLES);
      for (let i = 0; i < PACKET_SAMPLES; i++) {
        const s = Math.max(-1, Math.min(1, resampled[i]));
        pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
      }

      this.port.postMessage({ type: "audio", pcm: pcm16.buffer }, [pcm16.buffer]);
    }

    return true;
  }
}

registerProcessor("audio-processor", AudioProcessor);
