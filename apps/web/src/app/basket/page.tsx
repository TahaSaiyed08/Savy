"use client";
import { useRouter } from "next/navigation";
import { EmptyState, InsetGroup, LargeTitle, Row, Status, money } from "@/components/ui";
import { CircleCheck, ShoppingCart } from "@/components/icons";
import { api, withUser } from "@/lib/api";
import { useApi } from "@/lib/use-api";

export default function Basket() {
  const router = useRouter();
  const { data: b, loading, error } = useApi(() => api.GET("/basket", { params: withUser() }));
  const cheapest = b?.stores[0];
  const totalItems = cheapest ? cheapest.matched + cheapest.missing : 0;

  return (
    <>
      <LargeTitle title="Basket" />
      <Status loading={loading} error={error} />

      {!loading && !error && b && !b.cheapest_store && (
        <EmptyState icon={<ShoppingCart size={52} />} title="Add items to compare stores." primaryLabel="Add items" onPrimary={() => router.push("/list")} />
      )}

      {b?.cheapest_store && cheapest && (
        <>
          <div className="mx-4 mb-6 flex flex-col gap-3 rounded-[20px] border border-separator bg-elevated p-5 shadow-[0_6px_18px_0_rgba(0,0,0,0.04)] dark:shadow-[0_8px_24px_0_rgba(0,0,0,0.25)]">
            <div className="flex items-center justify-between">
              <p className="text-[13px] font-medium tracking-wide text-label-2 uppercase">Cheapest single store</p>
              <CircleCheck size={20} className="text-tint" />
            </div>
            <p className="text-[28px] font-bold">{b.cheapest_store}</p>
            <p className="text-[34px] font-bold text-tint">{money(cheapest.total)}</p>
            <p className="text-[15px] text-label-2">
              {cheapest.matched} of {totalItems} items on sale
            </p>
          </div>

          <InsetGroup header="One store">
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

          {b.delta > 0 && <p className="-mt-4 mb-6 px-8 text-[13px] font-semibold text-tint">Split-shopping saves {money(b.delta)}.</p>}

          {b.split.length > 0 && (
            <InsetGroup header={`Split shop · ${money(b.split_total)}`}>
              {b.split.map((l) => (
                <Row key={l.user_item_id} title={l.item_label} subtitle={l.store} detail={money(l.cost)} />
              ))}
            </InsetGroup>
          )}

          {b.unmatched.length > 0 && (
            <InsetGroup header="No deal this week">
              {b.unmatched.map((u) => (
                <Row key={u} title={u} />
              ))}
            </InsetGroup>
          )}
        </>
      )}
    </>
  );
}
