"use client";

import { Children, Fragment, isValidElement, useCallback, useEffect, useId, useMemo, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";

/**
 * Drop-in replacement for a native <select>. Keep writing <option> children and an
 * onChange that reads event.target.value; the browser's default popup is replaced by a
 * styled listbox (a bottom sheet on phones). A visually hidden native <select> mirrors the
 * value so form validation (`required`) and `name` keep working.
 */

type Option = { value: string; label: string; disabled: boolean };
export type SelectChangeEvent = { target: { value: string; name: string }; currentTarget: { value: string; name: string } };

export type SelectProps = {
  value?: string | number | null;
  onChange?: (event: SelectChangeEvent) => void;
  children?: ReactNode;
  className?: string;
  id?: string;
  name?: string;
  disabled?: boolean;
  required?: boolean;
  title?: string;
  "aria-label"?: string;
  "aria-labelledby"?: string;
};

function textOf(node: ReactNode): string {
  if (node === null || node === undefined || typeof node === "boolean") return "";
  if (typeof node === "string" || typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(textOf).join("");
  if (isValidElement(node)) return textOf((node.props as { children?: ReactNode }).children);
  return "";
}

function collect(children: ReactNode, out: Option[]) {
  Children.forEach(children, (child) => {
    if (!isValidElement(child)) return;
    const props = child.props as { value?: string | number; children?: ReactNode; disabled?: boolean };
    if (child.type === "option") {
      const label = textOf(props.children);
      out.push({ value: props.value !== undefined ? String(props.value) : label, label, disabled: Boolean(props.disabled) });
    } else if (child.type === Fragment || child.type === "optgroup") {
      collect(props.children, out);
    }
  });
}

type Placement = { sheet: boolean; left: number; width: number; top?: number; bottom?: number; maxHeight: number };

function Chevron({ open }: { open: boolean }) {
  return (
    <svg className={`ui-select-chevron${open ? " is-open" : ""}`} viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="m6 9 6 6 6-6" /></svg>
  );
}

export function Select({ value, onChange, children, className = "", id, name = "", disabled, required, title, ...aria }: SelectProps) {
  const options = useMemo(() => { const list: Option[] = []; collect(children, list); return list; }, [children]);
  const current = value === null || value === undefined ? "" : String(value);
  const foundIndex = options.findIndex((option) => option.value === current);
  const selectedIndex = foundIndex >= 0 ? foundIndex : 0;
  const selected = options[selectedIndex];
  const isPlaceholder = !selected || selected.value === "";

  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const [place, setPlace] = useState<Placement | null>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const typed = useRef({ text: "", at: 0 });
  const listId = useId();

  const measure = useCallback(() => {
    const el = triggerRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    if (window.innerWidth < 640) { setPlace({ sheet: true, left: 12, width: 0, maxHeight: Math.round(window.innerHeight * 0.6) }); return; }
    const gap = 6;
    const below = window.innerHeight - rect.bottom - 14;
    const above = rect.top - 14;
    const wanted = Math.min(options.length * 42 + 12, 300);
    const flip = below < wanted && above > below;
    setPlace({
      sheet: false,
      left: Math.max(8, Math.min(rect.left, window.innerWidth - Math.max(rect.width, 180) - 8)),
      width: Math.max(rect.width, 180),
      top: flip ? undefined : rect.bottom + gap,
      bottom: flip ? window.innerHeight - rect.top + gap : undefined,
      maxHeight: Math.max(120, Math.min(300, flip ? above : below)),
    });
  }, [options.length]);

  const firstEnabled = useCallback((from: number, step: 1 | -1) => {
    for (let i = from; i >= 0 && i < options.length; i += step) if (!options[i].disabled) return i;
    return -1;
  }, [options]);

  const openMenu = () => {
    if (disabled || !options.length) return;
    measure();
    setActive(options[selectedIndex]?.disabled ? Math.max(0, firstEnabled(0, 1)) : selectedIndex);
    setOpen(true);
  };
  const closeMenu = useCallback(() => setOpen(false), []);

  const commit = (index: number) => {
    const option = options[index];
    if (!option || option.disabled) return;
    setOpen(false);
    triggerRef.current?.focus();
    if (option.value !== current) onChange?.({ target: { value: option.value, name }, currentTarget: { value: option.value, name } });
  };

  useEffect(() => {
    if (!open) return;
    const reposition = () => measure();
    window.addEventListener("resize", reposition);
    window.addEventListener("scroll", reposition, true);
    return () => { window.removeEventListener("resize", reposition); window.removeEventListener("scroll", reposition, true); };
  }, [open, measure]);

  useEffect(() => {
    if (open) document.getElementById(`${listId}-${active}`)?.scrollIntoView({ block: "nearest" });
  }, [open, active, listId]);

  const onKeyDown = (event: { key: string; preventDefault: () => void }) => {
    const { key } = event;
    if (!open) {
      if (["ArrowDown", "ArrowUp", "Enter", " "].includes(key)) { event.preventDefault(); openMenu(); }
      return;
    }
    if (key === "Escape" || key === "Tab") { if (key === "Escape") event.preventDefault(); closeMenu(); return; }
    if (key === "ArrowDown") { event.preventDefault(); const next = firstEnabled(active + 1, 1); if (next >= 0) setActive(next); return; }
    if (key === "ArrowUp") { event.preventDefault(); const next = firstEnabled(active - 1, -1); if (next >= 0) setActive(next); return; }
    if (key === "Home") { event.preventDefault(); const next = firstEnabled(0, 1); if (next >= 0) setActive(next); return; }
    if (key === "End") { event.preventDefault(); const next = firstEnabled(options.length - 1, -1); if (next >= 0) setActive(next); return; }
    if (key === "Enter" || key === " ") { event.preventDefault(); commit(active); return; }
    if (key.length === 1) {
      const now = Date.now();
      typed.current.text = now - typed.current.at > 700 ? key.toLowerCase() : typed.current.text + key.toLowerCase();
      typed.current.at = now;
      const hit = options.findIndex((option) => !option.disabled && option.label.toLowerCase().startsWith(typed.current.text));
      if (hit >= 0) setActive(hit);
    }
  };

  const layout = /\bw-full\b/.test(className) ? "is-full" : /\bblock\b/.test(className) ? "is-block" : "is-inline";

  return (
    <div className={`ui-select ${layout}`}>
      <button
        ref={triggerRef}
        type="button"
        id={id}
        title={title}
        role="combobox"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={open ? listId : undefined}
        aria-activedescendant={open ? `${listId}-${active}` : undefined}
        aria-required={required || undefined}
        aria-label={aria["aria-label"]}
        aria-labelledby={aria["aria-labelledby"]}
        disabled={disabled}
        className={`ui-select-trigger ${className}`}
        onClick={() => (open ? closeMenu() : openMenu())}
        onKeyDown={onKeyDown}
        onKeyUp={(event) => { if (event.key === " ") event.preventDefault(); }}
      >
        <span className={`ui-select-value${isPlaceholder ? " is-placeholder" : ""}`}>{selected?.label ?? ""}</span>
        <Chevron open={open} />
      </button>
      <select className="ui-select-native" tabIndex={-1} aria-hidden="true" name={name || undefined} required={required} disabled={disabled} value={current} onChange={() => undefined}>
        {options.map((option, index) => <option key={`${option.value}-${index}`} value={option.value} disabled={option.disabled}>{option.label}</option>)}
      </select>
      {open && place ? createPortal(
        <>
          <div className={`ui-select-backdrop${place.sheet ? " is-sheet" : ""}`} onPointerDown={closeMenu} />
          <ul
            id={listId}
            role="listbox"
            aria-label={aria["aria-label"] || title || "Options"}
            className={`ui-select-panel${place.sheet ? " is-sheet" : ""}`}
            style={place.sheet ? { maxHeight: place.maxHeight } : { left: place.left, width: place.width, top: place.top, bottom: place.bottom, maxHeight: place.maxHeight }}
          >
            {options.map((option, index) => (
              <li
                key={`${option.value}-${index}`}
                id={`${listId}-${index}`}
                role="option"
                aria-selected={index === selectedIndex}
                aria-disabled={option.disabled || undefined}
                className={`ui-select-option${index === active ? " is-active" : ""}${index === selectedIndex ? " is-selected" : ""}${option.disabled ? " is-disabled" : ""}`}
                onPointerDown={(event) => event.preventDefault()}
                onMouseEnter={() => { if (!option.disabled) setActive(index); }}
                onClick={() => commit(index)}
              >
                <span>{option.label}</span>
                {index === selectedIndex ? <svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="m5 12.5 4.5 4.5L19 7.5" /></svg> : null}
              </li>
            ))}
          </ul>
        </>,
        document.body,
      ) : null}
    </div>
  );
}
