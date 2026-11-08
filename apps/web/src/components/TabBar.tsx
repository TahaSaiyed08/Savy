"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { List, ShoppingCart, Tag } from "@/components/icons";
import { useBasketCount } from "@/lib/use-items";

// Three tabs, each a list of items: Pantry is every item ever added; Basket is the ones moved there
// (still shown in Pantry too); Flyers is every item on sale in a current flyer, searchable. Adding items
// stays on Pantry's own + button, not a tab.
const TABS = [
  { href: "/list", label: "Pantry", Icon: List },
  { href: "/basket", label: "Basket", Icon: ShoppingCart },
  { href: "/flyers", label: "Flyers", Icon: Tag },
];

export function TabBar() {
  const path = usePathname();
  const basketLeft = useBasketCount();
  return (
    <nav className="fixed inset-x-0 bottom-0 z-10 border-t border-separator bg-elevated/85 pb-[env(safe-area-inset-bottom)] backdrop-blur-xl">
      <ul className="mx-auto flex max-w-xl">
        {TABS.map((t) => {
          const on = path.startsWith(t.href);
          return (
            <li key={t.href} className="flex-1">
              <Link
                href={t.href}
                aria-current={on ? "page" : undefined}
                className={`flex min-h-tap flex-col items-center justify-center gap-0.5 pt-1.5 text-[0.625rem] font-medium transition-colors duration-150 ${on ? "text-tint" : "text-label-2"}`}
              >
                <span className="relative">
                  <t.Icon size={26} />
                  {t.href === "/basket" && basketLeft > 0 && (
                    <span aria-label={`${basketLeft} left`} className="absolute -right-2 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-destructive px-1 text-[10px] font-bold text-white tabular-nums">
                      {basketLeft}
                    </span>
                  )}
                </span>
                {t.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
