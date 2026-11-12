/** H5 · Owner profile: name, phone, email and the per-category notification matrix. */

import { useEffect, useState, type FormEvent } from "react";
import { api } from "../api/apiClient";
import { NotificationPreferences } from "../features/alerts/NotificationPreferences";

export function OwnerProfile({ houseId }: { houseId: number }) {
  const [form, setForm] = useState({ full_name: "", phone: "", email: "" });
  const [loaded, setLoaded] = useState(false);
  const [notice, setNotice] = useState<{ kind: "ok" | "error"; text: string } | null>(null);

  useEffect(() => {
    api
      .me()
      .then((me) => {
        setForm({ full_name: me.name ?? me.full_name ?? "", phone: me.phone ?? "", email: me.email });
        setLoaded(true);
      })
      .catch(() => setNotice({ kind: "error", text: "Unable to load your profile." }));
  }, []);

  async function save(event: FormEvent) {
    event.preventDefault();
    try {
      await api.updateMe({
        full_name: form.full_name.trim() || undefined,
        phone: form.phone.trim() || undefined,
        email: form.email.trim() || undefined,
      });
      setNotice({ kind: "ok", text: "Profile saved." });
    } catch (err) {
      const message = (err as { message?: string }).message ?? "Could not save your profile.";
      setNotice({ kind: "error", text: message });
    }
  }

  const set = (key: keyof typeof form) => (e: { target: { value: string } }) => setForm({ ...form, [key]: e.target.value });

  return (
    <div className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Your home / profile</p>
          <h1>Profile and alerts</h1>
          <p className="muted">How we reach you when something happens at home.</p>
        </div>
      </header>
      {notice && <div className={notice.kind === "ok" ? "notice" : "notice error"} role={notice.kind === "ok" ? "status" : "alert"}>{notice.text}</div>}
      <div className="settings-grid">
        <form className="card" onSubmit={(e) => void save(e)} aria-label="Profile">
          <h2>Contact details</h2>
          <label>
            Name
            <input value={form.full_name} onChange={set("full_name")} disabled={!loaded} autoComplete="name" />
          </label>
          <label>
            Mobile phone (for text alerts)
            <input value={form.phone} onChange={set("phone")} disabled={!loaded} type="tel" placeholder="+15551234567" autoComplete="tel" />
          </label>
          <label>
            Email
            <input value={form.email} onChange={set("email")} disabled={!loaded} type="email" autoComplete="email" />
          </label>
          {!form.phone.trim() && loaded && <p className="muted">Add a phone number to receive text alerts.</p>}
          <button className="primary" type="submit" disabled={!loaded}>
            Save profile
          </button>
        </form>
        <NotificationPreferences houseId={houseId} />
      </div>
    </div>
  );
}
