"use client";
// Full-screen takeover (not a sheet) while /intake/receipt runs, matching the Figma "Reading receipt" frame.
import { Loader } from "@/components/icons";

export function ReceiptLoading({ previewUrl, onCancel }: { previewUrl?: string; onCancel: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-bg" style={{ paddingTop: "env(safe-area-inset-top)" }}>
      <div className="flex h-11 items-center px-4">
        <button type="button" onClick={onCancel} className="text-[17px] font-semibold text-tint">
          Cancel
        </button>
      </div>
      <div className="flex flex-1 flex-col items-center gap-7 px-8 pt-16">
        {previewUrl ? (
          // eslint-disable-next-line @next/next/no-img-element -- transient blob: URL, not a static asset
          <img src={previewUrl} alt="" className="h-[246px] w-[174px] rounded-xl object-cover blur-[1.5px]" />
        ) : (
          <div className="h-[246px] w-[174px] rounded-xl bg-elevated" />
        )}
        <Loader size={28} className="text-label-2" />
        <div className="flex flex-col items-center gap-2 text-center">
          <p className="text-[22px] font-semibold">Reading your receipt…</p>
          <p className="text-[15px] text-label-2">This takes a few seconds.</p>
        </div>
      </div>
    </div>
  );
}
