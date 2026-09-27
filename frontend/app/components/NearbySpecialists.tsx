"use client";

import { useState } from "react";
import { findNearby, ApiError, NearbyPlace } from "../lib/api";

const CATEGORIES = [
  { key: "nephrologist", label: "Nephrologists" },
  { key: "kidney_hospital", label: "Kidney hospitals" },
  { key: "dialysis_center", label: "Dialysis centers" },
  { key: "emergency_hospital", label: "Emergency hospitals" },
];

type State =
  | { status: "idle" }
  | { status: "locating" }
  | { status: "loading" }
  | { status: "denied" }
  | { status: "unavailable"; message: string }
  | { status: "error"; message: string }
  | { status: "results"; results: NearbyPlace[] };

export default function NearbySpecialists() {
  const [category, setCategory] = useState("nephrologist");
  const [state, setState] = useState<State>({ status: "idle" });

  function search(cat: string) {
    setCategory(cat);
    if (!("geolocation" in navigator)) {
      setState({ status: "unavailable", message: "Location services are not supported in this browser." });
      return;
    }
    setState({ status: "locating" });
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        setState({ status: "loading" });
        try {
          const res = await findNearby(pos.coords.latitude, pos.coords.longitude, cat);
          setState({ status: "results", results: res.results });
        } catch (err) {
          if (err instanceof ApiError && err.status === 503) {
            setState({ status: "unavailable", message: err.message });
          } else {
            setState({ status: "error", message: err instanceof ApiError ? err.message : "Search failed." });
          }
        }
      },
      () => setState({ status: "denied" }),
      { timeout: 10000 }
    );
  }

  return (
    <div className="bg-[var(--surface)] border border-[var(--line)] rounded-xl p-5">
      <h3 className="font-[family-name:var(--font-display)] font-semibold text-sm mb-1">
        Find nearby kidney specialists
      </h3>
      <p className="text-xs text-[var(--ink-soft)] mb-3">
        Uses your device location, requested only when you search. Nothing is stored.
      </p>

      <div className="flex flex-wrap gap-2 mb-3">
        {CATEGORIES.map((c) => (
          <button
            key={c.key}
            type="button"
            onClick={() => search(c.key)}
            className={`text-xs px-3 py-1.5 rounded-full border transition-colors ${
              category === c.key && state.status !== "idle"
                ? "bg-[var(--primary)] text-white border-[var(--primary)]"
                : "border-[var(--line)] hover:border-[var(--primary)]"
            }`}
          >
            {c.label}
          </button>
        ))}
      </div>

      {state.status === "locating" && (
        <p className="text-xs text-[var(--ink-soft)]">Requesting your location…</p>
      )}
      {state.status === "loading" && (
        <p className="text-xs text-[var(--ink-soft)]">Searching nearby…</p>
      )}
      {state.status === "denied" && (
        <div className="text-xs text-[var(--risk-medium)] bg-[var(--risk-medium)]/8 border border-[var(--risk-medium)]/30 rounded-lg p-3">
          Location permission was denied. Enable location access in your browser settings to
          find specialists near you.
        </div>
      )}
      {state.status === "unavailable" && (
        <div className="text-xs text-[var(--ink-soft)] bg-[var(--bg)] border border-[var(--line)] rounded-lg p-3">
          {state.message}
        </div>
      )}
      {state.status === "error" && (
        <div className="text-xs text-[var(--risk-high)] bg-[var(--risk-high)]/8 border border-[var(--risk-high)]/30 rounded-lg p-3">
          {state.message}
        </div>
      )}
      {state.status === "results" && (
        state.results.length === 0 ? (
          <p className="text-xs text-[var(--ink-soft)]">No results found nearby for this category.</p>
        ) : (
          <ul className="space-y-2">
            {state.results.map((p, i) => (
              <li key={i} className="text-sm border border-[var(--line)] rounded-lg p-3">
                <div className="font-medium">{p.name}</div>
                <div className="text-xs text-[var(--ink-soft)]">{p.address}</div>
                {p.rating != null && (
                  <div className="text-xs text-[var(--ink-soft)] mt-1">
                    ★ {p.rating} ({p.user_ratings_total} reviews)
                  </div>
                )}
              </li>
            ))}
          </ul>
        )
      )}
    </div>
  );
}
