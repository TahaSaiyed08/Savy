"use client";
import { money } from "@/components/ui";
import { productImage } from "@/lib/products";
import type { Schemas } from "@/lib/api";

export function formatUnit(unit: string) {
  return unit.replace(/^(\d+)(\D+)$/, "$1 $2");
}

export function dealBadge(deal: Schemas["Deal"], isCheapest: boolean, groupSize: number) {
  if (!isCheapest) return null;
  if (deal.savings_vs_median != null && deal.savings_vs_median > 0) return `Save ${money(deal.savings_vs_median)} vs typical`;
  if (groupSize === 1) return "Lowest this week";
  return null;
}

export function DealCard({
  deal,
  isCheapest,
  groupSize,
  onClick,
}: {
  deal: Schemas["Deal"];
  isCheapest: boolean;
  groupSize: number;
  onClick?: () => void;
}) {
  const img = productImage(deal.flyer_label);
  const badge = dealBadge(deal, isCheapest, groupSize);
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex w-[150px] shrink-0 flex-col overflow-hidden rounded-2xl border border-separator bg-elevated text-left shadow-card"
    >
      <div className="relative size-[150px] bg-elevated">
        {img ? (
          // eslint-disable-next-line @next/next/no-img-element -- demo product photography shipped as static assets
          <img src={img} alt="" className="size-full object-cover" />
        ) : (
          <div className="flex size-full items-center justify-center text-[28px] font-semibold text-label-2">{deal.item_label.charAt(0)}</div>
        )}
        <span className="absolute left-1.5 top-1.5 rounded-[5px] bg-elevated/95 px-1.5 py-1 text-[13px] text-label">{deal.store}</span>
      </div>
      <div className="flex flex-col gap-1 p-2.5">
        <p className={`text-[28px] font-bold ${isCheapest ? "text-tint" : "text-label"}`}>{money(deal.price)}</p>
        {deal.unit_price != null && deal.unit && (
          <p className="text-[13px] text-label-2">
            {money(deal.unit_price)}/{formatUnit(deal.unit)}
          </p>
        )}
        <p className="truncate text-[13px] text-label-2">{deal.flyer_label}</p>
        {deal.match_score < 1 && <p className="text-[13px] text-label-2">Probable match</p>}
        {badge && (
          <div className="rounded-lg border border-savings-border bg-savings-bg px-1.5 py-1">
            <p className="text-[13px] font-medium text-savings-text">{badge}</p>
          </div>
        )}
      </div>
    </button>
  );
}
