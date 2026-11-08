import { money } from "@/components/ui";

/** The yellow flyer sticker: only ever a sale price from a flyer. */
export function PriceTag({ price, regular, large }: { price?: number | null; regular?: number | null; large?: boolean }) {
  const was = regular != null && price != null && regular > price ? regular : null;
  return (
    <span className={`flex ${large ? "items-center gap-2" : "flex-col items-end gap-0.5"}`} aria-label={`On sale, ${money(price)}${was ? `, was ${money(was)}` : ""}`}>
      <span
        aria-hidden
        className={`bg-price-tag font-extrabold text-on-price-tag tabular-nums ${large ? "rounded-[9px] px-2.5 py-[3px] text-[22px]" : "rounded-[6px] px-[7px] py-0.5 text-[17px]"}`}
      >
        {money(price)}
      </span>
      {was != null && (
        <span aria-hidden className="text-[12px] text-label-2 tabular-nums line-through">
          {money(was)}
        </span>
      )}
    </span>
  );
}
