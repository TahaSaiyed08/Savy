"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { List, ShoppingCart, Tag } from "@/components/icons";

const TABS = [
  { href: "/list", label: "My List", Icon: List },
  { href: "/deals", label: "Deals", Icon: Tag },
  { href: "/basket", label: "Basket", Icon: ShoppingCart },
];

export function TabBar() {
  const path = usePathname();
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
                <t.Icon size={26} />
                {t.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
