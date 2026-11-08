import { Camera, List, Mic, ReceiptText, Tag } from "@/components/icons";

const ICONS = { receipt: ReceiptText, photo: Camera, voice: Mic, manual: List, flyer: Tag };

/** The flyer's own picture when there is one, else how the item got on the list. With `href`, the image
 * itself opens that flyer in a new tab (used instead of a separate "Original flyer" link). Rows that pass
 * `href` are usually a tap/swipe target themselves, so this stops its own pointer/click events from
 * bubbling — tapping the image opens the flyer, not the row's own action. */
export function Thumb({
  src,
  source,
  href,
  store,
  item,
}: {
  src?: string | null;
  source?: keyof typeof ICONS;
  href?: string | null;
  store?: string | null;
  item?: string | null;
}) {
  const Icon = ICONS[source ?? "flyer"];
  const body = src ? (
    // eslint-disable-next-line @next/next/no-img-element -- remote flyer cutouts, sizes unknown ahead of time
    <img src={src} alt="" loading="lazy" className="size-full bg-white object-contain" />
  ) : (
    <Icon size={22} />
  );

  if (href) {
    const stop = (e: React.SyntheticEvent) => e.stopPropagation();
    return (
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        aria-label={`Open ${store || "the"} flyer for ${item || "this item"}`}
        onPointerDown={stop}
        onPointerUp={stop}
        onClick={stop}
        className="flex size-11 shrink-0 items-center justify-center overflow-hidden rounded-[8px] bg-fill text-tint transition-transform active:scale-95"
      >
        {body}
      </a>
    );
  }
  return (
    <span className="flex size-11 shrink-0 items-center justify-center overflow-hidden rounded-[8px] bg-fill text-tint">
      {body}
    </span>
  );
}
