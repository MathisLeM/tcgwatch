"use client";

import { useEffect, useState } from "react";
import Protected from "@/components/Protected";
import { AlertConfig, createAlert, deleteAlert, listAlerts, testAlert } from "@/lib/api";

function AlertsInner() {
  const [alerts, setAlerts] = useState<AlertConfig[]>([]);
  const [channel, setChannel] = useState<"email" | "discord">("email");
  const [destination, setDestination] = useState("");
  const [alertType, setAlertType] = useState<"restock" | "price_drop" | "any">("restock");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  function reload() {
    listAlerts().then(setAlerts).catch(() => {});
  }
  useEffect(reload, []);

  async function add(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setMsg(null);
    try {
      await createAlert({ scope_type: "favorites", channel, destination, alert_type: alertType });
      setDestination("");
      reload();
      setMsg("✅ Alerte créée — elle couvre tous vos favoris.");
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "Erreur");
    } finally {
      setBusy(false);
    }
  }

  async function onTest(id: number) {
    const r = await testAlert(id);
    setMsg(r.success ? "✅ Test envoyé (ou journalisé en dry-run)." : `❌ ${r.detail}`);
  }

  async function onDelete(id: number) {
    await deleteAlert(id);
    reload();
  }

  return (
    <div className="max-w-3xl">
      <h1 className="text-xl font-semibold mb-1">Mes alertes</h1>
      <p className="text-sm text-gray-400 mb-5">
        Soyez notifié dès qu&apos;un de vos favoris est réapprovisionné ou baisse de prix.
      </p>

      <form onSubmit={add} className="bg-gray-900 border border-white/10 rounded-xl p-4 mb-6 space-y-3">
        <div className="flex flex-wrap gap-2">
          <select value={channel} onChange={(e) => setChannel(e.target.value as "email" | "discord")}
            className="rounded-lg bg-gray-950 border border-white/10 px-3 py-2 text-sm">
            <option value="email">Email</option>
            <option value="discord">Discord</option>
          </select>
          <select value={alertType} onChange={(e) => setAlertType(e.target.value as typeof alertType)}
            className="rounded-lg bg-gray-950 border border-white/10 px-3 py-2 text-sm">
            <option value="restock">Réapprovisionnement</option>
            <option value="price_drop">Baisse de prix</option>
            <option value="any">Les deux</option>
          </select>
          <input
            value={destination} onChange={(e) => setDestination(e.target.value)} required
            placeholder={channel === "email" ? "votre@email.com" : "URL du webhook Discord"}
            className="flex-1 min-w-60 rounded-lg bg-gray-950 border border-white/10 px-3 py-2 text-sm
                       focus:outline-none focus:border-red-500"
          />
          <button type="submit" disabled={busy}
            className="bg-red-600 hover:bg-red-500 disabled:opacity-60 text-white text-sm
                       font-semibold px-4 py-2 rounded-lg">Ajouter</button>
        </div>
        {msg && <p className="text-sm text-gray-300">{msg}</p>}
      </form>

      <div className="space-y-2">
        {alerts.map((a) => (
          <div key={a.id}
            className="flex items-center justify-between bg-gray-900 border border-white/5 rounded-lg px-4 py-3">
            <div className="text-sm">
              <span className="font-medium">{a.channel === "email" ? "📧 Email" : "💬 Discord"}</span>
              <span className="text-gray-400"> · {a.alert_type} · {a.scope_type}</span>
              <div className="text-xs text-gray-500 truncate max-w-md">{a.destination}</div>
            </div>
            <div className="flex items-center gap-3 text-sm">
              <button onClick={() => onTest(a.id)} className="text-gray-400 hover:text-white">Tester</button>
              <button onClick={() => onDelete(a.id)} className="text-red-400 hover:text-red-300">Supprimer</button>
            </div>
          </div>
        ))}
        {alerts.length === 0 && <p className="text-gray-500 text-sm">Aucune alerte configurée.</p>}
      </div>
    </div>
  );
}

export default function AlertsPage() {
  return (
    <Protected>
      <AlertsInner />
    </Protected>
  );
}
