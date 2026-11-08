import { ChevronRight, Clock, ShoppingCart } from "@/components/icons";
import { PriceTag } from "@/components/PriceTag";
import { Thumb } from "@/components/Thumb";
import { money } from "@/components/ui";
import { daysLeft, itemMeta, weekday } from "@/lib/format";
import type { Schemas } from "@/lib/api";

const cheapestOf = (similar: Schemas["FlyerListing"][]) => Math.min(...similar.map((l) => l.price ?? Infinity));

function DealLine({ item }: { item: Schemas["ListItem"] }) {
  const deal = item.cheapest;
  if (!deal) {
    const n = item.closest?.length ?? 0;
    return n ? <p className="truncate text-[13px] text-label-2">No exact match · {n} similar on sale</p> : null;
  }
  const left = daysLeft(deal.valid_to);
  if (left != null && left >= 0 && left <= 2 && deal.valid_to) {
    return (
      <p className="flex items-center gap-1 truncate text-[13px] text-clock">
        <Clock size={13} className="shrink-0" />
        {deal.store}, ends {weekday(deal.valid_to)}
      </p>
    );
  }
  return (
    <p className="truncate text-[13px] text-label-2">
      {deal.store}
      {!!item.saves_vs_next && <span className="font-semibold text-tint"> · {money(item.saves_vs_next)} less than next store</span>}
    </p>
  );
}

/** The inside of a Pantry or Basket row. `inBasketMark` is for Pantry, where an item can be in both. */
export function ItemContent({ item, struck, inBasketMark }: { item: Schemas["ListItem"]; struck?: boolean; inBasketMark?: boolean }) {
  const meta = itemMeta(item);
  return (
    <>
      <Thumb src={item.cheapest?.image_url ?? item.closest?.[0]?.image_url} source={item.source} />
      <div className="min-w-0 flex-1">
        <p className="flex items-center gap-1.5">
          <span className={`truncate ${struck ? "text-label-2 line-through" : ""}`}>{item.item}</span>
          {inBasketMark && item.in_basket && <ShoppingCart size={14} className="shrink-0 text-tint" aria-label="In basket" />}
        </p>
        {meta && <p className="truncate text-[15px] text-label-2">{meta}</p>}
        {!struck && <DealLine item={item} />}
      </div>
      {item.cheapest ? (
        <PriceTag price={item.cheapest.price} regular={item.cheapest.regular_price} />
      ) : (
        !!item.closest?.length && <span className="shrink-0 text-[15px] font-semibold tabular-nums">from {money(cheapestOf(item.closest))}</span>
      )}
      <ChevronRight size={16} className="shrink-0 text-label-2/60" />
    </>
  );
}
