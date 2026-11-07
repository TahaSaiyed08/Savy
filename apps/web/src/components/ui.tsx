// HIG building blocks. Component list (frozen interface with Design): LargeTitle, InsetGroup, Row, Status,
// TabBar. Design changes the look via tokens in globals.css; Frontend keeps these props stable.
import type { ReactNode } from "react";

export function LargeTitle({ title, action }: { title: string; action?: ReactNode }) {
  return (
    <header className="flex items-end justify-between px-4 pt-[calc(env(safe-area-inset-top)+1.5rem)] pb-2">
      <h1 className="text-[2.125rem] leading-tight font-bold tracking-tight">{title}</h1>
      {action}
    </header>
  );
}

export function InsetGroup({ header, footer, children }: { header?: string; footer?: string; children: ReactNode }) {
  return (
    <section className="mx-4 mb-6">
      {header && <h2 className="px-4 pb-1.5 text-[0.8125rem] uppercase text-label-2">{header}</h2>}
      <ul className="overflow-hidden rounded-[10px] bg-elevated">{children}</ul>
      {footer && <p className="px-4 pt-1.5 text-[0.8125rem] text-label-2">{footer}</p>}
    </section>
  );
}

export function Row({ title, subtitle, detail, accent }: {
  title: string; subtitle?: string; detail?: string; accent?: boolean;
}) {
  return (
    <li className="flex min-h-tap items-center gap-3 pl-4 [&:not(:last-child)>div]:border-b [&>div]:border-separator">
      <div className="flex min-h-tap flex-1 items-center gap-3 py-2.5 pr-4">
        <div className="min-w-0 flex-1">
          <p className="truncate">{title}</p>
          {subtitle && <p className="truncate text-[0.9375rem] text-label-2">{subtitle}</p>}
        </div>
        {detail && <span className={accent ? "font-semibold text-tint" : "text-label-2"}>{detail}</span>}
      </div>
    </li>
  );
}

export function Status({ loading, error, empty }: { loading?: boolean; error?: string; empty?: string }) {
  const text = loading ? "Loading…" : error ?? empty;
  return text ? <p className="px-8 py-12 text-center text-label-2">{text}</p> : null;
}

export const money = (n?: number | null) => (n == null ? "—" : `$${n.toFixed(2)}`);
