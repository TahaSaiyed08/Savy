import { Camera, List, Mic, ReceiptText, Tag } from "@/components/icons";

const ICONS = { receipt: ReceiptText, photo: Camera, voice: Mic, manual: List, flyer: Tag };

/** The flyer's own picture when there is one, else how the item got on the list. `category` (1-5) tints the well. */
export function Thumb({ src, source, category }: { src?: string | null; source?: keyof typeof ICONS; category?: number }) {
  const Icon = ICONS[source ?? "flyer"];
  const tint = category && !src ? { background: `var(--cat-${category}-bg)`, color: `var(--cat-${category}-fg)` } : undefined;
  return (
    <span className="flex size-11 shrink-0 items-center justify-center overflow-hidden rounded-[8px] bg-fill text-tint" style={tint}>
      {src ? (
        // eslint-disable-next-line @next/next/no-img-element -- remote flyer cutouts, sizes unknown ahead of time
        <img src={src} alt="" loading="lazy" className="size-full bg-white object-contain" />
      ) : (
        <Icon size={22} />
      )}
    </span>
  );
}
