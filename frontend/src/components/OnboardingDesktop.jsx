import { Fragment, useEffect } from "react";
import { motion } from "framer-motion";
import { useSightingsStore } from "../stores/sightingsStore";
import { HighlightRing } from "./HighlightRing";
import { CoachCallout } from "./CoachCallout";

const TARGETS = [
  {
    id: "theme",
    n: 1,
    label: "Motyw kolorystyczny",
    title: "Zmień paletę kolorów",
    body: "Przełączaj między motywami mapy - znajdź najczytelniejszy.",
    selector: '[data-onboard="theme-cycle"]',
    anchor: "below-left",
  },
  {
    id: "layers",
    n: 2,
    label: "Warstwy mapy",
    title: "12 warstw OpenStreetMap",
    body: (
      <>
        Lasy, woda, zabudowa, drogi
        <br />- włącz kontekst środowiskowy.
      </>
    ),
    selector: '[data-onboard="mode-toggle"]',
    anchor: "below-left",
  },
  {
    id: "calc",
    n: 3,
    label: "Model ryzyka",
    title: "Oblicz strefy ryzyka",
    body: "Wybierz wielkość próby oraz algorytm i przelicz - wynik pojawia się na mapie.",
    selector: '[data-onboard="calc-panel"]',
    anchor: "right-of",
    offsetY: 80,
  },
  {
    id: "report",
    n: 4,
    label: "Zgłoszenie obserwacji",
    title: "Widziałeś dzika?",
    body: "Kliknij +, ustaw pin na miejscu spotkania i wyślij. Obserwacja trafia do modelu od razu.",
    selector: '[data-onboard="report-fab"]',
    anchor: "left-of",
  },
];

const STAGGER = 0.2;
const footerDelay = 0.15 + TARGETS.length * STAGGER;

function FooterStrip({ onDismiss }) {
  return (
    <div
      style={{
        position: "fixed",
        top: "50%",
        left: "50%",
        transform: "translate(-50%, -50%)",
        zIndex: 502,
      }}
    >
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: footerDelay, duration: 0.3, ease: "easeOut" }}
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: "6px",
          background: "rgba(8,14,22,0.88)",
          border: "1px solid rgba(255,255,255,0.08)",
          backdropFilter: "blur(10px)",
          padding: "18px 28px",
          borderRadius: "16px",
          boxShadow: "0 18px 50px rgba(0,0,0,0.5)",
          maxWidth: "300px",
        }}
      >
        <div
          style={{
            width: "100%",
            borderBottom: "1px solid rgba(255,255,255,0.06)",
            paddingBottom: "12px",
            marginBottom: "6px",
            textAlign: "center",
          }}
        >
          <p
            style={{
              margin: 0,
              fontSize: "11px",
              color: "#9CA3AF",
              lineHeight: 1.55,
            }}
          >
            <strong
              style={{ color: "rgb(var(--color-primary))", fontWeight: 700 }}
            >
              Uwaga: dane są testowe.
            </strong>
          </p>
        </div>
        <span
          style={{
            fontSize: "12px",
            color: "#fff",
            fontWeight: 600,
            whiteSpace: "nowrap",
          }}
        >
          Zgłoś, przeglądaj, analizuj
        </span>
        <motion.button
          data-qa="onboarding.dismiss"
          whileHover={{ scale: 1.03 }}
          whileTap={{ scale: 0.95 }}
          onClick={onDismiss}
          style={{
            marginTop: "8px",
            padding: "10px 24px",
            borderRadius: "999px",
            background: "rgb(var(--color-primary))",
            color: "white",
            fontWeight: 700,
            fontSize: "13px",
            border: "none",
            cursor: "pointer",
            boxShadow: "0 12px 32px rgb(var(--color-primary) / 0.35)",
            whiteSpace: "nowrap",
          }}
        >
          Wchodzę na mapę →
        </motion.button>
      </motion.div>
    </div>
  );
}

export function OnboardingDesktop() {
  const { completeOnboarding } = useSightingsStore();

  useEffect(() => {
    const onKey = (e) => {
      if (e.key === "Escape") completeOnboarding();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [completeOnboarding]);

  return (
    <motion.div
      role="dialog"
      aria-modal="true"
      aria-label="Witamy na mapie dzików"
      className="fixed inset-0 z-[500]"
      style={{ backgroundColor: "rgba(4, 8, 14, 0.62)" }}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.3 }}
      onClick={(e) => {
        if (e.target === e.currentTarget) completeOnboarding();
      }}
    >
      {TARGETS.map((t, i) => (
        <Fragment key={t.id}>
          <HighlightRing selector={t.selector} delay={i * STAGGER} />
          <CoachCallout {...t} delay={0.15 + i * STAGGER} />
        </Fragment>
      ))}

      <FooterStrip onDismiss={completeOnboarding} />
    </motion.div>
  );
}
