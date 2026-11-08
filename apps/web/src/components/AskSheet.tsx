"use client";
import { useRef, useState } from "react";
import { Sheet } from "@/components/Sheet";
import { Skeleton } from "@/components/ui";
import { Sparkles } from "@/components/icons";
import { api, type Schemas } from "@/lib/api";

const EXAMPLES = ["What's the cheapest milk this week?", "Which store has the cheapest eggs?", "Biggest discounts at No Frills", "Compare bread prices"];

type Turn = { question: string; answer?: Schemas["AskResponse"]; error?: string };

/** Genie writes **bold** in its answers; show it as bold, not as literal asterisks. Unpaired asterisks are left alone. */
function Rich({ text }: { text: string }) {
  const parts = text.split("**");
  if (parts.length % 2 === 0) return <>{text}</>;
  return <>{parts.map((part, i) => (i % 2 ? <strong key={i}>{part}</strong> : part))}</>;
}

/** Plain-language questions about this week's flyers, answered by Databricks Genie. */
export function AskSheet({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [text, setText] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [busy, setBusy] = useState(false);
  const conversation = useRef<string | undefined>(undefined);

  async function send(question: string) {
    const q = question.trim();
    if (q.length < 2 || busy) return;
    setText("");
    setBusy(true);
    setTurns((t) => [...t, { question: q }]);
    const fail = (error: string) => setTurns((t) => t.map((x, i) => (i === t.length - 1 ? { ...x, error } : x)));
    try {
      const { data, error, response } = await api.POST("/ask", { body: { question: q, conversation_id: conversation.current } });
      if (data) {
        conversation.current = data.conversation_id;
        setTurns((t) => t.map((x, i) => (i === t.length - 1 ? { ...x, answer: data } : x)));
      } else if (response?.status === 429) {
        fail("You've asked a lot of questions. Try again in a while.");
      } else {
        const detail = (error as { detail?: unknown } | undefined)?.detail;
        fail(typeof detail === "string" ? detail : "Couldn't get an answer. Try again.");
      }
    } catch {
      fail("You seem to be offline. Try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Sheet open={open} onClose={onClose} title="Ask about deals" tall action={<span className="w-[72px]" />}>
      <div className="flex min-h-full flex-col gap-4 px-4 pb-6 pt-2">
        {turns.length === 0 && (
          <div className="flex flex-col gap-3">
            <p className="text-[15px] text-label-2">Ask in your own words. Genie reads this week&apos;s flyers near you and works out the answer.</p>
            <div className="flex flex-wrap gap-2">
              {EXAMPLES.map((e) => (
                <button key={e} type="button" onClick={() => send(e)} className="min-h-tap rounded-full bg-fill px-3.5 text-left text-[15px] text-tint">
                  {e}
                </button>
              ))}
            </div>
          </div>
        )}

        {turns.map((t, n) => (
          <div key={n} className="flex flex-col gap-2">
            <p className="self-end rounded-[16px] bg-tint px-3.5 py-2 text-[15px] text-on-tint">{t.question}</p>
            {!t.answer && !t.error && (
              <div role="status" className="flex flex-col gap-2 rounded-[16px] bg-elevated p-3.5">
                <span className="sr-only">Genie is working on it</span>
                <Skeleton className="h-3 w-4/5" />
                <Skeleton className="h-3 w-3/5" />
                <p className="pt-1 text-[13px] text-label-2">Genie is working on it. The first question can take up to a minute while the warehouse wakes up.</p>
              </div>
            )}
            {t.error && <p className="rounded-[16px] bg-elevated p-3.5 text-[15px] text-destructive">{t.error}</p>}
            {t.answer && (
              <div className="flex flex-col gap-3 rounded-[16px] bg-elevated p-3.5">
                {t.answer.answer && <p className="text-[15px]"><Rich text={t.answer.answer} /></p>}
                {!t.answer.answer && t.answer.description && <p className="text-[15px]"><Rich text={t.answer.description} /></p>}
                {t.answer.rows.length > 0 && (
                  <div className="-mx-1 overflow-x-auto">
                    <table className="w-full min-w-max border-collapse text-left text-[13px] tabular-nums">
                      <thead>
                        <tr>
                          {t.answer.columns.map((c) => (
                            <th key={c} className="whitespace-nowrap px-2 pb-1.5 font-semibold text-label-2">
                              {c.replaceAll("_", " ")}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {t.answer.rows.map((row, i) => (
                          <tr key={i} className="border-t border-separator">
                            {row.map((v, j) => (
                              <td key={j} className="whitespace-nowrap px-2 py-1.5">
                                {v ?? "—"}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
                {t.answer.sql && (
                  <details className="text-[13px]">
                    <summary className="min-h-tap cursor-pointer py-2 text-tint">Show the SQL Genie wrote</summary>
                    <pre className="overflow-x-auto rounded-[10px] bg-fill p-3 text-[12px] leading-snug">{t.answer.sql}</pre>
                  </details>
                )}
              </div>
            )}
          </div>
        ))}

        <form
          className="sticky bottom-0 mt-auto flex items-center gap-2 bg-bg pt-2"
          onSubmit={(e) => {
            e.preventDefault();
            send(text);
          }}
        >
          <label className="sr-only" htmlFor="ask-input">
            Ask about this week&apos;s deals
          </label>
          <input
            id="ask-input"
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Ask about this week's deals"
            maxLength={300}
            className="min-w-0 flex-1 rounded-full bg-fill px-4 py-3 text-[17px] outline-none placeholder:text-label-2"
          />
          <button type="submit" disabled={busy || text.trim().length < 2} className="flex min-h-tap shrink-0 items-center px-2 text-[17px] font-semibold text-tint disabled:opacity-40">
            Ask
          </button>
        </form>
      </div>
    </Sheet>
  );
}

export function AskButton({ onClick }: { onClick: () => void }) {
  return (
    <button type="button" onClick={onClick} aria-label="Ask about deals" className="mb-1 flex min-h-tap items-center gap-1 rounded-full bg-fill px-3 text-[15px] font-medium text-tint">
      <Sparkles size={16} />
      Ask
    </button>
  );
}
