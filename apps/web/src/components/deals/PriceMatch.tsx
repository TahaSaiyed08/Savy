"use client";
// The screen shown to the cashier: price, store, valid dates and the flyer tile, all on one screen. Flipp publishes
// no page images, so a page is rebuilt from each tile's own cutout at its exact position.
import { useEffect, useRef, useState } from "react";
import { Calendar, ChevronLeft, ChevronRight, ExternalLink, Tag } from "@/components/icons";
import { FlyerZoomPane } from "@/components/deals/FlyerZoomPane";
import { PriceTag } from "@/components/PriceTag";
import { Thumb } from "@/components/Thumb";
import { PrimaryButton, Skeleton, money } from "@/components/ui";
import { api, type Schemas } from "@/lib/api";
import { daysLeft, fullName, itemMeta, shortDate, validRange } from "@/lib/format";

export type Listing = {
  pageId: string;
  flyerItemId: string;
  store: string;
  label?: string;
  price?: number | null;
  regularPrice?: number | null;
  unitPrice?: number | null;
  unit?: string | null;
  conditions?: string | null;
  validFrom?: string | null;
  validTo?: string | null;
  imageUrl?: string | null;
  storeUrl?: string | null; // the store's own page for it
};

export type MatchTarget = {
  from: string;
  name: string;
  meta: string;
  listing: Listing | null;
  saves?: number | null;
  closest?: Listing[];
  missing?: string[];
  onAddToPantry?: () => void;
  onAddToBasket?: () => void;
  inPantry?: boolean;
};

export const fromDeal = (d: Schemas["Deal"]): Listing => ({
  pageId: d.page_id, flyerItemId: d.flyer_item_id, store: d.store, label: d.flyer_label, price: d.price,
  regularPrice: d.regular_price, unitPrice: d.unit_price, unit: d.unit, conditions: d.conditions,
  validFrom: d.valid_from, validTo: d.valid_to, imageUrl: d.image_url,
  storeUrl: d.store_url,
});

export const fromListing = (l: Schemas["FlyerListing"]): Listing => ({
  pageId: l.page_id, flyerItemId: l.flyer_item_id, store: l.store, label: l.label, price: l.price,
  regularPrice: l.regular_price, unitPrice: l.unit_price, unit: l.unit, conditions: l.conditions,
  validFrom: l.valid_from, validTo: l.valid_to, imageUrl: l.image_url,
  storeUrl: l.store_url,
});

export const matchFor = (from: string, item: Schemas["ListItem"]): MatchTarget => ({
  from, name: fullName(item), meta: itemMeta(item), listing: item.cheapest ? fromDeal(item.cheapest) : null,
  saves: item.saves_vs_next, closest: item.closest?.map(fromListing), missing: item.missing,
});

function FlyerPage({ pageId, targetId, onPage }: { pageId: string; targetId: string; onPage: (p: Schemas["PageView"]) => void }) {
  const [page, setPage] = useState<Schemas["PageView"] | null>(null);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [settled, setSettled] = useState(false);
  const [aspect, setAspect] = useState<number | null>(null);
  const [imgFailed, setImgFailed] = useState(false); // the real page didn't load: draw the page from its items
  const report = useRef(onPage);
  report.current = onPage;

  useEffect(() => {
    let live = true;
    setFailed(false);
    api
      .GET("/flyer-pages/{page_id}", { params: { path: { page_id: pageId } } })
      .then(({ data }) => {
        if (!live) return;
        if (!data) return setFailed(true);
        setPage(data);
        report.current(data);
      })
      .catch(() => live && setFailed(true));
    return () => {
      live = false;
    };
  }, [pageId, attempt]);

  if (failed) {
    return (
      <div className="absolute inset-0 flex flex-col items-center justify-center gap-1 text-[15px] text-label-2">
        Couldn&apos;t open this flyer.
        <button type="button" onClick={() => setAttempt((n) => n + 1)} className="min-h-tap font-semibold text-tint">
          Retry
        </button>
      </div>
    );
  }

  const tile = page?.tiles.find((t) => t.item_id === targetId);
  const real = !!page?.image_url && !imgFailed; // the printed page itself, when Flipp has it
  const waitsForImage = real || !!tile?.image_url;
  const ready = !!page && (settled || !waitsForImage);
  const box = (b: number[]) => ({
    left: `${b[0] * 100}%`, top: `${b[1] * 100}%`, width: `${(b[2] - b[0]) * 100}%`, height: `${(b[3] - b[1]) * 100}%`,
  });

  return (
    <>
      {!ready && (
        <div className="absolute inset-3" role="status">
          <span className="sr-only">Loading flyer</span>
          <Skeleton className="mx-auto h-full max-w-full rounded-[8px]" />
        </div>
      )}
      {page && (
        <div className={`absolute inset-0 transition-opacity ${ready ? "" : "opacity-0"}`} role="img" aria-label={`${page.store} flyer, page ${page.page_no ?? 1}${tile ? ", deal highlighted" : ""}`}>
          <FlyerZoomPane aspect={page.aspect ?? aspect ?? 0.7} focus={real && !aspect && !page.aspect ? null : tile?.bbox}>
            {real && (
              // eslint-disable-next-line @next/next/no-img-element -- a page from the Volume, proxied through /api
              <img
                src={`/api${page.image_url}`}
                alt=""
                draggable={false}
                onLoad={(e) => {
                  setAspect(e.currentTarget.naturalWidth / e.currentTarget.naturalHeight);
                  setSettled(true);
                }}
                onError={() => {
                  setImgFailed(true);
                  setSettled(false);
                }}
                className="absolute inset-0 size-full"
              />
            )}
            {!real &&
              page.tiles.map((t) => {
                const mine = t.item_id === targetId;
                return (
                  <div key={t.item_id} className="absolute overflow-hidden bg-white" style={box(t.bbox)}>
                    {t.image_url ? (
                      // eslint-disable-next-line @next/next/no-img-element -- remote flyer cutouts
                      <img
                        src={t.image_url}
                        alt=""
                        draggable={false}
                        onLoad={mine ? () => setSettled(true) : undefined}
                        onError={mine ? () => setSettled(true) : undefined}
                        className="size-full object-contain"
                      />
                    ) : (
                      <div className="flex size-full flex-col justify-between border border-black/10 p-1 text-[6px] leading-tight text-black">
                        <span className="line-clamp-3">{t.label}</span>
                        <span className="font-bold">{money(t.price)}</span>
                      </div>
                    )}
                  </div>
                );
              })}
            {tile && (
              <div
                className="pointer-events-none absolute rounded-[2px]"
                style={{ ...box(tile.bbox), boxShadow: "0 0 0 9999px rgb(0 0 0 / 0.4)", outline: "calc(3px / var(--zoom)) solid var(--tint)" }}
              />
            )}
          </FlyerZoomPane>
        </div>
      )}
    </>
  );
}

function FlyerStage({ listing }: { listing: Listing }) {
  const [pageId, setPageId] = useState(listing.pageId);
  const [page, setPage] = useState<Schemas["PageView"] | null>(null);
  const nav = "flex size-11 items-center justify-center text-tint disabled:text-label-2/40";
  return (
    <div className="mx-4 mb-2 flex min-h-0 flex-1 flex-col overflow-hidden rounded-[16px] bg-elevated">
      <div className="relative min-h-0 flex-1 bg-fill">
        <FlyerPage key={pageId} pageId={pageId} targetId={listing.flyerItemId} onPage={setPage} />
      </div>
      <div className="flex shrink-0 items-center justify-between px-1">
        <button type="button" aria-label="Previous page" className={nav} disabled={!page?.prev_page_id} onClick={() => page?.prev_page_id && setPageId(page.prev_page_id)}>
          <ChevronLeft size={20} />
        </button>
        <p className="text-[13px] text-label-2 tabular-nums">{page ? `Page ${page.page_no ?? 1} of ${page.page_count}` : " "}</p>
        <button type="button" aria-label="Next page" className={nav} disabled={!page?.next_page_id} onClick={() => page?.next_page_id && setPageId(page.next_page_id)}>
          <ChevronRight size={20} />
        </button>
      </div>
    </div>
  );
}

function MatchCard({ listing, saves, closestNote }: { listing: Listing; saves?: number | null; closestNote: boolean }) {
  const left = daysLeft(listing.validTo);
  const range = validRange(listing.validFrom, listing.validTo);
  const expired = left != null && left < 0;
  const extra = [listing.conditions, listing.unitPrice != null && listing.unit ? `${money(listing.unitPrice)} / ${listing.unit.replace(/^(\d+)/, "$1 ")}` : null].filter(Boolean).join(" · ");
  return (
    <div className="mx-4 mb-2 flex shrink-0 flex-col gap-1.5 rounded-[16px] bg-elevated p-3.5">
      {expired && listing.validTo && <p className="-mx-1 rounded-[8px] bg-destructive px-2 py-1 text-[13px] font-semibold text-white">Expired {shortDate(listing.validTo)}</p>}
      {closestNote && <p className="text-[13px] text-label-2">Closest match, not your exact item</p>}
      <div className="flex items-center gap-3">
        <Thumb src={listing.imageUrl} />
        <p className="min-w-0 flex-1 truncate text-[17px] font-semibold">{listing.store}</p>
        {listing.storeUrl && ( // the store's own page for the product; never Flipp's
          <a
            href={listing.storeUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="flex min-h-tap shrink-0 items-center gap-1 text-[15px] font-semibold text-label underline underline-offset-[3px]"
          >
            Original flyer
            <ExternalLink size={15} />
            <span className="sr-only">(opens {listing.store}&apos;s site in a new tab)</span>
          </a>
        )}
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <PriceTag price={listing.price} regular={listing.regularPrice} large />
        {!!saves && <span className="rounded-full border border-savings-border bg-savings-bg px-2.5 py-1 text-[13px] font-semibold text-savings-text">{money(saves)} less than next store</span>}
      </div>
      {range && (
        <p className={`flex items-center gap-1.5 text-[15px] ${left != null && left >= 0 && left <= 2 ? "text-clock" : "text-label-2"}`}>
          <Calendar size={15} className="shrink-0" />
          Valid {range}
          {left != null && left >= 0 && ` · ${left === 0 ? "Ends today" : `Ends in ${left} day${left === 1 ? "" : "s"}`}`}
        </p>
      )}
      {extra && <p className="truncate text-[13px] text-label-2">{extra}</p>}
    </div>
  );
}

function PriceMatchScreen({ target, onClose }: { target: MatchTarget; onClose: () => void }) {
  const [picked, setPicked] = useState<Listing | null>(null);
  const listing = target.listing ?? picked;
  const close = useRef(onClose);
  close.current = onClose;

  // A real history entry, so the phone's back gesture leaves this screen rather than the tab. Keeps Next's own state.
  useEffect(() => {
    if (!history.state?.priceMatch) history.pushState({ ...history.state, priceMatch: true }, "");
    const onPop = () => close.current();
    window.addEventListener("popstate", onPop);
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("popstate", onPop);
      document.body.style.overflow = overflow;
    };
  }, []);

  // The cashier may take a moment: keep the screen on while this is open.
  useEffect(() => {
    let lock: WakeLockSentinel | undefined;
    let gone = false;
    navigator.wakeLock
      ?.request("screen")
      .then((l) => {
        if (gone) l.release();
        else lock = l;
      })
      .catch(() => {});
    return () => {
      gone = true;
      lock?.release();
    };
  }, []);

  const back = picked && !target.listing ? () => setPicked(null) : () => history.back();

  return (
    <div className="fixed inset-0 z-40 bg-bg">
      <div className="mx-auto flex h-full max-w-xl flex-col" style={{ paddingTop: "env(safe-area-inset-top)", paddingBottom: "env(safe-area-inset-bottom)" }}>
        <header className="relative flex h-11 shrink-0 items-center">
          <button type="button" onClick={back} className="flex h-11 items-center gap-0.5 pl-2 pr-3 text-[17px] text-label">
            <ChevronLeft size={22} />
            {picked && !target.listing ? "Closest" : target.from}
          </button>
          <h1 className="pointer-events-none absolute inset-x-0 text-center text-[17px] font-semibold">Price match</h1>
        </header>

        <div className="mx-4 mb-2 shrink-0">
          <p className="truncate text-[17px]">{target.name}</p>
          {target.meta && <p className="truncate text-[15px] text-label-2">{target.meta}</p>}
        </div>

        {listing ? (
          <>
            <MatchCard listing={listing} saves={target.saves} closestNote={!target.listing} />
            <FlyerStage key={listing.flyerItemId} listing={listing} />
            <p className="shrink-0 pb-2 text-center text-[12px] text-label-2">Pinch or double-tap to zoom</p>
            {target.onAddToPantry && (
              <div className="flex shrink-0 gap-3 px-4 pb-3">
                <PrimaryButton onClick={target.onAddToPantry} disabled={target.inPantry}>
                  {target.inPantry ? "In pantry" : "Add to pantry"}
                </PrimaryButton>
                <button type="button" onClick={target.onAddToBasket} className="h-[50px] w-full rounded-[14px] bg-fill text-[17px] font-semibold text-label">
                  Add to basket
                </button>
              </div>
            )}
          </>
        ) : (
          <div className="min-h-0 flex-1 overflow-y-auto pb-6">
            <div className="flex flex-col items-center gap-2 px-8 py-8 text-center">
              <Tag size={44} className="text-label-2" />
              <p className="text-[17px] font-semibold">No exact match this week</p>
              <p className="text-[15px] text-label-2">
                {target.closest?.length
                  ? "These are on sale and come close."
                  : "We'll check again when new flyers land on Thursday."}
              </p>
              {!!target.missing?.length && (
                <p className="text-[13px] text-label-2">
                  Add the {new Intl.ListFormat("en", { type: "conjunction" }).format(target.missing)} (swipe it left in
                  Pantry, then Edit) to find your exact product.
                </p>
              )}
            </div>
            {!!target.closest?.length && (
              <section className="mx-4">
                <h2 className="px-3.5 pb-1.5 text-[13px] uppercase text-label-2">Closest this week</h2>
                <ul className="overflow-hidden rounded-[14px] bg-elevated">
                  {target.closest.map((l) => (
                    <li key={l.flyerItemId} className="relative">
                      <button type="button" onClick={() => setPicked(l)} className="row-sep relative flex min-h-[3.75rem] w-full items-center gap-3 px-3.5 py-3 text-left" style={{ "--sep": "70px" } as React.CSSProperties}>
                        <Thumb src={l.imageUrl} />
                        <span className="min-w-0 flex-1">
                          <span className="block truncate">{l.label}</span>
                          <span className="block truncate text-[15px] text-label-2">{l.store}</span>
                        </span>
                        <PriceTag price={l.price} regular={l.regularPrice} />
                      </button>
                    </li>
                  ))}
                </ul>
              </section>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export function PriceMatch({ target, onClose }: { target: MatchTarget | null; onClose: () => void }) {
  return target ? <PriceMatchScreen key={target.listing?.flyerItemId ?? target.name} target={target} onClose={onClose} /> : null;
}
