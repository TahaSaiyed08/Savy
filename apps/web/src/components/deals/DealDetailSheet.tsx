"use client";
import { useState } from "react";
import { Sheet } from "@/components/Sheet";
import { PrimaryButton, money } from "@/components/ui";
import { productImage } from "@/lib/products";
import { formatUnit } from "@/components/deals/DealCard";
import type { Schemas } from "@/lib/api";

export function formatValidity(weekStart?: string | null) {
  if (!weekStart) return undefined;
  const start = new Date(`${weekStart}T00:00:00`);
  const end = new Date(start);
  end.setDate(end.getDate() + 6);
  const month = start.toLocaleDateString("en-US", { month: "short" });
  return `Valid ${month} ${start.getDate()} – ${end.getDate()}`;
}

export function DealDetailSheet({
  deal,
  others,
  onClose,
}: {
  deal: Schemas["Deal"] | null;
  others: Schemas["Deal"][];
  onClose: () => void;
}) {
  const [showNote, setShowNote] = useState(false);
  if (!deal) return null;
  const img = productImage(deal.flyer_label);
  const validity = formatValidity(deal.week_start);

  return (
    <Sheet
      open={!!deal}
      onClose={() => {
        setShowNote(false);
        onClose();
      }}
      title="Deal details"
      action={<span className="w-[72px]" />}
    >
      <div className="flex flex-col gap-4 px-4 pb-8">
        <div className="relative flex h-[200px] items-center justify-center overflow-hidden rounded-2xl border border-separator bg-elevated shadow-card">
          {img ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={img} alt="" className="size-[200px] object-cover" />
          ) : (
            <p className="text-[40px] font-semibold text-label-2">{deal.item_label.charAt(0)}</p>
          )}
          <span className="absolute left-3 top-3 rounded-full border border-separator bg-bg px-2.5 py-1 text-[13px]">{deal.store}</span>
        </div>

        <p className="text-[22px] font-semibold">{deal.flyer_label}</p>

        <div className="flex items-baseline gap-3.5">
          <p className="text-[34px] font-bold text-tint">{money(deal.price)}</p>
          {deal.unit_price != null && deal.unit && (
            <p className="text-[15px] text-label-2">
              {money(deal.unit_price)}/{formatUnit(deal.unit)}
            </p>
          )}
        </div>

        <div className="flex flex-wrap gap-2">
          {validity && <span className="rounded-full border border-separator bg-elevated px-2 py-1.5 text-[13px] text-label-2">{validity}</span>}
          {deal.savings_vs_median != null && deal.savings_vs_median > 0 && (
            <span className="rounded-full bg-savings-bg px-2 py-1.5 text-[13px] text-savings-text">Save {money(deal.savings_vs_median)} vs typical</span>
          )}
        </div>

        {others.length > 0 && (
          <>
            <p className="pt-3 text-[13px] font-semibold text-label-2">OTHER STORES THIS WEEK</p>
            <div className="overflow-hidden rounded-2xl border border-separator bg-elevated shadow-card">
              {others.map((o) => (
                <div key={o.flyer_item_id} className="flex h-[52px] items-center justify-between border-b border-separator px-4 last:border-b-0">
                  <p className="text-[17px]">{o.store}</p>
                  <p className="text-[17px] font-semibold">{money(o.price)}</p>
                </div>
              ))}
            </div>
          </>
        )}

        <div className="pt-2">
          <PrimaryButton onClick={() => setShowNote(true)}>See it on the flyer</PrimaryButton>
          {showNote && <p className="pt-2 text-center text-[13px] text-label-2">Flyer photo isn&apos;t available in this demo.</p>}
        </div>
      </div>
    </Sheet>
  );
}
