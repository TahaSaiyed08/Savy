"use client";
import { InsetGroup, LargeTitle, money, Row, Status } from "@/components/ui";
import { api, withUser } from "@/lib/api";
import { useApi } from "@/lib/use-api";

export default function Basket() {
  const { data: b, loading, error } = useApi(() => api.GET("/basket", { params: withUser() }));
  return (
    <>
      <LargeTitle title="Basket" />
      <Status loading={loading} error={error} empty={b && !b.cheapest_store ? "Add items to compare stores." : undefined} />
      {b?.cheapest_store && (
        <>
          <InsetGroup header="One store" footer={b.delta > 0 ? `Split-shopping saves ${money(b.delta)}.` : undefined}>
            {b.stores.map((s, i) => (
              <Row
                key={s.store}
                title={s.store}
                subtitle={s.missing ? `${s.missing} item${s.missing > 1 ? "s" : ""} not on sale` : "Everything on your list"}
                detail={money(s.total)}
                accent={i === 0}
              />
            ))}
          </InsetGroup>
          <InsetGroup header={`Split shop · ${money(b.split_total)}`}>
            {b.split.map((l) => (
              <Row key={l.user_item_id} title={l.item_label} subtitle={l.store} detail={money(l.cost)} />
            ))}
          </InsetGroup>
          {b.unmatched.length > 0 && (
            <InsetGroup header="No deal this week">
              {b.unmatched.map((u) => <Row key={u} title={u} />)}
            </InsetGroup>
          )}
        </>
      )}
    </>
  );
}
