"use client";
import { useState } from "react";
import { Sheet } from "@/components/Sheet";
import { PrimaryButton } from "@/components/ui";
import { formatPostal, normalizePostal } from "@/lib/postal";

/** Asks for a postal code. Flyers and prices come from the stores around it. */
export function LocationSheet({
  open,
  current,
  onClose,
  onSave,
}: {
  open: boolean;
  current: string | null;
  onClose: () => void;
  onSave: (postal: string) => void;
}) {
  const [text, setText] = useState(current ? formatPostal(current) : "");
  const [error, setError] = useState(false);

  function save() {
    const code = normalizePostal(text);
    if (!code) return setError(true);
    onSave(code);
  }

  return (
    <Sheet open={open} onClose={onClose} title="Flyer location" action={<span className="w-[72px]" />}>
      <form
        className="flex flex-col gap-4 px-4 pb-6 pt-2"
        onSubmit={(e) => {
          e.preventDefault();
          save();
        }}
      >
        <p className="text-[15px] text-label-2">Flyers and prices come from the grocery stores around this postal code.</p>
        <label className="flex flex-col gap-1.5">
          <span className="text-[13px] uppercase text-label-2">Postal code</span>
          <input
            value={text}
            onChange={(e) => {
              setText(e.target.value);
              setError(false);
            }}
            placeholder="V6T 1Z4"
            autoComplete="postal-code"
            autoCapitalize="characters"
            inputMode="text"
            aria-invalid={error}
            className="rounded-[10px] bg-fill px-3 py-3 text-[17px] uppercase outline-none placeholder:text-label-2"
          />
          {error && <span role="alert" className="text-[13px] text-destructive">Enter a postal code like V6T 1Z4.</span>}
        </label>
        <PrimaryButton type="submit">Show flyers near here</PrimaryButton>
        <p className="text-center text-[13px] text-label-2">The first time for a new area takes about 30 seconds.</p>
      </form>
    </Sheet>
  );
}
