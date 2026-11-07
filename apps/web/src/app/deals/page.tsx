"use client";
import { InsetGroup, LargeTitle, money, Row, Status } from "@/components/ui";
import { api, type Schemas, withUser } from "@/lib/api";
import { useApi } from "@/lib/use-api";

export default function Deals() {
  const { data, loading, error } = useApi(() => api.GET("/deals", { params: withUser() }));
  // Plain reduce, not Object.groupBy: that needs iOS 17.4+ and judges' phones vary.
  const byItem: Record<string, Schemas["Deal"][]> = {};
  for (const d of data ?? []) (byItem[d.item_label] ??= []).push(d);
  return (
    <>
      <LargeTitle title="Deals" />
      <Status loading={loading} error={error} empty={data?.length === 0 ? "No deals on your items this week." : undefined} />
      {Object.entries(byItem).map(([item, deals]) => (
        <InsetGroup key={item} header={item}>
          {[...deals]
            .sort((a, b) => (a.unit_price ?? Infinity) - (b.unit_price ?? Infinity))
            .map((d, i) => (
              <Row
                key={d.flyer_item_id}
                title={d.store}
                subtitle={`${d.flyer_label}${d.unit_price != null ? ` · ${money(d.unit_price)}/${d.unit}` : ""}${d.match_score < 1 ? " · probable match" : ""}`}
                detail={money(d.price)}
                accent={i === 0}
              />
            ))}
        </InsetGroup>
      ))}
    </>
  );
}
