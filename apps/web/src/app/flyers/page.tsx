"use client";
// Every item on sale in a current flyer, one row per product at its cheapest store. Tapping a row opens the same
// Price Match screen as Pantry and Basket.
import { useCallback, useEffect, useRef, useState } from "react";
import { PriceMatch, fromListing, type MatchTarget } from "@/components/deals/PriceMatch";
import { Check, CirclePlus, Clock, MapPin, Tag } from "@/components/icons";
import { AskButton, AskSheet } from "@/components/AskSheet";
import { LocationSheet } from "@/components/LocationSheet";
import { PriceTag } from "@/components/PriceTag";
import { Thumb } from "@/components/Thumb";
import { useToast } from "@/components/Toast";
import { Chip, EmptyState, LargeTitle, ListSkeleton, RetryButton, SearchField, SkeletonRow, Status, money } from "@/components/ui";
import { api, type Schemas } from "@/lib/api";
import { daysLeft, fullName, itemMeta, weekday } from "@/lib/format";
import { formatPostal, setPostal } from "@/lib/postal";
import { useItems } from "@/lib/use-items";

const PAGE_SIZE = 30;
const ALL = "All";
const SORTS = [
  ["savings", "Biggest savings"],
  ["price", "Price"],
  ["ends", "Ends soon"],
  ["az", "A–Z"],
  ["relevance", "Best match"], // only offered while searching
] as const;
type Sort = (typeof SORTS)[number][0];
type Group = Schemas["FlyerGroup"];

const identity = (x: Pick<Group, "brand" | "item" | "variant" | "size_qty">) => [x.brand, x.item, x.variant, x.size_qty].join("|").toLowerCase();

function Ends({ validTo }: { validTo?: string | null }) {
  if (!validTo) return null;
  const left = daysLeft(validTo);
  const soon = left != null && left >= 0 && left <= 2;
  return (
    <span className={soon ? "inline-flex items-center gap-1 text-clock" : ""}>
      {soon && <Clock size={12} />}
      Until {weekday(validTo)}
    </span>
  );
}

export default function Flyers() {
  const { items, addItems, setBasket } = useItems();
  const [query, setQuery] = useState("");
  const [store, setStore] = useState(ALL);
  const [chosenSort, setSort] = useState<Sort | null>(null);
  // Searching defaults to best match: "Biggest savings" puts peanut butter and jam above actual butter.
  const sort: Sort = query.trim() ? (chosenSort ?? "relevance") : chosenSort === "relevance" || !chosenSort ? "savings" : chosenSort;
  const [groups, setGroups] = useState<Group[]>([]);
  const [stores, setStores] = useState<string[]>([]);
  const [category, setCategory] = useState(ALL);
  const [categories, setCategories] = useState<string[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [state, setState] = useState<"replacing" | "more" | "idle">("replacing");
  const [error, setError] = useState<"first" | "more" | null>(null);
  const [match, setMatch] = useState<MatchTarget | null>(null);
  const [place, setPlace] = useState<Schemas["FlyersStatus"] | null>(null);
  const [picking, setPicking] = useState(false);
  const [asking, setAsking] = useState(false);
  const [fetching, setFetching] = useState(false);
  const toast = useToast();
  const requestId = useRef(0);
  const sentinel = useRef<HTMLDivElement>(null);

  const load = useCallback(
    (next: number) => {
      const id = ++requestId.current;
      const append = next > 1;
      setState(append ? "more" : "replacing");
      setError(null);
      api
        .GET("/flyer-items", {
          params: {
            query: {
              q: query || undefined,
              store: store === ALL ? undefined : store,
              category: category === ALL ? undefined : category,
              sort,
              page: next,
              page_size: PAGE_SIZE,
            },
          },
        })
        .then(({ data }) => {
          if (id !== requestId.current) return;
          if (!data) throw new Error("no data");
          setPage(data.page);
          setTotal(data.total);
          setStores(data.stores);
          setCategories(data.categories);
          setFetching(!data.ready);
          setGroups((prev) => (append ? [...prev, ...data.items] : data.items));
          setState("idle");
        })
        .catch(() => {
          if (id !== requestId.current) return;
          setError(append ? "more" : "first");
          setState("idle");
        });
    },
    [query, store, category, sort],
  );

  useEffect(() => {
    const t = setTimeout(() => load(1), query ? 300 : 0);
    return () => clearTimeout(t);
  }, [load, query]);

  const refreshStatus = useCallback(() => api.GET("/flyers/status").then(({ data }) => data && setPlace(data)).catch(() => {}), []);
  useEffect(() => {
    refreshStatus();
  }, [refreshStatus]);

  // The first download for a new area takes about 30 s: ask again until it lands, then show the list.
  useEffect(() => {
    if (!fetching) return;
    const timer = setInterval(async () => {
      const { data } = await api.GET("/flyers/status").catch(() => ({ data: undefined }));
      if (data?.ready) {
        setPlace(data);
        load(1);
      }
    }, 3000);
    return () => clearInterval(timer);
  }, [fetching, load]);

  function moveTo(postal: string) {
    setPicking(false);
    setPostal(postal);
    setStore(ALL);
    setCategory(ALL);
    setQuery("");
    refreshStatus();
    load(1);
  }

  const hasMore = groups.length < total;
  useEffect(() => {
    if (state !== "idle" || !hasMore || error) return;
    const el = sentinel.current;
    if (!el) return;
    const io = new IntersectionObserver(([e]) => e.isIntersecting && load(page + 1), { rootMargin: "400px" });
    io.observe(el);
    return () => io.disconnect();
  }, [state, hasMore, error, page, load]);

  const inPantry = (g: Group) => !!items?.some((i) => identity(i) === identity(g));

  async function add(g: Group, toBasket = false) {
    try {
      const existing = items?.find((i) => identity(i) === identity(g));
      const saved = existing ?? (await addItems({ source: "flyer", items: [{ brand: g.brand, item: g.item, variant: g.variant, size_qty: g.size_qty, size_unit: g.size_unit, confidence: 1 }] }))[0];
      if (toBasket) await setBasket(saved.user_item_id, true);
      toast.show(toBasket ? "Added to basket" : "Added to pantry");
    } catch {
      toast.show("Couldn't add that item");
    }
  }

  function open(g: Group) {
    setMatch({
      from: "Flyers", name: fullName(g), meta: itemMeta(g), listing: fromListing(g.cheapest), saves: g.saves_vs_next,
      inPantry: inPantry(g), onAddToPantry: () => add(g).then(() => setMatch((m) => m && { ...m, inPantry: true })),
      onAddToBasket: () => add(g, true).then(() => setMatch((m) => m && { ...m, inPantry: true })),
    });
  }

  const replacing = state === "replacing";
  return (
    <>
      <LargeTitle
        title="Flyers"
        action={
          <div className="flex items-center gap-2">
            {place?.ask_enabled && <AskButton onClick={() => setAsking(true)} />}
            <button type="button" onClick={() => setPicking(true)} aria-label="Change flyer location" className="mb-1 flex min-h-tap items-center gap-1 rounded-full bg-fill px-3 text-[15px] font-medium text-tint">
              <MapPin size={16} />
              {place ? formatPostal(place.postal) : "Location"}
            </button>
          </div>
        }
      />
      <SearchField value={query} onChange={setQuery} placeholder="Search deals" />
      <div className="flex gap-2 overflow-x-auto px-4 pb-2">
        {[ALL, ...stores].map((s) => (
          <Chip key={s} label={s} selected={store === s} onClick={() => setStore(s)} />
        ))}
      </div>
      {categories.length > 0 && (
        <div role="group" aria-label="Categories" className="flex gap-2 overflow-x-auto px-4 pb-2">
          {["Everything", ...categories].map((c) => (
            <Chip key={c} label={c} selected={(c === "Everything" ? ALL : c) === category} onClick={() => setCategory(c === "Everything" ? ALL : c)} />
          ))}
        </div>
      )}
      <label className="flex items-center gap-1 px-4 pb-2 text-[13px] text-label-2">
        Sort:
        <select value={sort} onChange={(e) => setSort(e.target.value as Sort)} className="min-h-tap bg-transparent text-[13px] font-semibold text-tint outline-none">
          {SORTS.filter(([v]) => v !== "relevance" || query.trim()).map(([v, l]) => (
            <option key={v} value={v}>
              {l}
            </option>
          ))}
        </select>
      </label>

      {fetching && (
        <p role="status" className="px-6 pb-3 text-center text-[15px] text-label-2">
          Fetching this week&apos;s flyers{place ? ` near ${formatPostal(place.postal)}` : ""}. The first time takes about 30 seconds.
        </p>
      )}
      {(replacing || fetching) && <ListSkeleton rows={8} />}
      {error === "first" && (
        <>
          <Status error="Couldn't load deals" />
          <RetryButton onRetry={() => load(1)} />
        </>
      )}
      {!replacing && !fetching && !error && groups.length === 0 && (
        <EmptyState
          icon={<Tag size={52} />}
          title={query ? `No deals for "${query}"` : "No flyers found here"}
          subtitle={query ? "Try a different name or brand." : "Try a nearby postal code, or check back Thursday when new flyers land."}
        />
      )}

      {!replacing && !fetching && groups.length > 0 && (
        <section className="mx-4 mb-6">
          <h2 className="px-3.5 pb-1.5 text-[13px] uppercase text-label-2">{total} on sale</h2>
          <ul className="overflow-hidden rounded-[14px] bg-elevated">
            {groups.map((g) => {
              const added = inPantry(g);
              const meta = itemMeta(g);
              return (
                <li key={g.cheapest.flyer_item_id} className="row-sep relative flex items-center" style={{ "--sep": "70px" } as React.CSSProperties}>
                  <button type="button" onClick={() => open(g)} className="flex min-h-[3.75rem] min-w-0 flex-1 items-center gap-3 py-3 pl-3.5 text-left">
                    <Thumb src={g.cheapest.image_url} />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate">{g.item}</span>
                      {meta && <span className="block truncate text-[15px] text-label-2">{meta}</span>}
                      <span className="block truncate text-[13px] text-label-2">
                        {g.cheapest.store} · <Ends validTo={g.cheapest.valid_to} />
                        {!!g.saves_vs_next && <span className="font-semibold text-tint"> · {money(g.saves_vs_next)} less</span>}
                      </span>
                    </span>
                    <PriceTag price={g.cheapest.price} regular={g.cheapest.regular_price} />
                  </button>
                  <button
                    type="button"
                    disabled={added}
                    onClick={() => add(g)}
                    aria-label={added ? `${fullName(g)} is in your pantry` : `Add ${fullName(g)} to pantry`}
                    className="flex size-11 shrink-0 items-center justify-center text-tint"
                  >
                    {added ? <Check size={22} /> : <CirclePlus size={24} />}
                  </button>
                </li>
              );
            })}
            {state === "more" && [0, 1, 2].map((i) => <SkeletonRow key={i} />)}
          </ul>
          <div ref={sentinel} />
          {error === "more" && (
            <p className="flex items-center justify-center gap-2 pt-2 text-[13px] text-label-2">
              Couldn&apos;t load more deals.
              <button type="button" onClick={() => load(page + 1)} className="min-h-tap font-semibold text-tint">
                Retry
              </button>
            </p>
          )}
          {!hasMore && !error && <p className="pt-3 text-center text-[13px] text-label-2">You&apos;ve seen every deal this week.</p>}
        </section>
      )}

      {place?.fetched_at && !fetching && (
        <p className="pb-6 text-center text-[12px] text-label-2">
          Flyers updated {new Date(place.fetched_at).toLocaleString("en-CA", { weekday: "short", hour: "numeric", minute: "2-digit" })}
        </p>
      )}
      {asking && <AskSheet open onClose={() => setAsking(false)} />}
      {picking && <LocationSheet open current={place?.postal ?? null} onClose={() => setPicking(false)} onSave={moveTo} />}
      {toast.node}
      <PriceMatch target={match} onClose={() => setMatch(null)} />
    </>
  );
}
