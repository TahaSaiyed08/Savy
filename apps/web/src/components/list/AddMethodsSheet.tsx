"use client";
import { Sheet } from "@/components/Sheet";
import { Camera, ChevronRight, Mic, ReceiptText } from "@/components/icons";

const OPTIONS = [
  { key: "receipt" as const, Icon: ReceiptText, title: "Scan a receipt", subtitle: "Adds everything you bought" },
  { key: "photo" as const, Icon: Camera, title: "Photo of a product", subtitle: "Adds one item from its packaging" },
  { key: "type" as const, Icon: Mic, title: "Type or say it", subtitle: "e.g. a 4 L jug of 2% milk" },
];

export type AddMethod = (typeof OPTIONS)[number]["key"];

export function AddMethodsSheet({
  open,
  onClose,
  onPick,
}: {
  open: boolean;
  onClose: () => void;
  onPick: (method: AddMethod) => void;
}) {
  return (
    <Sheet open={open} onClose={onClose} title="Add to your list" action={<span className="w-[72px]" />}>
      <div className="p-4">
        <div className="overflow-hidden rounded-[20px] bg-elevated shadow-[0_4px_16px_0_rgba(0,0,0,0.03)]">
          {OPTIONS.map((o) => (
            <button
              key={o.key}
              type="button"
              onClick={() => onPick(o.key)}
              className="flex w-full items-center gap-3.5 border-b border-separator p-4 text-left last:border-b-0"
            >
              <o.Icon size={26} className="shrink-0 text-tint" />
              <div className="min-w-0 flex-1">
                <p className="text-[17px] font-semibold">{o.title}</p>
                <p className="text-[15px] text-label-2">{o.subtitle}</p>
              </div>
              <ChevronRight size={16} className="shrink-0 text-label-2" />
            </button>
          ))}
        </div>
      </div>
    </Sheet>
  );
}
