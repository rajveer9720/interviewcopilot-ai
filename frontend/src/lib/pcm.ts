/**
 * Converts a browser MediaStream into 16-bit/16kHz/mono PCM chunks — the raw
 * format backend/transcripts/whisper_client.py expects. MediaRecorder's
 * compressed webm/opus output won't work here; Whisper needs uncompressed PCM.
 */
export class PcmStreamer {
  private ctx: AudioContext;
  private sources: MediaStreamAudioSourceNode[] = [];
  private merger: ChannelMergerNode | GainNode;
  private processor: ScriptProcessorNode;
  private readonly targetSampleRate = 16_000;

  constructor(streams: MediaStream[], onChunk: (pcm16: Int16Array) => void) {
    this.ctx = new AudioContext();
    this.merger = this.ctx.createGain();

    for (const stream of streams) {
      const source = this.ctx.createMediaStreamSource(stream);
      source.connect(this.merger);
      this.sources.push(source);
    }

    // ScriptProcessorNode is deprecated but universally supported and needs
    // no separate worklet module — fine for this data volume.
    this.processor = this.ctx.createScriptProcessor(4096, 1, 1);
    this.merger.connect(this.processor);

    // Some browsers only pull data through the graph once connected to a
    // destination; route through a silent gain so nothing is audibly echoed.
    const silence = this.ctx.createGain();
    silence.gain.value = 0;
    this.processor.connect(silence);
    silence.connect(this.ctx.destination);

    this.processor.onaudioprocess = (e) => {
      const input = e.inputBuffer.getChannelData(0);
      const downsampled = downsample(input, this.ctx.sampleRate, this.targetSampleRate);
      onChunk(floatTo16BitPCM(downsampled));
    };
  }

  stop() {
    this.processor.disconnect();
    this.merger.disconnect();
    this.sources.forEach((s) => s.disconnect());
    this.ctx.close();
  }
}

function downsample(buffer: Float32Array, inputRate: number, outputRate: number): Float32Array {
  if (outputRate === inputRate) return buffer;
  const ratio = inputRate / outputRate;
  const newLength = Math.round(buffer.length / ratio);
  const result = new Float32Array(newLength);
  let offsetResult = 0;
  let offsetBuffer = 0;
  while (offsetResult < newLength) {
    const nextOffsetBuffer = Math.round((offsetResult + 1) * ratio);
    let accum = 0;
    let count = 0;
    for (let i = offsetBuffer; i < nextOffsetBuffer && i < buffer.length; i++) {
      accum += buffer[i];
      count++;
    }
    result[offsetResult] = count > 0 ? accum / count : 0;
    offsetResult++;
    offsetBuffer = nextOffsetBuffer;
  }
  return result;
}

function floatTo16BitPCM(input: Float32Array): Int16Array {
  const output = new Int16Array(input.length);
  for (let i = 0; i < input.length; i++) {
    const s = Math.max(-1, Math.min(1, input[i]));
    output[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
  }
  return output;
}

export function int16ToBase64(pcm: Int16Array): string {
  const bytes = new Uint8Array(pcm.buffer);
  let binary = "";
  const chunkSize = 0x8000;
  for (let i = 0; i < bytes.length; i += chunkSize) {
    binary += String.fromCharCode(...bytes.subarray(i, i + chunkSize));
  }
  return btoa(binary);
}
