"use client";
import { useRouter } from "next/navigation";
import { EmptyState, InsetGroup, LargeTitle, RetryButton, Row, Skeleton, Status, money } from "@/components/ui";
import { CircleCheck, ShoppingCart } from "@/components/icons";
import { api, withUser } from "@/lib/api";
import { useApi } from "@/lib/use-api";

function BasketSkeleton() {
  return (
    <>
      <div className="mx-4 mb-6 flex flex-col gap-3 rounded-[20px] border border-separator bg-elevated p-5 shadow-card">
        <Skeleton className="h-3 w-32" />
        <Skeleton className="h-7 w-40" />
        <Skeleton className="h-9 w-28" />
        <Skeleton className="h-[15px] w-44" />
      </div>
      <section className="mx-4 mb-6">
        <Skeleton className="mb-1.5 ml-4 h-3 w-16" />
        <ul className="overflow-hidden rounded-[20px] bg-elevated shadow-card">
          {[0, 1, 2].map((i) => (
            <li key={i} className="flex min-h-tap items-center gap-3 border-b border-separator px-4 py-2.5 last:border-b-0">
              <Skeleton className="h-[17px] w-28" />
            </li>
          ))}
        </ul>
      </section>
    </>
  );
}

export default function Basket() {
  const router = useRouter();
  const { data: b, loading, error, refetch } = useApi(() => api.GET("/basket", { params: withUser() }));
  // b.stores is ordered fewest-missing-first, then cheapest within that tier (see the Basket model) — it's
  // the best single-store pick, not necessarily the lowest dollar total across all stores.
  const bestStore = b?.stores[0];
  const totalItems = bestStore ? bestStore.matched + bestStore.missing : 0;

  return (
    <>
      <LargeTitle title="Basket" />
      {loading && (
        <>
          <p role="status" className="sr-only">
            Loading…
          </p>
          <BasketSkeleton />
        </>
      )}
      <Status error={error} />
      {error && <RetryButton onRetry={refetch} />}

      {!loading && !error && b && !b.cheapest_store && (
        <EmptyState icon={<ShoppingCart size={52} />} title="Add items to compare stores." primaryLabel="Add items" onPrimary={() => router.push("/list")} />
      )}

      {b?.cheapest_store && bestStore && (
        <>
          <div className="mx-4 mb-6 flex flex-col gap-3 rounded-[20px] border border-tint/25 bg-gradient-to-br from-savings-bg to-elevated p-5 shadow-card">
            <div className="flex items-center justify-between">
              <p className="text-[13px] font-medium tracking-wide text-label-2 uppercase">Best single store</p>
              <span className="flex size-6 items-center justify-center rounded-full bg-tint text-white">
                <CircleCheck size={16} />
              </span>
            </div>
            <p className="text-[28px] font-bold">{b.cheapest_store}</p>
            <p className="text-[34px] font-bold text-tint">{money(bestStore.total)}</p>
            <p className="text-[15px] text-label-2">
              {bestStore.matched} of {totalItems} items on sale
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
