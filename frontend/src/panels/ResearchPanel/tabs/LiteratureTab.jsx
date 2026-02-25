/**
 * LiteratureTab.jsx - Bibliografia Trybu Badawczego
 * ~16 pozycji: artykuly recenzowane, materialy kursowe, pakiety R.
 * Kazda pozycja: co zaadaptowalismy / co odrzucilismy / gdzie w kodzie.
 */

import React, { useState } from 'react';

// ─── Badge typów ─────────────────────────────────────────────────────────────

const TypeBadge = ({ type }) => {
  const cfg = {
    paper:   { cls: 'bg-purple-900/50 text-purple-300 border-purple-700',  label: 'artykuł' },
    lecture: { cls: 'bg-orange-900/50 text-orange-300 border-orange-700',  label: 'wykład' },
    package: { cls: 'bg-cyan-900/50   text-cyan-300   border-cyan-700',    label: 'pakiet R' },
  };
  const { cls, label } = cfg[type] ?? cfg.paper;
  return (
    <span className={`text-xs px-2 py-0.5 rounded border font-mono ${cls}`}>
      {label}
    </span>
  );
};

// ─── Bloki karty ─────────────────────────────────────────────────────────────

const Adopted = ({ children }) => (
  <div className="mt-3 p-3 bg-green-900/20 border border-green-800/40 rounded">
    <p className="text-xs font-bold text-green-400 uppercase tracking-wide mb-1">
      ✓ Co zaadaptowaliśmy
    </p>
    <p className="text-sm text-gray-300 leading-relaxed">{children}</p>
  </div>
);

const Rejected = ({ children }) => (
  <div className="mt-2 p-3 bg-red-900/20 border border-red-800/40 rounded">
    <p className="text-xs font-bold text-red-400 uppercase tracking-wide mb-1">
      ✗ Co odrzuciliśmy i dlaczego
    </p>
    <p className="text-sm text-gray-300 leading-relaxed">{children}</p>
  </div>
);

const InCode = ({ children }) => (
  <div className="mt-2 p-3 bg-gray-800/60 border border-gray-700/40 rounded">
    <p className="text-xs font-bold text-gray-400 uppercase tracking-wide mb-1">
      → Gdzie w kodzie
    </p>
    <p className="text-sm text-gray-400 font-mono leading-relaxed">{children}</p>
  </div>
);

// ─── Karta wpisu ─────────────────────────────────────────────────────────────

const EntryCard = ({ type, authors, year, title, venue, doi, adopted, rejected, inCode }) => (
  <div className="mb-6 p-5 bg-gray-800/40 border border-gray-700/50 rounded-lg">
    <div className="flex items-center gap-2 mb-2">
      <TypeBadge type={type} />
      {year && <span className="text-xs text-gray-500">{year}</span>}
    </div>
    <p className="text-sm text-gray-400">{authors}</p>
    <p className="text-base font-semibold text-white mt-0.5 leading-snug">{title}</p>
    {venue && (
      <p className="text-sm italic text-gray-400 mt-1">{venue}</p>
    )}
    {doi && (
      <p className="text-xs text-blue-400 mt-0.5 font-mono">DOI: {doi}</p>
    )}
    <Adopted>{adopted}</Adopted>
    <Rejected>{rejected}</Rejected>
    <InCode>{inCode}</InCode>
  </div>
);

// ─── Dane bibliograficzne ─────────────────────────────────────────────────────

const PAPERS = [
  {
    type: 'paper',
    authors: 'Kopczewska, K.',
    year: 2021,
    title: 'Entropy as measure of agglomeration. Interactions of business locations and housing transactions in Warsaw metropolitan area',
    venue: 'in: Reggiani, Schintler, Czamanski, Patuelli (eds.), Handbook on Entropy, Complexity, and Spatial Dynamics: The Rebirth of Theory?, Edward Elgar 2021',
    doi: null,
    adopted: 'Zaadoptowałem rdzeń methodology entropy-tessellation-agglomeration: udziały pól kafli Voronoi jako prawdopodobieństwa, Shannon entropy na tych udziałach, normalizacja przez H_max=log(n). Wiernie implementuję Eq (1), (3), (4) paper\'u w 07_diagnostics.R:465-516 — H_emp = −Σ(p_i · log(p_i)) gdzie p_i = area_i / Σarea, H_max = log(n), H_rel = H_emp / H_max. Implementujemy ręcznie bez importowania pakietu spatialWarsaw (CONCEPT REF) — pełna kontrola numerics. Wykład CLASS 9 (Spatial Econometrics 09 - tesselation and entropy) Kopczewskiej był ścieżką nauki tej methodology.\n\nMoja interpretacja: paper rozwiązuje fundamentalny problem MAUP (Modified Areal Unit Problem) przez Voronoi tessellation — brak arbitralnych granic administrative. W naszym pipeline H_rel pełni dwie role: (1) measure aglomeracji obserwacji [główne zastosowanie paper\'u], (2) sanity check dla macierzy W — wartość bliska 1.0 potwierdza że kafle Voronoja mają zbliżone powierzchnie i W nie jest zdegenerowana. Druga rola jest projektowo specyficzna, nie z paper\'u.',
    rejected: 'Surowy ETA jako zmienna Y modelu — dziki nie tworzą skupisk jak firmy, ETA mierzy skupienie wzorca punktowego, nie ciągłe ryzyko na obszarze. Y musi być continuous per kafel (count_pop / inv_pop / log_count), nie globalny skalar entropii porównujący ze stanem maksymalnego rozproszenia.\n\nBivariate cross-product entropy między dwoma typami punktów — paper analizuje business + population OSOBNO (univariate) i porównuje wizualnie, brak łącznej formuły matematycznej. To research gap, nie świadome odrzucenie.\n\nShannon Redundancy O = 1 − relH (Eq 5 paper) — mathematically equivalent do 1 − H_rel, czyli redundantne raportowanie.',
    inCode: 'r_scripts/research/07_diagnostics.R:465-516 (H_emp, H_max, H_rel — własna impl. Shannona). Tessellation setup w 02_voronoi.R (paper proponuje Voronoi tessellation jako foundation methodology).',
    todoImpl: {
      priority: 'HIGH',
      summary: 'Trzy must-fix przed full publish: rescaling function dla scale-dependence, deduplikacja sightings GPS, Monte Carlo CSR test dla statystycznej istotności H_rel.',
      details: `1. RESCALING FUNCTION (07_diagnostics.R, po L516):
   Paper Appendix s. 21 proponuje normalizację do N_ref=1000:
   - log: multiplier = 0.015 * ln(n) + 0.8957
   - power: multiplier = 0.9056 * n^0.0144
   Wybór: log (smoother) lub power (bliższe danych paper).
   Implementacja: H_rel_norm <- H_rel / multiplier
   Bez tego H_rel z różnych okresów (różne n) NIE są porównywalne.

2. DEDUPLICATION SIGHTINGS (02_voronoi.R, przed st_voronoi()):
   Crowdsourcing ma duplicate GPS coords (ten sam dzik wielokrotnie zgłoszony).
   Opcja A: full dedup — sf::st_unique() lub dplyr::distinct(lon, lat)
   Opcja B: jitter — sf::st_jitter() z bardzo małym buffer (5-10m)
   Decyzja: A jeśli rzadkie duplikaty, B jeśli chcemy zachować evidence
   że wielu obywateli widzi tego samego dzika (sygnał reliability).

3. MONTE CARLO CSR TEST (nowy 07b_entropy_test.R lub w 07_diagnostics.R):
   Paper Eq (12), s. 13. Procedura:
   - Powtórz k=1000 razy: random n points w region boundary (sp::spsample(..., type="random"))
   - Per iterację: Voronoi → shares → relH_csr_i
   - Wynik: distribution {relH_csr_i}
   - Test: if relH_empir not in CI_1-α(relH_csr) → reject CSR hypothesis
   - Report w analytics_researchdiagnostics: relH_csr_mean, relH_csr_lower, relH_csr_upper, csr_p_value`,
      sources: 'Paper Eq (1), (3), (4) s. 6-7; Eq (12) s. 13; Appendix s. 21. NotebookLM 3-way dialog tura 3.',
    },
  },
  {
    type: 'paper',
    authors: 'Kubara, M., Kopczewska, K.',
    year: 2024,
    title: 'Akaike information criterion in choosing the optimal k-nearest neighbours of the spatial weight matrix',
    venue: 'Spatial Economic Analysis, 19(1), 73–91',
    doi: '10.1080/17421772.2023.2176539',
    adopted: 'Kubara i Kopczewska adresują ten sam problem: jak wybrać k w macierzy k-NN bez arbitralności? Ich odpowiedź — minimalizacja AIC modelu errorsarlm(Y ~ 1) po kandydatach k — przyjąłem w całości. Zaimplementowałem samodzielnie: pętla po k ∈ [k_min, k_max], per każde k buduję kNN → symetryzuję (make.sym.nb(), bo spatialreg wymaga symetrii) → nb2listw() → errorsarlm(Y~1). Zwycięski k = najniższy AIC. Nie wywołuję bestW() z pakietu spatialWarsaw — własna impl. w 05_matrix_w.R:140-213.\n\nMoja interpretacja: AIC jako kryterium selekcji sąsiedztwa to tania decyzja — jeden dodatkowy loop, a eliminujemy całą klasę błędów doboru k. Dla dzika w Białołęce nie zakładam z góry że "5 sąsiadów to naturalny zasięg" — dane decydują.\n\nLiteral cytat z paper: "AIC outperforms the logLik, LR and J-test methods in testing non-nested spatial models" — bezpośrednie uzasadnienie empiryczne dla mojego knn_aic loop, gdzie porównuję modele z różnymi macierzami W (non-nested case).',
    rejected: 'Odrzuciłem stałe k narzucone z góry (klasyczna praktyka: k=5 albo k=8). Dobór k a priori jest arbitralny — nie wiemy z góry co jest "naturalnym sąsiedztwem" dla rozmieszczenia dzika w Białołęce.',
    inCode: 'r_scripts/research/05_matrix_w.R:140-213 (pętla AIC: errorsarlm(Y~1) per k ∈ [k_min, k_max], wybór min(AIC))\nsrc/analytics/orchestrator_research.py (RESEARCH_W_METHOD=knn_aic aktywuje tę ścieżkę)',
  },
  {
    type: 'paper',
    authors: 'Elhorst, J.P.',
    year: 2010,
    title: 'Applied Spatial Econometrics: Raising the Bar',
    venue: 'Spatial Economic Analysis, 5(1), 9–28',
    doi: null,
    adopted: 'Z Elhorst zaadoptowałem dwie rzeczy. Pierwsza: taksonomię SAR/SEM/SDM jako spójną rodzinę modeli przestrzennych — to dało mi framework do myślenia o tym, który model dobrać do danych z rozmieszczenia dzika. Druga: efekty przestrzenne direct/indirect/total (impacts z LeSage & Pace 2009, spopularyzowane przez Elhorst). W moim pipeline dla modelu SAR obliczam impacts(best_result$model, listw=listw, R=500) — rozkład efektu predyktora na direct (jednostka sama), indirect (przez sąsiadów) i total — terminologia Elhorst/LeSage & Pace.\n\nCzego nie zaadoptowałem: LM cascade jako mechanizmu auto-selekcji SAR vs SEM.\n\nInterpretacja parametrów per Manski\'s spatial multiplier framework: ρ (endogenous interaction) — "decision of spatial unit depends on decision taken by other spatial units", dyfuzja szoków przez inverse spatial transformation. θ (exogenous interaction) — "local externalities", zależność od X innych jednostek. λ (correlated effects) — "similar unobserved environmental characteristics result in similar behaviour", spillover unmodelled regions. W naszym pipeline: ρ z lagsarlm (SAR), λ z errorsarlm (SEM), AIC comparison wybiera fits.\n\nAIC-only defense per Elhorst\'s own caveat (pp. 16): "tests for significant differences between log-likelihood function values, such as the LR-test, can formally not be used" dla non-nested models. Nasz knn_aic loop porównuje modele z różnymi W (różne k) — to non-nested case → LR cascade formally inapplicable → AIC justified. Plus per Kubara & Kopczewska 2024 (patrz oddzielny entry): empirical AIC superiority dla non-nested spatial models.\n\nCounter-arguments (honest): (1) "Data mining" risk per Burnham & Anderson — AIC valid między candidates a priori specified, multi-testing correction needed dla 50+ variants. Mój response: knn_aic ma bounded k ∈ [4, sqrt(n)] z theoretical justification, nie arbitrary. (2) Harris & Kravtsova (2009, cited by Elhorst): AIC W selection finds "local maximum among competing models, not necessarily correctly specified W". (3) Florax et al (2003): classical LM cascade w wielu przypadkach lepiej recover true DGP niż blind AIC search. Mój response: post-hoc Moran/LISA diagnostics w research/07_diagnostics.R weryfikują że final model passes spatial autocorrelation checks.',
    rejected: 'Odrzuciłem LM cascade (LM-Lag → LM-Error → Robust LM-Lag → Robust LM-Error → decision tree) z trzech powodów. (A) AIC to mainstream kryterium porównania modeli (Burnham & Anderson 2002) — niski koszt poznawczy dla odbiorcy. LM cascade jest niszowy w spatial econometrics. (B) Prostsza implementacja: 2 fity + 1 porównanie AIC kontra 4 testy + drzewo decyzyjne. (E) AIC trywialnie rozszerza się na SDM, SLX, SAC — LM cascade wymaga osobnych rodzin testów dla każdego.\n\nŚwiadomy trade-off: AIC selekcjonuje model o lepszym ficie, ale nie identyfikuje mechanizmu strukturalnego — czy zależność przestrzenna tkwi w Y (SAR) czy w resztach (SEM). LM cascade Elhorst by to rozróżnił. Wybrałem prostotę nad pryncypialną selekcją.\n\nMoja interpretacja: Elhorst (2010) to fundament metodologiczny projektu — SAR/SEM jako właściwa odpowiedź na problem autokorelacji przestrzennej w danych aglomeracyjnych. Moją decyzją było uproszczenie mechanizmu wyboru, nie odejście od rodziny modeli.',
    inCode: 'r_scripts/NEW_02_spatial_models.R:536-561 (# --- auto: wybor przez AIC ---; if (sar_result$AIC < sem_result$AIC) → SAR, else SEM)\nr_scripts/NEW_02_spatial_models.R:582-587 (impacts() — direct/indirect/total, Elhorst framework, SAR only)\nr_scripts/research/07_diagnostics.R:338-358 (lm.RStests() jako post-hoc diagnostics — obliczane i zapisywane do DB, NIE kryterium wyboru modelu)',
  },
  {
    type: 'paper',
    authors: 'Kopczewska, K.',
    year: 2023,
    title: 'Spatial bootstrapped microeconometrics: Forecasting for out-of-sample geo-locations in big data',
    venue: 'Scandinavian Journal of Statistics, 50(3), 1391–1419',
    doi: '10.1111/sjos.12636',
    adopted: 'Ideja PAM clustering do wyboru reprezentatywnej podpróby oraz Voronoi jako kalibracji przestrzeni dała mi framework dla logiki ensemble. Zaimplementowałem trójskładnikowe ważenie: 0.30×density + 0.40×spatial + 0.30×ETA — wagi dobrane analogicznie do strategii ważonego prognozowania z pracy.\n\nMoja interpretacja: paper uzasadnił architekturę ensemble zamiast single-model prediction. Trzy komponenty pokrywają trzy wymiary ryzyka: gęstość obserwacji (data-driven), SAR/SEM (structural spatial process), ETA (tessellation quality check).',
    rejected: 'BootSpatReg() właściwy – algorytm bootstrap dla danych count (zliczenia dzików na kafel) ma problem z wariancją zero gdy count=1. Out-of-sample forecasting dla nowych lokalizacji – poza scope projektu portfolio.',
    inCode: 'r_scripts/05_ensemble_prediction.R:146-154 (wagi ensemble: W_DENSITY=0.30, W_SPATIAL=0.40, W_ETA=0.30)\nr_scripts/research/05_matrix_w.R:284-314 (tessW jako kalibracja przestrzeni — wagi przez długość wspólnych granic)',
  },
  {
    type: 'paper',
    authors: 'Müller, S., Wilhelm, P., Haase, K.',
    year: 2013,
    title: 'Spatial dependencies and spatial drift in public transport seasonal ticket revenue data',
    venue: 'Journal of Retailing and Consumer Services, 20, 334–348',
    doi: '10.1016/j.jretconser.2013.01.005',
    adopted: 'Methodology reference dla concept spatial drift w wildlife encounter prediction. Główna teza paper (Dresden public transport, N=391 districts, 2005): relacje między zmiennymi a outcome rzadko są stałe w przestrzeni, a ignorowanie tej niestacjonarności prowadzi do averaging effects. Literal cytat: "On a global scale (neglecting these spatial differences) the effect of the promotion might be averaged out."\n\nUse case dla naszego projektu: zachowanie dzików w Białołęce może wykazywać regional inversion (bliskość człowieka attracts w jednym klastrze, repels w innym). Globalny SAR/SEM model może wskazać wynik "zero" jeśli te efekty się cancel out. Sample size adequate per Müller benchmark — nasze 1500 verified sightings (lub PUB ~870 cells) > Müller\'s N=391.\n\nMoja interpretacja: drift detection wymaga GWR + clustering coefficients pipeline (per Müller methodology). Świadoma decision: currently out of portfolio scope — Phase 6 publish focuses na SAR/SEM global z post-hoc LISA diagnostics. Pełna drift analysis = post-publish work, requires GWR reactivation (currently legacy).',
    rejected: 'Direct adoption Müller\'s GWR + Leung F1/F3 tests + k-means clustering coefficients workflow. Wymagałaby reactivation GWR pipeline który świadomie marked legacy archaeology (commit 88b4049). Currently używamy SAR/SEM-only approach z post-hoc LISA HH/LL/HL/LH cluster detection (research/07_diagnostics.R:299-327) — partial drift signal capture bez full local regression. Trade-off: stability + simpler architecture vs lost local nonstationarity detection.',
    inCode: 'r_scripts/research/07_diagnostics.R:299-327 (moran.test na resztach modelu — test dryfu przestrzennego po estymacji SAR/SEM)',
  },
  {
    type: 'paper',
    authors: 'Kopczewska, K.',
    year: 2014,
    title: 'The spatial range of local governments: does geographical distance affect governance and public service?',
    venue: 'The Annals of Regional Science (Springer). ISSN: 0570-1864',
    doi: '10.1007/s00168-013-0567-z',
    adopted: 'Z pracy Kopczewskiej zaadoptowałem konceptualny argument dla wyboru granicy administracyjnej Białołęki jako AOI analizy. Paper traktuje zasięg przestrzenny jako naturalną jednostkę analizy lokalnych zjawisk — przeniosłem ten argument na decyzję: granica administracyjna dzielnicy to weryfikowalny, stabilny proxy zakresu analizy, nawet jeśli zjawisko (aktywność dzika) przekracza te granice.\n\nMoja interpretacja: granica administracyjna to pragmatyczny compromise — świadomie nie odzwierciedla zasięgu ekologicznego dzika, ale daje stabilny, weryfikowalny AOI dla analizy. Paper Kopczewskiej dał mi językowy frame dla tej decyzji.',
    rejected: 'Formalna analiza zasięgu przestrzennego samorządów – nie dotyczy zjawisk przyrodniczych. Zakres administracyjny nie odzwierciedla zasięgu ekologicznego dzika (migracje przekraczają granice dzielnicy).',
    inCode: 'r_scripts/research/01_generate_voronoi.R:92-100 (PostgreSQL query: SELECT geom FROM boundaries WHERE name = \'bialoleka\')\nsrc/sightings/management/commands/init_grids.py:106-107 (to samo dla grid generation)',
  },
];

const LECTURES = [
  {
    type: 'lecture',
    authors: 'Kopczewska, K.',
    year: 2025,
    title: 'Temat 3: Statystyki przestrzenne / Spatial statistics',
    venue: 'Ekonometria i statystyka przestrzenna w R. Wydział Nauk Ekonomicznych UW. Updated 03.10.2025',
    doi: null,
    adopted: 'moran.test() dla globalnej Morana I (krok 7), localmoran() → LISA quadranty, struktura workflow: Moran I OLS residuów → sygnał autokorelacji → decyzja o modelu przestrzennym.\n\nMoja interpretacja: ta struktura workflow stała się szkieletem kroku 7 pipeline — OLS → Moran I residuów → jeśli istotny → SAR/SEM. Moran I nie jako finalna diagnostyka, ale jako kryterium selekcji: czy w ogóle model przestrzenny jest potrzebny.',
    rejected: 'LOSH (Local Spatial Heteroscedasticity) – poza scope. Join-count test dla danych binarnych – Y jest continuous w RESEARCH mode, nie binarne.',
    inCode: 'r_scripts/research/07_diagnostics.R: L299-327 (moran.test, krok 7 — global Moran\'s I) + L419-462 (localmoran → LISA HH/LL/HL/LH/NS quadrants)',
  },
  {
    type: 'lecture',
    authors: 'Kopczewska, K.',
    year: 2025,
    title: 'Temat 4: Modele zależności przestrzennych / Spatial dependence models',
    venue: 'Ekonometria i statystyka przestrzenna w R. Wydział Nauk Ekonomicznych UW. Updated 03.10.2025',
    doi: null,
    adopted: 'Pełny opis SAR/SEM: dlaczego OLS jest obciążone (biased & inconsistent) gdy istnieje lag przestrzenny Y, jak lm.RStests() wskazuje właściwy model, estymacja przez MLE z lagsarlm()/errorsarlm(). Efekty bezpośrednie i pośrednie (impacts). W mojej implementacji używam AIC zamiast LM cascade — patrz entry Elhorst 2010 dla uzasadnienia.',
    rejected: 'Podejście OLS-only – jak wykazano w materiale, MNK jest obciążone i niezgodne w obecności autokorelacji przestrzennej zmiennej zależnej. Duża próba nie pomaga.',
    inCode: 'r_scripts/NEW_02_spatial_models.R:340-408 (SAR: lagsarlm via MLE + SEM: errorsarlm via MLE)\nr_scripts/research/07_diagnostics.R:525-580 (impacts display — direct/indirect/total)',
  },
  {
    type: 'lecture',
    authors: 'Kopczewska, K.',
    year: 2025,
    title: 'Temat 5: Modele interakcji przestrzennych / Spatial interactions model',
    venue: 'Ekonometria i statystyka przestrzenna w R. Wydział Nauk Ekonomicznych UW. Updated 04.10.2025',
    doi: null,
    adopted: 'Z wykładu zaadoptowałem framework efektów spillover: aktywność dzicza w kaflu i wpływa na sąsiadów j przez człon ρWy w SAR. Tobler\'s First Law jako formalne uzasadnienie że bliskość przestrzenna ma znaczenie — bez tego założenia kNN i tessW byłyby arbitralne.\n\nMoja interpretacja: "spatial lag transmituje ryzyko" to nie metafora — to formalny mechanizm ρWy gdzie W = macierz wag (tessW lub kNN). Im wyższy ρ, tym silniejszy spillover. Dla dzika: ryzyko wylewa się z hotspotów do sąsiednich kafli, co SAR modeluje explicite.',
    rejected: 'Pełny model interakcji przestrzennych (gravity model z macierzą T przepływów). Nie obserwujemy realnych przepływów dzika między kaflami, tylko zliczenia obecności per kafel.',
    inCode: 'r_scripts/NEW_02_spatial_models.R:340-408 (ρ w SAR: lagsarlm, λ w SEM: errorsarlm)',
  },
  {
    type: 'lecture',
    authors: 'Kopczewska, K.',
    year: 2025,
    title: 'Zajęcia 6: Regresja ważona geograficznie (GWR) & dryf przestrzenny',
    venue: 'Ekonometria i statystyka przestrzenna w R. Wydział Nauk Ekonomicznych UW. Updated 05.10.2025',
    doi: null,
    adopted: 'Konceptualne rozróżnienie autokorelacja przestrzenna (podobieństwo sąsiadów) vs. dryf przestrzenny (kierunkowość efektów). Rozumienie że oba procesy mogą współistnieć – SAR/SEM absorbuje autokorelację, ale dryf wymaga diagnostyki residuów.\n\nFormal GWR equation: yᵢ = β₀(uᵢ,vᵢ) + Σₖ xᵢ,ₖ βₖ(uᵢ,vᵢ) + εᵢ, gdzie (uᵢ,vᵢ) są współrzędnymi geograficznymi a βₖ(uᵢ,vᵢ) lokalne współczynniki estymowane per obserwacja z weighted least squares (Brunsdon et al. 1996). Kernel functions: Gaussian (smooth decay), Bi-square (zero outside bandwidth), Adaptive vs Fixed. Bandwidth selection: AICc preferred over CV dla ecological data ("more robust than CV for small N").\n\nStability thresholds per Zajęcia 6: "N < 100: Do NOT use GWR — exploratory only. Unacceptable non-convergence; inflated Type I errors". "100 < N < 200: GWR wciąż wysoce niestabilny". "N = 500-5,000 ACCEPTABLE Stable convergence". Nasz FAST mode (9875 cells) > acceptable upper, PUB mode (~870 cells) w acceptable range, ale FAST/PUB mode wybrane jest dla speed/methodology consistency, nie GWR-friendliness.',
    rejected: 'Aktywne GWR pipeline. Świadoma migracja GWR → SAR/SEM w refactor 2026 z trzech powodów: (1) audytowalność — single global model z interpretable ρ/λ łatwiejsze do verify niż 870+ lokalnych modeli z różnymi współczynnikami; (2) stability — SAR/SEM stabilny dla całego naszego range (PUB ~870 cells, FAST 9875 cells); (3) simpler architecture — SAR/SEM jeden model + post-hoc LISA cluster detection lepiej fits portfolio scope niż full GWR + per-cell coefficient analysis.\n\nLegacy artifacts: test_r_pipeline.py marked @pytest.mark.skip (commit 88b4049) references stare tabele analytics_gwr_result które nie istnieją w current DB schema. GWmodel package removed z Dockerfile.r (commit 61f983b).',
    inCode: 'r_scripts/research/07_diagnostics.R:299-327 (moran.test na resztach modelu — test dryfu przestrzennego po estymacji SAR/SEM)',
  },
  {
    type: 'lecture',
    authors: 'Kopczewska, K.',
    year: 2025,
    title: 'Class 9: Detection of agglomeration – tessellation, entropy, Clark-Evans test, DBSCAN',
    venue: 'Spatial econometrics in R. Wydział Nauk Ekonomicznych UW',
    doi: null,
    adopted: 'Z wykładu zaadoptowałem dwa koncepty metodologiczne. Pierwszy: tessW — macierz wag przestrzennych zbudowana na siatce Voronoi, gdzie siłę połączenia między kaflem i a j definiuje długość ich wspólnej granicy. Zaimplementowałem to własnoręcznie w PostGIS: ST_Length(ST_CollectionExtract(ST_Intersection(a.geometry, b.geometry), 2)::geography) — każda para sąsiadów otrzymuje wagę proporcjonalną do metrów wspólnej granicy, nie do odległości centroidów.\n\nDrugi: ETA (Entropy-Tessellation-Agglomeration) jako miara skupienia rozkładu przestrzennego kafli Voronoi. Shannon entropy udziałów powierzchni kafli: H_emp = -sum(shares * log(shares)), H_rel = H_emp / H_max. Wysoka H_rel (→1) = kafle podobnej wielkości (obserwacje rozłożone równomiernie), niska H_rel (→0) = kafle silnie zróżnicowane (obserwacje skupione w jednym obszarze).\n\nMoja interpretacja: oba koncepty adresują ten sam problem — jak zmierzyć "nieregularność" tesselacji Voronoi z obserwacji terenowych. tessW przekłada tę nieregularność na wagi modelu przestrzennego; ETA raportuje ją jako diagnostykę skupienia. Wzajemnie komplementarne w pipeline.',
    rejected: 'Clark-Evans test, QDC (Quick Density Clustering), FLE (Focal Local Entropy), DBSCAN — narzędzia do analizy wzorców punktowych, nie do regresji przestrzennej. Clark-Evans test zakłada dane punktowe z hipotezą zerową CSR (Complete Spatial Randomness) — brak sensownej hipotezy zerowej dla administracyjnych granic kafli Voronoi.\n\nMAUP critique per Class 9 lecture (honest acknowledgment): "The aggregation of point data within administrative regions generates the Modified Areal Unit Problem (MAUP), what may bias all computations". Plus: "Regular cells of the same size however, do not follow the natural spatial pattern of data, and thus are still an arbitrary division of space". DBSCAN i FLE jako point-pattern methods avoid MAUP entirely. Mój wybór LISA via spdep wynika z trade-off: LISA daje formal p-values per cell (hypothesis testing) + integration z SAR/SEM workflow kosztem MAUP sensitivity. Point-pattern methods (DBSCAN, QDC, FLE) pozostają legitimate alternatives — out of current portfolio scope, post-publish potential.',
    inCode: 'r_scripts/research/05_matrix_w.R:284-314 (tessW custom: ST_Length wspólnych granic via PostGIS, wagi proporcjonalne do metrów)\nr_scripts/research/07_diagnostics.R:465-516 (ETA custom: H_emp/H_max/H_rel Shannon entropy udziałów powierzchni kafli)\nenv var: RESEARCH_RUN_ETA (1/0, default 0 — krok 7 opcjonalny)',
  },
  {
    type: 'lecture',
    authors: 'Kopczewska, K.',
    year: 2025,
    title: 'Class 12: Bootstrapped spatial microeconometrics',
    venue: 'Spatial econometrics in R. Wydział Nauk Ekonomicznych UW. Oparte na: Kopczewska (2023), Scandinavian Journal of Statistics',
    doi: null,
    adopted: 'Idea PAM clustering do wyboru reprezentatywnego podzbioru danych (inspiracja dla logiki ensemble). Voronoi jako kalibracja przestrzeni przy predykcji: nowe punkty "wpadają" do istniejących kafli przez tessellację.',
    rejected: 'Pełen BootSpatReg() pipeline – wymaga próby min. 50K obserwacji do sensownego resampligu subpróby. Nasz PUB mode (~870 cells) lub FAST mode (9875 cells) — bootstrap subsampling teoretycznie możliwy ale wymaga min. 50K obserwacji dla sensownego resamplingu per BootSpatReg() spec. Out of current portfolio scope.',
    inCode: 'r_scripts/05_ensemble_prediction.R:146-154 (wagi ensemble: W_DENSITY=0.30, W_SPATIAL=0.40, W_ETA=0.30)',
  },
  {
    type: 'lecture',
    authors: 'Kopczewska, K.',
    year: 2025,
    title: 'Temat 7: Przestrzenno-czasowa stabilność klastrów GWR / Spatio-temporal stability of GWR clusters',
    venue: 'Ekonometria przestrzenna w R. Wydział Nauk Ekonomicznych UW. Updated 16.10.2025. Oparte na: Kopczewska & Ćwiakowski (2021)',
    doi: null,
    adopted: 'Methodology reference dla spatio-temporal cluster stability analysis. STS algorithm (per Kopczewska 2021 Land Use Policy paper): (1) estimate GWR per period, (2) k-means cluster coefficients per period, (3) rasterise + compute median cluster ID per grid cell, (4) compare partitioning across periods z Adjusted Rand Index (ARI), (5) output coloured matrix period-to-period.\n\nFormalna definicja problemu: "The spatio-temporal stability problem is to detect if the similarity of coefficients, indicating whether they should belong to the same cluster, is stable in time over space".\n\nMoja interpretacja: STS jest applicable concept dla wildlife monitoring (seasonal patterns + 5-year data span), ale technical blockers: (a) STS() function w spatialWarsaw wymaga T≥2 periods ("Wymagane: dane z kilku okresów (T ≥ 2, inaczej funkcja zwróci błąd)"); (b) chunking 1500 sightings po latach redukuje per-period N do ~300 = below GWR stability threshold (per Zajęcia 6 entry: N<500 catastrophic); (c) GWR currently legacy archaeology w naszym pipeline.',
    rejected: 'Pełna spatio-temporal stability analysis w current pipeline. Required prerequisites NIE met: (a) GWR reactivation (currently legacy per Zajęcia 6 GWR entry), (b) per-period N adequate, (c) seasonal stratification methodology, (d) extended time series collection. Plus distinction od BootSpatReg() (often confused): BootSpatReg = spatial bootstrapped regression z PAM medoid selection dla large data; STS = ARI-based cluster stability across periods. Świadoma decyzja: STS deferred post-publish jako multi-period extension work.',
    inCode: 'r_scripts/research/07_diagnostics.R:415-462 (LISA HH/LL/HL/LH/NS counts per run)',
  },
];

const PACKAGES = [
  {
    type: 'package',
    authors: 'Kopczewska, K. et al.',
    year: null,
    title: 'spatialWarsaw: Spatial econometrics tools for Warsaw-school spatial analysis',
    venue: 'R package 0.9.0. GitHub: poktam/spatialWarsaw',
    doi: null,
    adopted: 'Z pakietu spatialWarsaw zaadoptowałem trzy koncepty metodologiczne (nie kod): tessW jako adaptacja tessellation-based W matrix, bestW jako k-NN z AIC selection, ETA jako Shannon entropy on tessellation areas.\n\nStatus: CONCEPT REF (methodology citation) + formal build-time dependency declaration. Lokalna kopia pakietu w repo, install w Dockerfile.r jako local source: install.packages(\'/app/spatialWarsaw\', repos=NULL, type=\'source\'). DESCRIPTION formalnie deklaruje 20 packages w Imports (spatialreg, GWmodel, spdep, sf, terra, dbscan, cluster, dplyr, ggplot2, stargazer, gridExtra, sampling, benford.analysis, DescTools, fossil, sp, rlang + 3 base R).\n\nMoja interpretacja: pre-cleanup plan (SPATIALWARSAW_ANALYSIS.md) zakładał pełną adopcję — verdict brzmiał "NATYCHMIAST: devtools::install_github(\'poktam/spatialWarsaw\')". W refactor 2026 zmieniłem podejście do CONCEPT REF + własne implementacje z trzech powodów: (1) stabilność — pakiet nie jest na CRAN, GitHub install wprowadza coupling i ryzyko silent failure; (2) audytowalność — własne implementacje są fully testable i debuggable, spatialWarsaw funkcje to black-box methodology; (3) niezależność — kluczowe runtime deps (spatialreg, sf, terra) dostarcza rocker base image niezależnie. Pakiet pozostaje methodology citation — komentarze w kodzie explicit pokazują akademicki provenance algorytmów.\n\nCounter-argument (honest): pre-cleanup analysis podnosiła 3 valid argumenty za użyciem pakietu — (a) tessW() parameter-free vs k-NN arbitrary k, (b) ETA() auto-transforms CRS do EPSG:3857, (c) STS() jako pipeline w jednym wywołaniu. Argument (a) zachowuje moc — w naszym pipeline używam knn z AIC-based k selection (data-driven k zamiast arbitrary), ale nie eliminuje fundamentalnej krytyki. Pełna konwersja do tessW workflow pozostaje legitimate alternative — out of current portfolio scope.',
    rejected: 'Bezpośredniego importu pakietu (library(spatialWarsaw)) nie użyłem. Pakiet zainstalowany w Dockerfile.r ze source, ale nigdy nie ładowany w aktywnych skryptach R (grep library(spatialWarsaw) = zero hits w r_scripts/).\n\nReliance na transitive dependency chain dla spatialreg — CC paranoid audit 2026-05-26 zweryfikował empirycznie że spatialreg pochodzi z rocker/geospatial:4.3.2 base image (Built 2024-02-07), niezależnie od spatialWarsaw chain. spatialWarsaw DESCRIPTION deklaruje spatialreg jako Imports, ale base image wyprzedza spatialWarsaw step w build order — usunięcie pakietu nie złamałoby spatialreg ani aktywnego pipeline\'u.\n\nGitHub install (devtools::install_github) — pakiet nie jest na CRAN, GitHub-based install dla production worker-r wprowadza coupling z external repo dostępnością + ryzyko silent install failure (empirycznie zaobserwowane: current image z 2026-01-18 nie ma spatialWarsaw mimo install step w Dockerfile.r). Wybrałem local-source install z kopią pakietu w repo.\n\nWłasna implementacja daje audytowalność każdej operacji.',
    inCode: 'library(spatialreg) ×3 (bezpośrednio, nie via spatialWarsaw):\nr_scripts/NEW_02_spatial_models.R:27\nr_scripts/research/05_matrix_w.R:150\nr_scripts/research/07_diagnostics.R:121\n\nMethodology references (komentarze):\nr_scripts/NEW_02_spatial_models.R:5 — "# ŹRÓDŁO: spatialWarsaw (lagsarlm, errorsarlm, sacsarlm)"\nr_scripts/research/05_matrix_w.R:284-314 — tessW reimplementation (custom)\nr_scripts/research/05_matrix_w.R:140-200 — bestW reimplementation z AIC selection\nr_scripts/research/07_diagnostics.R:465-516 — ETA Shannon entropy reimplementation\n\n0 calls library(spatialWarsaw) w aktywnych r_scripts/\n0 calls spatialWarsaw:: poza komentarzami',
  },
  {
    type: 'package',
    authors: 'Bivand, R., Pebesma, E., Gómez-Rubio, V.',
    year: null,
    title: 'spatialreg: Spatial Regression Analysis',
    venue: 'R package, CRAN: spatialreg',
    doi: null,
    adopted: 'lagsarlm() – estymacja modelu SAR (Spatial Autoregressive) przez MLE. errorsarlm() – estymacja modelu SEM (Spatial Error). impacts() – efekty bezpośrednie i pośrednie (direct/indirect/total) raportowane w kroku 7.',
    rejected: 'SLX (Spatial Lag of X) – nie przetestowano, LM tests nie wskazały potrzeby. spBreg_*() (MCMC Bayesian) – zbędna złożoność obliczeniowa dla naszej skali (PUB ~870 cells, FAST 9875 cells) względem benefit nad SAR/SEM. SDM z SDM-specific impacts – Elhorst (2010) uzasadnia parsimony.',
    inCode: 'r_scripts/NEW_02_spatial_models.R:340-408 (lagsarlm — SAR, errorsarlm — SEM, oba via MLE)\nr_scripts/research/07_diagnostics.R:525-580 (impacts display — direct/indirect/total spillovers)',
  },
];

// ─── Sekcje nawigacji ─────────────────────────────────────────────────────────

const SECTIONS = [
  { id: 'papers',   label: 'Artykuły',         count: PAPERS.length },
  { id: 'lectures', label: 'Mat. kursowe',      count: LECTURES.length },
  { id: 'packages', label: 'Pakiety R',          count: PACKAGES.length },
];

// ─── Główny komponent ─────────────────────────────────────────────────────────

const LiteratureTab = () => {
  const [activeSection, setActiveSection] = useState('papers');

  const entries = {
    papers:   PAPERS,
    lectures: LECTURES,
    packages: PACKAGES,
  }[activeSection];

  return (
    <div className="flex h-full gap-0">
      {/* Sidebar */}
      <nav className="w-44 flex-shrink-0 border-r border-gray-700 pr-4">
        <p className="text-xs text-gray-500 uppercase tracking-wide mb-3 font-semibold">
          Źródła
        </p>
        {SECTIONS.map((sec) => (
          <button
            key={sec.id}
            onClick={() => setActiveSection(sec.id)}
            className={`
              w-full text-left px-3 py-2.5 rounded text-sm mb-1 flex items-center justify-between transition-colors
              ${activeSection === sec.id
                ? 'bg-blue-600/30 text-blue-300 border border-blue-600/40'
                : 'text-gray-400 hover:text-white hover:bg-gray-700/50 border border-transparent'
              }
            `}
          >
            <span>{sec.label}</span>
            <span className="text-xs bg-gray-700 text-gray-400 rounded px-1.5 py-0.5">
              {sec.count}
            </span>
          </button>
        ))}

        <div className="mt-6 p-3 bg-gray-800/50 rounded border border-gray-700/50">
          <p className="text-xs text-gray-500 leading-relaxed">
            Każda pozycja: co zaadaptowaliśmy, co odrzuciliśmy i dlaczego, gdzie w kodzie.
          </p>
        </div>
      </nav>

      {/* Content */}
      <div className="flex-1 pl-6 overflow-auto">
        <SectionHeader sectionId={activeSection} count={entries.length} />
        {entries.map((entry, idx) => (
          <EntryCard key={idx} {...entry} />
        ))}
      </div>
    </div>
  );
};

// ─── Nagłówek sekcji ──────────────────────────────────────────────────────────

const SectionHeader = ({ sectionId, count }) => {
  const cfg = {
    papers: {
      title: 'Artykuły recenzowane',
      desc:  'Prace naukowe, których metodologia lub koncepcje zostały wykorzystane lub świadomie odrzucone podczas budowy RESEARCH pipeline.',
    },
    lectures: {
      title: 'Materiały kursowe',
      desc:  'Wykłady z kursu "Ekonometria i statystyka przestrzenna w R" (dr hab. K. Kopczewska, WNE UW, 2025). Każde zajęcia dały cegielkę do rozumienia całości.',
    },
    packages: {
      title: 'Pakiety R',
      desc:  'Biblioteki R i narzędzia analityczne. Aktywnie importowane w pipeline: spdep, spatialreg, RPostgres, sf i inne. Inspiracja metodologiczna (zainstalowane w Dockerfile.r jako CONCEPT REF, bez library() w skryptach R): spatialWarsaw — koncepty zaadoptowane i zaimplementowane własnoręcznie.',
    },
  };
  const { title, desc } = cfg[sectionId];
  return (
    <div className="mb-6">
      <h2 className="text-lg font-bold text-white">{title}</h2>
      <p className="text-sm text-gray-400 mt-1">{desc}</p>
      <div className="mt-3 h-px bg-gray-700" />
    </div>
  );
};

export default LiteratureTab;
