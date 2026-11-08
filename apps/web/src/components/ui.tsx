// HIG building blocks. Component list (frozen interface with Design): LargeTitle, InsetGroup, Row, Status,
// TabBar, plus the sheet-era additions below (EmptyState, Chip, PrimaryButton, FieldRow, UnitPicker). Design
// changes the look via tokens in globals.css; Frontend keeps these props stable.
import type { ReactNode } from "react";
import { Loader } from "@/components/icons";

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
      <ul className="overflow-hidden rounded-[20px] bg-elevated shadow-card">
        {children}
      </ul>
      {footer && <p className="px-4 pt-1.5 text-[0.8125rem] text-label-2">{footer}</p>}
    </section>
  );
}

export function Row({
  title,
  subtitle,
  detail,
  accent,
  destructive,
  leading,
  trailing,
  onClick,
}: {
  title: string;
  subtitle?: string;
  detail?: string;
  accent?: boolean;
  destructive?: boolean;
  leading?: ReactNode;
  trailing?: ReactNode;
  onClick?: () => void;
}) {
  const Tag = onClick ? "button" : "div";
  return (
    <li className="flex min-h-tap items-center gap-3 pl-4 [&:not(:last-child)>div]:border-b [&>div]:border-separator">
      <Tag
        onClick={onClick}
        type={onClick ? "button" : undefined}
        className="flex min-h-tap flex-1 items-center gap-3 py-2.5 pr-4 text-left"
      >
        {leading}
        <div className="min-w-0 flex-1">
          <p className={`truncate ${destructive ? "text-destructive" : ""}`}>{title}</p>
          {subtitle && <p className="truncate text-[0.9375rem] text-label-2">{subtitle}</p>}
        </div>
        {detail && <span className={accent ? "font-semibold text-tint" : "text-label-2"}>{detail}</span>}
        {trailing}
      </Tag>
    </li>
  );
}

export function Status({ loading, error, empty }: { loading?: boolean; error?: string; empty?: string }) {
  const text = loading ? "Loading…" : error ?? empty;
  return text ? <p className="px-8 py-12 text-center text-label-2">{text}</p> : null;
}

export function EmptyState({
  icon,
  title,
  subtitle,
  primaryLabel,
  onPrimary,
  secondaryLabel,
  onSecondary,
}: {
  icon: ReactNode;
  title: string;
  subtitle?: string;
  primaryLabel?: string;
  onPrimary?: () => void;
  secondaryLabel?: string;
  onSecondary?: () => void;
}) {
  return (
    <div className="flex min-h-[28rem] flex-col items-center justify-center gap-6 px-8 text-center">
      <div className="text-tint">{icon}</div>
      <div className="flex flex-col items-center gap-2">
        <p className="text-[17px] font-semibold">{title}</p>
        {subtitle && <p className="text-[15px] text-label-2">{subtitle}</p>}
      </div>
      {(primaryLabel || secondaryLabel) && (
        <div className="flex w-full flex-col gap-3">
          {primaryLabel && (
            <PrimaryButton onClick={onPrimary}>{primaryLabel}</PrimaryButton>
          )}
          {secondaryLabel && (
            <button type="button" onClick={onSecondary} className="flex h-tap items-center justify-center text-[15px] font-medium text-tint">
              {secondaryLabel}
            </button>
          )}
        </div>
      )}
    </div>
  );
}

export function PrimaryButton({
  children,
  onClick,
  disabled,
  loading,
  type = "button",
}: {
  children: ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  loading?: boolean;
  type?: "button" | "submit";
}) {
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled || loading}
      className="flex h-[50px] w-full items-center justify-center gap-2 rounded-[14px] bg-tint text-[17px] font-semibold text-white shadow-tint transition-opacity disabled:opacity-40"
    >
      {loading && <Loader size={18} />}
      {children}
    </button>
  );
}

export function Chip({
  label,
  selected,
  onClick,
}: {
  label: string;
  selected?: boolean;
  onClick?: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={selected}
      className={`flex h-tap shrink-0 items-center whitespace-nowrap rounded-full px-4 text-[15px] transition-colors ${
        selected ? "bg-tint font-semibold text-white shadow-tint" : "border border-separator bg-elevated text-label"
      }`}
    >
      {label}
    </button>
  );
}

export const UNITS = ["g", "kg", "ml", "l", "lb", "ea"];

export function UnitPicker({ value, onChange, units = UNITS }: { value: string; onChange: (u: string) => void; units?: string[] }) {
  return (
    <div className="flex gap-0.5 rounded-xl bg-bg p-0.5">
      {units.map((u) => (
        <button
          key={u}
          type="button"
          onClick={() => onChange(u)}
          aria-pressed={value === u}
          className={`flex h-tap flex-1 items-center justify-center rounded-[10px] text-[15px] transition-colors ${
            value === u ? "bg-tint font-semibold text-white" : "text-label-2"
          }`}
        >
          {u}
        </button>
      ))}
    </div>
  );
}

export function FieldRow({
  label,
  value,
  onChange,
  placeholder,
}: {
  label: string;
  value: string;
  onChange?: (v: string) => void;
  placeholder?: string;
}) {
  return (
    <div className="flex min-h-[52px] items-center gap-4 border-b border-separator/60 px-4 py-3 last:border-b-0">
      <p className="w-[85px] shrink-0 text-[17px] font-medium text-label-2">{label}</p>
      {onChange ? (
        <input
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          className="min-w-0 flex-1 bg-transparent text-[17px] text-label outline-none placeholder:text-label-2"
        />
      ) : (
        <p className="min-w-0 flex-1 truncate text-[17px]">{value || <span className="text-label-2">{placeholder}</span>}</p>
      )}
    </div>
  );
}

export const money = (n?: number | null) => (n == null ? "—" : `$${n.toFixed(2)}`);
