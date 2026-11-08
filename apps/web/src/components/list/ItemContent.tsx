import { ChevronRight, Clock, ShoppingCart } from "@/components/icons";
import { PriceTag } from "@/components/PriceTag";
import { StoreDot } from "@/components/StoreDot";
import { Thumb } from "@/components/Thumb";
import { money } from "@/components/ui";
import { categoryOf } from "@/lib/category";
import { daysLeft, itemMeta, weekday } from "@/lib/format";
import type { Schemas } from "@/lib/api";

const cheapestOf = (similar: Schemas["FlyerListing"][]) => Math.min(...similar.map((l) => l.price ?? Infinity));

/** The row's second line: where it's cheapest and what you save, or why there's no deal yet. */
function DealLine({ item }: { item: Schemas["ListItem"] }) {
  const deal = item.cheapest;
  if (!deal) {
    const n = item.closest?.length ?? 0;
    const meta = itemMeta(item);
    if (n) return <p className="truncate text-[15px] text-label-2">No exact match · {n} similar on sale</p>;
    return meta ? <p className="truncate text-[15px] text-label-2">{meta}</p> : null;
  }
  const left = daysLeft(deal.valid_to);
  const soon = left != null && left >= 0 && left <= 2 && !!deal.valid_to;
  return (
    <p className="flex items-center truncate text-[15px] text-label-2">
      <StoreDot store={deal.store} />
      <span className="truncate">{deal.store}</span>
      {!!item.saves_vs_next && <span className="shrink-0 font-semibold text-savings-text">&nbsp;· Save {money(item.saves_vs_next)}</span>}
      {soon && deal.valid_to && (
        <span className="flex shrink-0 items-center gap-1 font-semibold text-clock">
          &nbsp;· <Clock size={13} className="shrink-0" />
          ends {weekday(deal.valid_to)}
        </span>
      )}
    </p>
  );
}

/** The inside of a Pantry or Basket row: two lines, a thumbnail and one price. `inBasketMark` is for Pantry. */
export function ItemContent({ item, struck, inBasketMark }: { item: Schemas["ListItem"]; struck?: boolean; inBasketMark?: boolean }) {
  return (
    <>
      <Thumb src={item.cheapest?.image_url ?? item.closest?.[0]?.image_url} source={item.source} category={categoryOf(item.item)} />
      <div className="min-w-0 flex-1">
        <p className="flex items-center gap-1.5">
          <span className={`truncate ${struck ? "text-label-2 line-through" : ""}`}>{item.item}</span>
          {inBasketMark && item.in_basket && <ShoppingCart size={14} className="shrink-0 text-tint" aria-label="In basket" />}
        </p>
        {struck ? (itemMeta(item) ? <p className="truncate text-[15px] text-label-2">{itemMeta(item)}</p> : null) : <DealLine item={item} />}
      </div>
      <span className="flex min-w-16 shrink-0 justify-end">
        {item.cheapest ? (
          <PriceTag price={item.cheapest.price} regular={item.cheapest.regular_price} />
        ) : (
          !!item.closest?.length && <span className="text-[15px] font-bold tabular-nums">from {money(cheapestOf(item.closest))}</span>
        )}
      </span>
      <ChevronRight size={16} className="shrink-0 text-label-2/60" />
    </>
  );
}
