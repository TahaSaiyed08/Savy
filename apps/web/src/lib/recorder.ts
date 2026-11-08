// Thin MediaRecorder wrapper for the hold-to-talk mic. Safari records audio/mp4, Chrome audio/webm;
// /intake/voice accepts either (stt.py passes the content-type straight through to ElevenLabs).
export class VoiceRecorder {
  private recorder?: MediaRecorder;
  private chunks: BlobPart[] = [];
  private stream?: MediaStream;
  private audioCtx?: AudioContext;

  async start(onLevel?: (level: number) => void) {
    this.stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const mimeType = ["audio/webm", "audio/mp4"].find((t) => MediaRecorder.isTypeSupported(t));
    this.recorder = new MediaRecorder(this.stream, mimeType ? { mimeType } : undefined);
    this.chunks = [];
    this.recorder.ondataavailable = (e) => {
      if (e.data.size) this.chunks.push(e.data);
    };
    this.recorder.start();
    if (onLevel) this.monitorLevel(onLevel);
  }

  private monitorLevel(onLevel: (level: number) => void) {
    if (!this.stream) return;
    this.audioCtx = new AudioContext();
    const source = this.audioCtx.createMediaStreamSource(this.stream);
    const analyser = this.audioCtx.createAnalyser();
    analyser.fftSize = 256;
    source.connect(analyser);
    const data = new Uint8Array(analyser.frequencyBinCount);
    const tick = () => {
      if (!this.recorder || this.recorder.state !== "recording") return;
      analyser.getByteFrequencyData(data);
      const avg = data.reduce((a, b) => a + b, 0) / data.length;
      onLevel(Math.min(1, avg / 140));
      requestAnimationFrame(tick);
    };
    tick();
  }

  stop(): Promise<{ blob: Blob; mimeType: string; filename: string } | null> {
    return new Promise((resolve) => {
      if (!this.recorder) return resolve(null);
      const mimeType = this.recorder.mimeType || "audio/webm";
      this.recorder.onstop = () => {
        this.stream?.getTracks().forEach((t) => t.stop());
        this.audioCtx?.close().catch(() => {});
        resolve(
          this.chunks.length
            ? { blob: new Blob(this.chunks, { type: mimeType }), mimeType, filename: mimeType.includes("mp4") ? "voice.mp4" : "voice.webm" }
            : null,
        );
      };
      this.recorder.stop();
    });
  }

  cancel() {
    this.recorder?.stop();
    this.stream?.getTracks().forEach((t) => t.stop());
    this.audioCtx?.close().catch(() => {});
  }
}
