import { useSightingsStore } from "../stores/sightingsStore";

export default function ReportFAB() {
  const { enterAddMode } = useSightingsStore();

  return (
    <button
      data-qa="sighting.fab-open"
      onClick={() => {
        enterAddMode();
      }}
      className="w-14 h-14 rounded-2xl flex items-center justify-center text-white text-2xl font-bold cursor-pointer border-none fab-primary"
      aria-label="Zgłoś obserwację"
    >
      <svg
        width="24"
        height="24"
        viewBox="0 0 24 24"
        fill="none"
        stroke="white"
        strokeWidth="2.5"
        strokeLinecap="round"
      >
        <path d="M12 5v14M5 12h14" />
      </svg>
    </button>
  );
}
