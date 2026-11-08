"use client";
// Pinch, drag and double-tap/scroll zoom over one flyer page, opening zoomed to `focus`. Hand-rolled with pointer
// events, like SwipeRow: this is the only place that needs it.
import { useEffect, useLayoutEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";

const MAX_SCALE = 8;
const DOUBLE_TAP_SCALE = 2.5;
const FOCUS_PADDING = 24;

type Box = [number, number, number, number] | number[];

export function FlyerZoomPane({ aspect, focus, children }: { aspect: number; focus?: Box | null; children: ReactNode }) {
  const [size, setSize] = useState<{ w: number; h: number } | null>(null);
  const [view, setView] = useState({ scale: 1, x: 0, y: 0 });
  const [live, setLive] = useState(false);
  const paneRef = useRef<HTMLDivElement>(null);
  const pointers = useRef(new Map<number, { x: number; y: number }>());
  const pinch = useRef<{ dist: number; scale: number } | null>(null);
  const pan = useRef<{ x: number; y: number; cx: number; cy: number } | null>(null);
  const lastTap = useRef(0);
  const focused = useRef(false);

  useLayoutEffect(() => {
    const el = paneRef.current!;
    const measure = () => setSize({ w: el.clientWidth, h: el.clientHeight });
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const pageH = size ? Math.min(size.h, size.w / aspect) : 0;
  const pageW = pageH * aspect;

  function clamp(scale: number, x: number, y: number) {
    if (!size) return { scale, x, y };
    const maxX = Math.max(0, (pageW * scale - size.w) / 2);
    const maxY = Math.max(0, (pageH * scale - size.h) / 2);
    return { scale, x: Math.max(-maxX, Math.min(maxX, x)), y: Math.max(-maxY, Math.min(maxY, y)) };
  }

  useLayoutEffect(() => {
    if (!size || !focus || focused.current) return;
    focused.current = true;
    const [x0, y0, x1, y1] = focus;
    const fit = Math.min((size.w - FOCUS_PADDING * 2) / ((x1 - x0) * pageW), (size.h - FOCUS_PADDING * 2) / ((y1 - y0) * pageH));
    const scale = Math.max(1, Math.min(MAX_SCALE, fit));
    setView(clamp(scale, -((x0 + x1) / 2 - 0.5) * pageW * scale, -((y0 + y1) / 2 - 0.5) * pageH * scale));
    // eslint-disable-next-line react-hooks/exhaustive-deps -- runs once, when the pane is first measured
  }, [size, focus]);

  function zoomTo(next: number, cx: number, cy: number) {
    setView((v) => {
      const scale = Math.max(1, Math.min(MAX_SCALE, next));
      const rect = paneRef.current!.getBoundingClientRect();
      const ax = cx - rect.left - rect.width / 2;
      const ay = cy - rect.top - rect.height / 2;
      return clamp(scale, ax - ((ax - v.x) / v.scale) * scale, ay - ((ay - v.y) / v.scale) * scale);
    });
  }

  const wheel = useRef<(e: WheelEvent) => void>(() => {});
  wheel.current = (e) => {
    e.preventDefault();
    zoomTo(view.scale * (1 - e.deltaY * 0.01), e.clientX, e.clientY);
  };
  useEffect(() => {
    const el = paneRef.current!;
    const onWheel = (e: WheelEvent) => wheel.current(e);
    el.addEventListener("wheel", onWheel, { passive: false }); // React's own wheel listener can't preventDefault
    return () => el.removeEventListener("wheel", onWheel);
  }, []);

  function onPointerDown(e: React.PointerEvent) {
    (e.currentTarget as Element).setPointerCapture(e.pointerId);
    pointers.current.set(e.pointerId, { x: e.clientX, y: e.clientY });
    setLive(true);
    if (pointers.current.size === 2) {
      const [a, b] = [...pointers.current.values()];
      pinch.current = { dist: Math.hypot(a.x - b.x, a.y - b.y), scale: view.scale };
      pan.current = null;
    } else if (pointers.current.size === 1) {
      pan.current = { x: view.x, y: view.y, cx: e.clientX, cy: e.clientY };
      const now = Date.now();
      if (now - lastTap.current < 300) {
        zoomTo(view.scale > 1 ? 1 : DOUBLE_TAP_SCALE, e.clientX, e.clientY);
        lastTap.current = 0;
      } else {
        lastTap.current = now;
      }
    }
  }
  function onPointerMove(e: React.PointerEvent) {
    if (!pointers.current.has(e.pointerId)) return;
    pointers.current.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (pointers.current.size === 2 && pinch.current) {
      const [a, b] = [...pointers.current.values()];
      zoomTo(pinch.current.scale * (Math.hypot(a.x - b.x, a.y - b.y) / pinch.current.dist), (a.x + b.x) / 2, (a.y + b.y) / 2);
    } else if (pan.current) {
      const p = pan.current;
      setView((v) => clamp(v.scale, p.x + e.clientX - p.cx, p.y + e.clientY - p.cy));
    }
  }
  function endPointer(e: React.PointerEvent) {
    pointers.current.delete(e.pointerId);
    if (pointers.current.size < 2) pinch.current = null;
    if (pointers.current.size === 1) {
      const [p] = [...pointers.current.values()];
      pan.current = { x: view.x, y: view.y, cx: p.x, cy: p.y };
    } else {
      pan.current = null;
    }
    if (pointers.current.size === 0) setLive(false);
  }

  return (
    <div
      ref={paneRef}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={endPointer}
      onPointerCancel={endPointer}
      className="absolute inset-0 touch-none select-none overflow-hidden"
    >
      {size && (
        <div
          style={{
            width: pageW,
            height: pageH,
            left: (size.w - pageW) / 2,
            top: (size.h - pageH) / 2,
            transform: `translate(${view.x}px, ${view.y}px) scale(${view.scale})`,
            transition: live ? "none" : "transform 200ms",
            "--zoom": view.scale,
          } as CSSProperties}
          className="absolute overflow-hidden bg-white"
        >
          {children}
        </div>
      )}
    </div>
  );
}
