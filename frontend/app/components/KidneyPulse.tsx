"use client";

type RiskLevel = "LOW" | "MEDIUM" | "HIGH" | null;

const RISK_COLOR: Record<string, string> = {
  LOW: "var(--risk-low)",
  MEDIUM: "var(--risk-medium)",
  HIGH: "var(--risk-high)",
};

const RISK_PULSE_CLASS: Record<string, string> = {
  LOW: "ring-pulse-low",
  MEDIUM: "ring-pulse-medium",
  HIGH: "ring-pulse-high",
};

export default function KidneyPulse({ risk }: { risk: RiskLevel }) {
  const color = risk ? RISK_COLOR[risk] : "var(--primary)";
  const pulseClass = risk ? RISK_PULSE_CLASS[risk] : "ring-pulse-low";

  return (
    <div className="relative flex items-center justify-center w-40 h-40 shrink-0">
      <div
        className={`absolute inset-0 rounded-full ${pulseClass}`}
        style={{ background: color, filter: "blur(10px)", opacity: 0.28, transform: "scale(0.55)" }}
        aria-hidden
      />
      <svg
        viewBox="0 0 100 100"
        className="relative w-24 h-24"
        role="img"
        aria-label={risk ? `Kidney risk indicator: ${risk}` : "Kidney risk indicator: no prediction yet"}
      >
        <path
          d="M50 12
             C 30 12, 18 28, 20 48
             C 21.5 62, 30 66, 30 78
             C 30 88, 40 92, 47 86
             C 52 82, 50 74, 55 70
             C 68 68, 82 56, 80 40
             C 78 22, 66 12, 50 12 Z"
          fill={color}
          fillOpacity={risk ? 0.9 : 0.55}
          stroke={color}
          strokeWidth="1.5"
          style={{ transition: "fill-opacity 0.4s ease" }}
        />
      </svg>
    </div>
  );
}
