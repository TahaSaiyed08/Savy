import { storeColorVar } from "@/lib/store";

/** Small colored dot before a store name. Decorative: the store name is always written beside it. */
export function StoreDot({ store }: { store?: string | null }) {
  return <span aria-hidden className="mr-1.5 inline-block size-2 shrink-0 rounded-full align-[0.05em]" style={{ background: storeColorVar(store) }} />;
}
