"use client";
// Self-contained idle / recording / parsed flow. Typed text skips straight to /intake/manual; holding the
// mic records via MediaRecorder and posts to /intake/voice. Both land on the same parsed editor.
import { useRef, useState } from "react";
import { Sheet } from "@/components/Sheet";
import { InlineError, PrimaryButton } from "@/components/ui";
import { Loader, Mic } from "@/components/icons";
import { ItemEditor, draftFrom, draftToItem, type ItemDraft } from "@/components/ItemEditor";
import { api, withUser, type Schemas } from "@/lib/api";
import { intakeController, intakeErrorMessage } from "@/lib/intake";
import { VoiceRecorder } from "@/lib/recorder";

export type Step = "idle" | "recording" | "transcribing" | "parsed";
const BARS = 18;

export function TypeOrSaySheet({
  open,
  onClose,
  onAdd,
  saving,
  saveError,
  onRetrySave,
  previewStep,
}: {
  open: boolean;
  onClose: () => void;
  onAdd: (item: Schemas["ExtractedItem"], source: "manual" | "voice") => void;
  saving?: boolean;
  /** Set when the last onAdd's /items save failed; "tap to retry" re-submits the same parsed item. */
  saveError?: string;
  onRetrySave?: () => void;
  /** Dev-only: render straight into a step (e.g. "recording") without a real mic, for /dev/states. */
  previewStep?: Step;
}) {
  const [step, setStep] = useState<Step>(previewStep ?? "idle");
  const [text, setText] = useState("");
  const [levels, setLevels] = useState<number[]>(() =>
    previewStep === "recording" ? Array.from({ length: BARS }, () => 0.15 + Math.random() * 0.75) : Array(BARS).fill(0.15),
  );
  const [transcript, setTranscript] = useState<string>();
  const [draft, setDraft] = useState<ItemDraft | null>(null);
  const [errorMsg, setErrorMsg] = useState<string>();
  const [viaVoice, setViaVoice] = useState(false);
  const recorder = useRef<VoiceRecorder | null>(null);
  const released = useRef(false);

  function reset() {
    setStep("idle");
    setText("");
    setTranscript(undefined);
    setDraft(null);
    setErrorMsg(undefined);
    recorder.current?.cancel();
    recorder.current = null;
  }

  async function submitManual() {
    const value = text.trim();
    if (!value) return;
    setStep("transcribing");
    setErrorMsg(undefined);
    setViaVoice(false);
    const ctl = intakeController();
    try {
      const { data, error, response } = await api.POST("/intake/manual", {
        params: withUser(),
        body: { text: value },
        signal: ctl.signal,
      });
      ctl.done();
      if (error || !data) {
        setErrorMsg(intakeErrorMessage(response));
        setStep("idle");
        return;
      }
      setTranscript(value);
      setDraft(draftFrom(data.extraction.items[0] ?? { item: value, confidence: 0.5 }));
      setStep("parsed");
    } catch {
      ctl.done();
      if (ctl.wasCancelled()) return;
      setErrorMsg(intakeErrorMessage());
      setStep("idle");
    }
  }

  async function startRecording() {
    if (typeof window === "undefined" || !window.MediaRecorder || !navigator.mediaDevices) {
      setErrorMsg("Recording isn't supported here — type instead.");
      return;
    }
    released.current = false;
    try {
      const rec = new VoiceRecorder();
      await rec.start((level) => setLevels((prev) => [...prev.slice(1), 0.15 + level * 0.85]));
      if (released.current) {
        rec.cancel();
        return;
      }
      recorder.current = rec;
      setErrorMsg(undefined);
      setStep("recording");
    } catch {
      setErrorMsg("Microphone access is blocked. Type it instead.");
    }
  }

  function releaseTalk() {
    released.current = true;
    if (step === "recording") stopRecording();
  }

  async function stopRecording() {
    const rec = recorder.current;
    recorder.current = null;
    if (!rec) {
      setStep("idle");
      return;
    }
    setStep("transcribing");
    const result = await rec.stop();
    if (!result) {
      setErrorMsg("Hold the button while you talk.");
      setStep("idle");
      return;
    }
    setViaVoice(true);
    const ctl = intakeController();
    try {
      const form = new FormData();
      form.set("file", result.blob, result.filename);
      const { data, error, response } = await api.POST("/intake/voice", {
        params: withUser(),
        body: form as never,
        signal: ctl.signal,
      });
      ctl.done();
      if (error || !data) {
        setErrorMsg(intakeErrorMessage(response, "voice"));
        setStep("idle");
        return;
      }
      setTranscript(data.transcript ?? undefined);
      setDraft(draftFrom(data.extraction.items[0] ?? { item: "", confidence: 0.5 }));
      setStep("parsed");
    } catch {
      ctl.done();
      if (ctl.wasCancelled()) return;
      setErrorMsg(intakeErrorMessage());
      setStep("idle");
    }
  }

  function submitParsed() {
    if (!draft) return;
    onAdd(draftToItem(draft, 1), viaVoice ? "voice" : "manual");
  }

  return (
    <Sheet
      open={open}
      onClose={() => {
        reset();
        onClose();
      }}
      title="Type or say it"
      action={<span className="w-[72px]" />}
    >
      <div className="flex flex-col gap-6 px-4 pt-5 pb-8">
        {errorMsg && <p className="text-[13px] text-destructive">{errorMsg}</p>}

        {step === "parsed" && draft ? (
          <>
            {transcript && <p className="text-[15px] text-label-2">&ldquo;{transcript}&rdquo;</p>}
            <ItemEditor draft={draft} onChange={setDraft} />
            {saveError && onRetrySave && <InlineError message={saveError} onRetry={onRetrySave} />}
            <PrimaryButton onClick={submitParsed} disabled={!draft.item} loading={saving}>
              Add to list
            </PrimaryButton>
          </>
        ) : (
          <>
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  submitManual();
                }
              }}
              placeholder="e.g. a 4 L jug of 2% milk"
              aria-label="What do you want to add?"
              rows={3}
              disabled={step !== "idle"}
              className="min-h-[108px] w-full resize-none rounded-2xl border border-separator bg-elevated p-4 text-[17px] text-label shadow-card outline-none placeholder:text-label-2/70 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-tint"
            />

            <div className="flex flex-col items-center gap-4">
              {step === "recording" ? (
                <div className="flex h-10 items-end gap-1">
                  {levels.map((l, i) => (
                    <span key={i} className="w-1 rounded-sm bg-tint" style={{ height: `${8 + l * 32}px` }} />
                  ))}
                </div>
              ) : (
                <div className="h-10" />
              )}

              <button
                type="button"
                aria-label={step === "recording" ? "Release to stop recording" : "Hold to talk"}
                onPointerDown={(e) => {
                  e.preventDefault();
                  (e.currentTarget as Element).setPointerCapture(e.pointerId);
                  if (step === "idle") startRecording();
                }}
                onPointerUp={releaseTalk}
                onPointerCancel={releaseTalk}
                disabled={step === "transcribing"}
                className={`flex items-center justify-center rounded-full border shadow-soft transition-all duration-150 ${
                  step === "recording" ? "size-[110px] border-2 border-tint/30 bg-savings-bg" : "size-24 border-separator bg-bg"
                }`}
              >
                <span
                  className={`flex items-center justify-center rounded-full bg-tint shadow-tint transition-all duration-150 ${
                    step === "recording" ? "size-[88px]" : "size-20"
                  }`}
                >
                  {step === "transcribing" ? <Loader size={34} className="text-white" /> : <Mic size={34} className="text-white" />}
                </span>
              </button>

              <p className={`text-[17px] font-semibold ${step === "recording" ? "text-tint" : ""}`}>
                {step === "recording" ? "Listening… release to stop" : step === "transcribing" ? "Understanding…" : "Hold to talk"}
              </p>
            </div>
          </>
        )}
      </div>
    </Sheet>
  );
}
