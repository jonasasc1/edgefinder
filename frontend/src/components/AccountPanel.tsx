import { NavLink } from "react-router";

import { loadAccount, LOGOUT_URL, signOutCleanup, useAccount } from "../lib/account";
import { setCalmFx, useCalmFx } from "../lib/calm";
import { formatDateMedium } from "../lib/format";
import { Skeleton } from "./Skeleton";

type Variant = "sidebar" | "sheet";

/** Initiale in einer Panzerplatte (Token-Farben); die Identität selbst steht daneben als Text. */
function Avatar({ name, size }: { name: string; size: "sm" | "md" }) {
  const initial = (name.trim().charAt(0) || "?").toLocaleUpperCase("de-AT");
  return (
    <span
      aria-hidden="true"
      className={`plate grid shrink-0 place-items-center bg-accent-solid font-display font-bold text-on-accent ${
        size === "sm" ? "size-10 text-title3" : "size-12 text-title2"
      }`}
    >
      {initial}
    </span>
  );
}

/** Schalter „Effekte reduzieren“ (persönlich, zusätzlich zur Systemeinstellung „Bewegung reduzieren“). */
function CalmSwitch() {
  const calm = useCalmFx();
  return (
    <button
      type="button"
      role="switch"
      aria-checked={calm}
      onClick={() => setCalmFx(!calm)}
      className="flex min-h-touch w-full items-center justify-between gap-3 rounded-control bg-fill px-3 text-left"
    >
      <span className="min-w-0">
        <span className="block text-subhead font-medium text-ink">Effekte reduzieren</span>
        <span className="block text-caption text-ink-2">Weniger Blitze und Bewegung</span>
      </span>
      <span
        aria-hidden="true"
        className={`relative h-6 w-11 shrink-0 rounded-chip transition-colors ${calm ? "bg-accent-solid" : "bg-fill-strong"}`}
      >
        <span
          className={`absolute left-0.5 top-0.5 size-5 rounded-chip bg-on-accent shadow-card transition-transform ${calm ? "translate-x-5" : ""}`}
        />
      </span>
    </button>
  );
}

/** Am Handy: Zugang zum Admin-Bereich über das Darstellung-Sheet (nur für Admins, kein 6. Tab). */
function AdminLink() {
  return (
    <NavLink
      to="/admin"
      className="flex min-h-touch items-center justify-between gap-3 rounded-control bg-fill px-3 text-subhead font-medium text-ink"
    >
      Admin-Bereich
      <span aria-hidden="true" className="text-ink-2">›</span>
    </NavLink>
  );
}

/** Konto-Bereich: Anmeldung über Cloudflare Access, Zustand der Speicherung, Abmelden. */
export function AccountPanel({ variant }: { variant: Variant }) {
  const { status, info, notice, saveError } = useAccount();
  const compact = variant === "sidebar";
  const small = compact ? "text-caption" : "text-footnote";

  const signOut = async (event: React.MouseEvent<HTMLAnchorElement>) => {
    event.preventDefault();
    await signOutCleanup();
    window.location.assign(LOGOUT_URL);
  };

  return (
    <section aria-label="Konto" className={`flex flex-col gap-3 ${compact ? "" : "mb-5 border-b border-line pb-5"}`}>
      {status === "loading" && (
        <div role="status" aria-label="Konto wird geladen" className="flex items-center gap-3">
          <Skeleton className="size-10 shrink-0" />
          <div className="flex min-w-0 flex-1 flex-col gap-2">
            <Skeleton className="h-4 w-2/3" />
            <Skeleton className="h-3 w-full" />
          </div>
        </div>
      )}

      {status === "ready" && info && (
        <>
          <div className="flex min-w-0 items-center gap-3">
            <Avatar name={info.displayName} size={compact ? "sm" : "md"} />
            <div className="min-w-0">
              <div className="truncate text-subhead font-semibold text-ink">{info.displayName}</div>
              <div className={`truncate ${small} text-ink-2`} title={info.email}>
                {info.email}
              </div>
            </div>
          </div>
          <p className={`${small} text-ink-2`}>
            Angemeldet über Cloudflare Access (Google). Konto seit {formatDateMedium(info.createdAt)}.
          </p>
          {notice && (
            <p role="status" className={`rounded-control bg-bull-soft px-3 py-2 ${small} font-medium text-bull-ink`}>
              {notice}
            </p>
          )}
          {saveError && (
            <p role="alert" className={`rounded-control bg-bear-soft px-3 py-2 ${small} text-bear-ink`}>
              Änderungen konnten nicht gespeichert werden. Sie bleiben in diesem Browser und werden bei der nächsten Änderung erneut gesendet.
            </p>
          )}
        </>
      )}

      {status === "local" && (
        <div className="flex items-center gap-3">
          <Avatar name="L" size={compact ? "sm" : "md"} />
          <p className={`${small} self-center text-ink-2`}>
            Lokaler Modus – Einstellungen werden nur in diesem Browser gespeichert.
          </p>
        </div>
      )}

      {status === "error" && (
        <div role="alert" className="flex flex-col gap-2">
          <p className={`${small} text-ink-2`}>
            <strong className="block text-subhead font-semibold text-ink">Konto nicht erreichbar</strong>
            Einstellungen und Favoriten gelten vorerst nur in diesem Browser.
          </p>
          <button
            type="button"
            onClick={() => void loadAccount()}
            className="h-touch rounded-control bg-fill px-4 text-subhead font-semibold text-ink hover:bg-fill-strong"
          >
            Erneut versuchen
          </button>
        </div>
      )}

      <CalmSwitch />

      {variant === "sheet" && status === "ready" && info?.isAdmin && <AdminLink />}

      {status === "ready" && (
        <a
          href={LOGOUT_URL}
          onClick={(event) => void signOut(event)}
          className="flex h-touch items-center justify-center rounded-control text-subhead font-semibold text-accent-ink ring-1 ring-edge hover:bg-fill"
        >
          Abmelden
        </a>
      )}
    </section>
  );
}
