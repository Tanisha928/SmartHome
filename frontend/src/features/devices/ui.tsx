/** Small presentational pieces local to the device screens. Replace with Mithil's shared
 *  components (DataView, dialogs, form fields) when they land. */

import { useEffect, useRef, useState, type ReactNode } from "react";
import type { DeviceHealth } from "./logic";

export const colors = {
  online: { bg: "#dcfce7", fg: "#166534" },
  offline: { bg: "#fee2e2", fg: "#991b1b" },
  disabled: { bg: "#e2e8f0", fg: "#334155" },
  primary: "#0f766e",
  border: "#cbd5e1",
};

export const button = {
  minHeight: 44,
  padding: "0 1rem",
  borderRadius: 8,
  border: `1px solid ${colors.border}`,
  background: "#fff",
  cursor: "pointer",
  fontSize: 16,
} as const;

export const primaryButton = { ...button, background: colors.primary, color: "#fff", border: "none" };

export const input = {
  minHeight: 44,
  padding: "0 0.75rem",
  borderRadius: 8,
  border: `1px solid ${colors.border}`,
  fontSize: 16,
  width: "100%",
  boxSizing: "border-box",
} as const;

export const card = {
  background: "#fff",
  border: `1px solid ${colors.border}`,
  borderRadius: 12,
  padding: "1rem",
} as const;

const HEALTH_TEXT: Record<DeviceHealth, string> = {
  online: "● Online",
  offline: "○ Offline",
  disabled: "⏸ Disabled",
};

/** Colour + icon + text, never colour alone. */
export function HealthBadge({ health, text }: { health: DeviceHealth; text?: string }) {
  return (
    <span
      style={{
        background: colors[health].bg,
        color: colors[health].fg,
        borderRadius: 999,
        padding: "0.1rem 0.6rem",
        fontSize: 14,
        whiteSpace: "nowrap",
      }}
    >
      {text ?? HEALTH_TEXT[health]}
    </span>
  );
}

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label style={{ display: "grid", gap: 4, fontSize: 14 }}>
      <span>{label}</span>
      {children}
    </label>
  );
}

export function Dialog({
  title,
  children,
  onClose,
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    ref.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(15,23,42,0.45)",
        display: "grid",
        placeItems: "center",
        zIndex: 50,
      }}
    >
      <div
        ref={ref}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        tabIndex={-1}
        style={{ ...card, width: "min(520px, 92vw)", outline: "none" }}
      >
        <h3 style={{ marginTop: 0 }}>{title}</h3>
        {children}
      </div>
    </div>
  );
}

export function ConfirmDialog({
  title,
  body,
  confirmLabel,
  onConfirm,
  onCancel,
}: {
  title: string;
  body: ReactNode;
  confirmLabel: string;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  return (
    <Dialog title={title} onClose={onCancel}>
      <div>{body}</div>
      <div style={{ display: "flex", gap: 8, justifyContent: "flex-end", marginTop: 16 }}>
        <button type="button" style={button} onClick={onCancel}>
          Cancel
        </button>
        <button
          type="button"
          style={{ ...primaryButton, background: "#b91c1c" }}
          onClick={onConfirm}
        >
          {confirmLabel}
        </button>
      </div>
    </Dialog>
  );
}

/** Shows a device API key exactly once (PLAN 6.1). Closing it means the key is gone. */
export function ApiKeyModal({
  apiKey,
  deviceLabel,
  onClose,
}: {
  apiKey: string;
  deviceLabel: string;
  onClose: () => void;
}) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(apiKey);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  };
  return (
    <Dialog title={`Device key for ${deviceLabel}`} onClose={onClose}>
      <p>
        Copy this key into the device now. <strong>It will not be shown again.</strong> If it is
        lost, an admin can rotate it.
      </p>
      <code
        data-testid="api-key"
        style={{
          display: "block",
          padding: "0.75rem",
          background: "#f1f5f9",
          borderRadius: 8,
          wordBreak: "break-all",
          userSelect: "all",
        }}
      >
        {apiKey}
      </code>
      <div style={{ display: "flex", gap: 8, justifyContent: "flex-end", marginTop: 16 }}>
        <button type="button" style={button} onClick={() => void copy()}>
          {copied ? "Copied ✓" : "Copy key"}
        </button>
        <button type="button" style={primaryButton} onClick={onClose}>
          I've saved it
        </button>
      </div>
    </Dialog>
  );
}

export function Notice({ kind, children }: { kind: "error" | "info"; children: ReactNode }) {
  return (
    <p
      role={kind === "error" ? "alert" : "status"}
      style={{
        padding: "0.5rem 0.75rem",
        borderRadius: 8,
        background: kind === "error" ? "#fee2e2" : "#e0f2fe",
        color: kind === "error" ? "#991b1b" : "#075985",
      }}
    >
      {children}
    </p>
  );
}
