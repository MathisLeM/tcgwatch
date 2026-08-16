"use client";

import { useState } from "react";

import { joinWaitlist } from "@/lib/api";

type State = "idle" | "sending" | "done" | "error";

/** Formulaire de liste d'attente de la landing.
 *
 *  Le champ garde exactement le style de la maquette « Landing v2 » — seul le
 *  `action="#"` mort a été remplacé par un vrai POST vers `/waitlist`. Une fois
 *  l'inscription passée, le formulaire est remplacé par le message de succès
 *  (l'API est idempotente, mais laisser le bouton actif invite à re-cliquer). */
export default function WaitlistForm({ source = "landing" }: { source?: string }) {
  const [email, setEmail] = useState("");
  const [state, setState] = useState<State>("idle");
  const [message, setMessage] = useState("");

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (state === "sending") return;
    setState("sending");
    try {
      const res = await joinWaitlist(email.trim(), source);
      setMessage(res.message);
      setState("done");
    } catch (err) {
      // Rate limit (429) ou API injoignable : on reste explicite plutôt que muet.
      setMessage(
        err instanceof Error && err.message
          ? err.message
          : "Inscription impossible pour le moment — réessayez dans un instant.",
      );
      setState("error");
    }
  }

  if (state === "done") {
    return (
      <p className="text-sm text-ok font-medium" role="status">
        {message}
      </p>
    );
  }

  return (
    <>
      <form
        onSubmit={onSubmit}
        className="flex flex-wrap items-center justify-center gap-2.5 w-full max-w-[460px]"
      >
        <label htmlFor="waitlist-email" className="sr-only">
          Adresse e-mail
        </label>
        <input
          id="waitlist-email"
          name="email"
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          disabled={state === "sending"}
          placeholder="vous@exemple.com"
          className="flex-1 min-w-[220px] bg-canvas border border-line-strong rounded-xl px-4 py-3.5
                     text-sm text-ink placeholder-dim outline-none focus:border-accent transition-colors
                     disabled:opacity-60"
        />
        <button
          type="submit"
          disabled={state === "sending"}
          className="bg-accent text-on-accent font-semibold px-[22px] py-3.5 rounded-xl text-sm whitespace-nowrap
                     cursor-pointer hover:brightness-110 transition-[filter] disabled:opacity-60
                     disabled:cursor-not-allowed"
        >
          {state === "sending" ? "Envoi…" : "Prévenez-moi"}
        </button>
      </form>
      {state === "error" ? (
        <p className="text-xs text-gold" role="alert">
          {message}
        </p>
      ) : (
        <p className="text-xs text-dim">Pas de spam — juste un e-mail à l&apos;ouverture.</p>
      )}
    </>
  );
}
