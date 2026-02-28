/**
 * LiteratureTab.jsx - Bibliografia Trybu Badawczego
 * ~16 pozycji: artykuly recenzowane, materialy kursowe, pakiety R.
 * Kazda pozycja: co zaadaptowalismy / co odrzucilismy / gdzie w kodzie.
 */

import React, { useState } from "react";

// ─── Badge typów ─────────────────────────────────────────────────────────────

const TypeBadge = ({ type }) => {
  const cfg = {
    paper: {
      cls: "bg-purple-900/50 text-purple-300 border-purple-700",
      label: "artykuł",
    },
    lecture: {
      cls: "bg-orange-900/50 text-orange-300 border-orange-700",
      label: "wykład",
    },
    package: {
      cls: "bg-cyan-900/50   text-cyan-300   border-cyan-700",
      label: "pakiet R",
    },
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
    <p className="text-sm text-gray-400 font-mono leading-relaxed">
      {children}
    </p>
  </div>
);

// ─── Karta wpisu ─────────────────────────────────────────────────────────────

const EntryCard = ({
  type,
  authors,
  year,
  title,
  venue,
  doi,
  adopted,
  rejected,
  inCode,
}) => (
  <div className="mb-6 p-5 bg-gray-800/40 border border-gray-700/50 rounded-lg">
    <div className="flex items-center gap-2 mb-2">
      <TypeBadge type={type} />
      {year && <span className="text-xs text-gray-500">{year}</span>}
    </div>
    <p className="text-sm text-gray-400">{authors}</p>
    <p className="text-base font-semibold text-white mt-0.5 leading-snug">
      {title}
    </p>
    {venue && <p className="text-sm italic text-gray-400 mt-1">{venue}</p>}
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
    type: "paper",
    authors: "Kopczewska, K.",
    year: 2021,
    title:
      "Entropy as measure of agglomeration. Interactions of business locations and housing transactions in Warsaw metropolitan area",
    venue:
      "in: Reggiani, Schintler, Czamanski, Patuelli (eds.), Handbook on Entropy, Complexity, and Spatial Dynamics: The Rebirth of Theory?, Edward Elgar 2021",
    doi: null,
    adopted:
      "Z tej pracy zaadaptowałem rdzeń metodologii entropia–tessellacja–aglomeracja: udziały pól kafli Voronoi traktowane jak prawdopodobieństwa, entropia Shannona policzona na tych udziałach i normalizacja przez H_max = log(n). Równania (1), (3) i (4) artykułu implementuję wiernie w 07_diagnostics.R:465-516 - H_emp = −Σ(p_i · log(p_i)), gdzie p_i = area_i / Σarea, H_max = log(n), H_rel = H_emp / H_max. Całość liczę własnym kodem, bez ładowania pakietu spatialModel (w projekcie ma on status odniesienia koncepcyjnego, CONCEPT REF) - dzięki temu każda operacja numeryczna pozostaje pod kontrolą. Ścieżką nauki tej metodologii był wykład CLASS 9 (Spatial Econometrics 09 – tesselation and entropy) Kopczewskiej.\n\nMoja interpretacja: artykuł rozwiązuje fundamentalny problem MAUP (Modified Areal Unit Problem) przez tessellację Voronoi - znikają arbitralne granice administracyjne. W naszym przepływie obliczeniowym H_rel gra dwie role: po pierwsze mierzy aglomerację obserwacji (główne zastosowanie z artykułu), po drugie służy jako test zdrowego rozsądku dla macierzy W - wartość bliska 1.0 potwierdza, że kafle mają zbliżone powierzchnie i W nie jest zdegenerowana. Ta druga rola to już nasz pomysł projektowy, nie pochodzi z artykułu.",
    rejected:
      "Surowego ETA jako zmiennej Y modelu nie przyjąłem - dziki nie tworzą skupisk jak firmy, ETA mierzy skupienie wzorca punktowego, nie ciągłe ryzyko na obszarze. Y musi być ciągłe (continuous) per kafel (count_pop / inv_pop / log_count), nie globalnym skalarem entropii porównującym ze stanem maksymalnego rozproszenia.\n\nEntropii dwuwymiarowej (bivariate cross-product entropy) między dwoma typami punktów nie zaadoptowałem - artykuł analizuje business + population OSOBNO (univariate) i porównuje wizualnie, bez łącznej formuły matematycznej. To luka badawcza, nie świadome odrzucenie.\n\nRedundancja Shannona O = 1 − relH (Eq 5 artykułu) - matematycznie równoważna 1 − H_rel, czyli zbędne powielanie.",
    inCode:
      "r_scripts/research/07_diagnostics.R:465-516 (H_emp, H_max, H_rel - własna implementacja entropii Shannona). Przygotowanie tessellacji w 02_voronoi.R (artykuł proponuje tessellację Voronoi jako fundament metodologii).",
    todoImpl: {
      priority: "HIGH",
      summary:
        "Trzy must-fix przed full publish: rescaling function dla scale-dependence, deduplikacja sightings GPS, Monte Carlo CSR test dla statystycznej istotności H_rel.",
      details: `1. RESCALING FUNCTION (07_diagnostics.R, po L516):
   Paper Appendix s. 21 proponuje normalizację do N_ref=1000:
   - log: multiplier = 0.015 * ln(n) + 0.8957
   - power: multiplier = 0.9056 * n^0.0144
   Wybór: log (smoother) lub power (bliższe danych paper).
   Implementacja: H_rel_norm <- H_rel / multiplier
   Bez tego H_rel z różnych okresów (różne n) NIE są porównywalne.

2. DEDUPLICATION SIGHTINGS (02_voronoi.R, przed st_voronoi()):
   Crowdsourcing ma duplicate GPS coords (ten sam dzik wielokrotnie zgłoszony).
   Opcja A: full dedup - sf::st_unique() lub dplyr::distinct(lon, lat)
   Opcja B: jitter - sf::st_jitter() z bardzo małym buffer (5-10m)
   Decyzja: A jeśli rzadkie duplikaty, B jeśli chcemy zachować evidence
   że wielu obywateli widzi tego samego dzika (sygnał reliability).

3. MONTE CARLO CSR TEST (nowy 07b_entropy_test.R lub w 07_diagnostics.R):
   Paper Eq (12), s. 13. Procedura:
   - Powtórz k=1000 razy: random n points w region boundary (sp::spsample(..., type="random"))
   - Per iterację: Voronoi → shares → relH_csr_i
   - Wynik: distribution {relH_csr_i}
   - Test: if relH_empir not in CI_1-α(relH_csr) → reject CSR hypothesis
   - Report w analytics_researchdiagnostics: relH_csr_mean, relH_csr_lower, relH_csr_upper, csr_p_value`,
      sources:
        "Paper Eq (1), (3), (4) s. 6-7; Eq (12) s. 13; Appendix s. 21. NotebookLM 3-way dialog tura 3.",
    },
  },
  {
    type: "paper",
    authors: "Kubara, M., Kopczewska, K.",
    year: 2024,
    title:
      "Akaike information criterion in choosing the optimal k-nearest neighbours of the spatial weight matrix",
    venue: "Spatial Economic Analysis, 19(1), 73–91",
    doi: "10.1080/17421772.2023.2176539",
    adopted:
      'Kubara i Kopczewska adresują ten sam problem: jak wybrać k w macierzy k-NN bez arbitralności? Ich odpowiedź - minimalizacja AIC modelu errorsarlm(Y ~ 1) po kandydatach k - przyjąłem w całości. Zaimplementowałem samodzielnie: pętla po k ∈ [k_min, k_max], per każde k: buduję kNN, symetryzuję (make.sym.nb(), bo spatialreg wymaga symetrii), nb2listw(), errorsarlm(Y~1). Zwycięski k = najniższy AIC. Nie wywołuję bestW() z pakietu spatialModel - własna implementacja w 05_matrix_w.R:140-213.\n\nMoja interpretacja: AIC jako kryterium selekcji sąsiedztwa to tania decyzja - jedna dodatkowa pętla, a eliminujemy całą klasę błędów doboru k. Dla dzika w Białołęce nie zakładam z góry że "5 sąsiadów to naturalny zasięg" - dane decydują.\n\nArtykuł stwierdza wprost: "AIC outperforms the logLik, LR and J-test methods in testing non-nested spatial models" - bezpośrednie uzasadnienie empiryczne dla mojej pętli knn_aic, gdzie porównuję modele z różnymi macierzami W (non-nested case).',
    rejected:
      'Odrzuciłem stałe k narzucone z góry (klasyczna praktyka: k=5 albo k=8). Dobór k a priori jest arbitralny - nie wiemy z góry co jest "naturalnym sąsiedztwem" dla rozmieszczenia dzika w Białołęce.',
    inCode:
      "r_scripts/research/05_matrix_w.R:140-213 (pętla AIC: errorsarlm(Y~1) per k ∈ [k_min, k_max], wybór min(AIC))\nsrc/analytics/orchestrator_research.py (RESEARCH_W_METHOD=knn_aic aktywuje tę ścieżkę)",
  },
  {
    type: "paper",
    authors: "Elhorst, J.P.",
    year: 2010,
    title: "Applied Spatial Econometrics: Raising the Bar",
    venue: "Spatial Economic Analysis, 5(1), 9–28",
    doi: null,
    adopted:
      'Z Elhorst zaadoptowałem dwie rzeczy. Pierwsza: taksonomię SAR/SEM/SDM jako spójną rodzinę modeli przestrzennych - to dało mi ramy do myślenia o tym, który model dobrać do danych z rozmieszczenia dzika. Druga: efekty przestrzenne direct/indirect/total (impacts z LeSage & Pace 2009, spopularyzowane przez Elhorst). W moim przepływie dla modelu SAR obliczam impacts(best_result$model, listw=listw, R=500), który rozkłada efekt predyktora na direct (jednostka sama), indirect (przez sąsiadów) i total - terminologia Elhorst/LeSage & Pace.\n\nJedno tylko odrzuciłem: LM cascade jako mechanizm auto-selekcji SAR vs SEM.\n\nInterpretację parametrów opieram na ramach Manski\'s spatial multiplier framework: ρ (interakcja endogeniczna) - "decision of spatial unit depends on decision taken by other spatial units" - dyfuzja szoków przez odwrotną transformację przestrzenną. θ (interakcja egzogeniczna) - "local externalities" - zależność od X innych jednostek. λ (efekty skorelowane) - "similar unobserved environmental characteristics result in similar behaviour" - rozlewanie na niemodelowane regiony. W naszym przepływie: ρ z lagsarlm (SAR), λ z errorsarlm (SEM), porównanie AIC wybiera dopasowanie.\n\nObrona podejścia AIC-only, zgodnie z własnym zastrzeżeniem Elhorst (pp. 16): "tests for significant differences between log-likelihood function values, such as the LR-test, can formally not be used" dla non-nested models. Nasza pętla knn_aic porównuje modele z różnymi W (różne k) - to przypadek modeli nie-zagnieżdżonych (non-nested) → LR cascade formalnie nieuzasadniony → AIC uzasadniony. Plus per Kubara & Kopczewska 2024 (zob. oddzielny wpis): empiryczna wyższość AIC dla modeli nie-zagnieżdżonych w przestrzeni.\n\nUczciwie trzeba przyznać, że ta decyzja ma przeciwników. Burnham i Anderson ostrzegają przed przeszukiwaniem danych (data mining): AIC jest poprawny między kandydatami zdefiniowanymi a priori, a przy ponad 50 wariantach należałoby korygować wielokrotne testowanie. Nasza pętla ma jednak ograniczone k ∈ [4, sqrt(n)] z uzasadnieniem teoretycznym - to nie jest ślepe przeszukiwanie. Harris i Kravtsova (2009, za Elhorstem) idą dalej: selekcja W przez AIC znajduje "local maximum among competing models, not necessarily correctly specified W". A Florax et al. (2003) pokazują, że klasyczna kaskada LM w wielu przypadkach lepiej odtwarza prawdziwy DGP niż przeszukiwanie po AIC. Na oba zarzuty odpowiadamy tym samym: diagnostyki post-hoc Moran/LISA w research/07_diagnostics.R sprawdzają, czy model końcowy przechodzi kontrole autokorelacji przestrzennej. Gdyby przeszukiwanie wybrało zły model - reszty by to zdradziły.',
    rejected:
      "Odrzuciłem LM cascade (LM-Lag → LM-Error → Robust LM-Lag → Robust LM-Error → decision tree) z trzech powodów: AIC to powszechnie stosowane kryterium porównania modeli (Burnham & Anderson 2002) - niski koszt poznawczy dla odbiorcy, a LM cascade jest niszowy w ekonometrii przestrzennej. Do tego prostsza implementacja: 2 dopasowania + 1 porównanie AIC kontra 4 testy + drzewo decyzyjne. I wreszcie: AIC trywialnie rozszerza się na SDM, SLX, SAC - LM cascade wymaga osobnych rodzin testów dla każdego.\n\nAIC wskazuje model o lepszym dopasowaniu, ale nie identyfikuje mechanizmu strukturalnego - czy zależność przestrzenna tkwi w Y (SAR) czy w resztach (SEM). Zresztą, LM cascade Elhorst by to rozróżnił. Wybrałem prostotę nad pryncypialną selekcją. I to wystarczy.\n\nMoja interpretacja: Elhorst (2010) to fundament metodologiczny projektu - SAR/SEM jako właściwa odpowiedź na problem autokorelacji przestrzennej w danych aglomeracyjnych. Moją decyzją było uproszczenie mechanizmu wyboru, nie odejście od rodziny modeli.",
    inCode:
      "r_scripts/02_spatial_models.R:536-561 (# --- auto: wybor przez AIC ---; if (sar_result$AIC < sem_result$AIC) → SAR, else SEM)\nr_scripts/02_spatial_models.R:582-587 (impacts() - direct/indirect/total, Elhorst framework, SAR only)\nr_scripts/research/07_diagnostics.R:338-358 (lm.RStests() jako post-hoc diagnostics - obliczane i zapisywane do DB, NIE kryterium wyboru modelu)",
  },
  {
    type: "paper",
    authors: "Kopczewska, K.",
    year: 2023,
    title:
      "Spatial bootstrapped microeconometrics: Forecasting for out-of-sample geo-locations in big data",
    venue: "Scandinavian Journal of Statistics, 50(3), 1391–1419",
    doi: "10.1111/sjos.12636",
    adopted:
      "Pomysł klastrowania PAM (Partitioning Around Medoids) do wyboru reprezentatywnej podpróby oraz Voronoi jako kalibracji przestrzeni dał mi ramy dla logiki ensemble. Zaimplementowałem trójskładnikowe ważenie: 0.30×density + 0.40×spatial + 0.30×ETA - wagi dobrałem analogicznie do strategii ważonego prognozowania z pracy.\n\nMoja interpretacja: artykuł uzasadnił architekturę ensemble zamiast predykcji jednomodelowej. W RESEARCH: trzy składniki - density_score (gęstość obserwacji, wywodzone z danych), model_fitted/SAR/SEM (strukturalny proces przestrzenny), area_rank_score (geometria tessellacji). W PUB: dwa sygnały geometryczne oparte na polu kafla - SAR/SEM nie ma zastosowania (brak wariancji Y, Voronoi 1:1).",
    rejected:
      "Pominąłem właściwy BootSpatReg() - algorytm bootstrap dla danych zliczeniowych (zliczenia dzików na kafel) ma problem z wariancją zero gdy count=1. Prognozowanie poza próbą (out-of-sample) dla nowych lokalizacji - poza zakresem projektu portfolio.",
    inCode:
      "r_scripts/05_ensemble_prediction.R:146-154 (wagi ensemble: W_DENSITY=0.30, W_SPATIAL=0.40, W_ETA=0.30)\nr_scripts/research/05_matrix_w.R:284-314 (tessW jako kalibracja przestrzeni - wagi przez długość wspólnych granic)",
  },
  {
    type: "paper",
    authors: "Müller, S., Wilhelm, P., Haase, K.",
    year: 2013,
    title:
      "Spatial dependencies and spatial drift in public transport seasonal ticket revenue data",
    venue: "Journal of Retailing and Consumer Services, 20, 334–348",
    doi: "10.1016/j.jretconser.2013.01.005",
    adopted:
      'Skąd w projekcie o dzikach praca o biletach komunikacji miejskiej w Dreźnie? Stąd, że Müller (N=391 dzielnic, 2005) pokazuje zjawisko, które może dotyczyć i nas: relacje między zmiennymi a wynikiem rzadko są stałe w przestrzeni, a ignorowanie tej niestacjonarności uśrednia efekty (averaging effects). Dosłowny cytat: "On a global scale (neglecting these spatial differences) the effect of the promotion might be averaged out."\n\nZachowanie dzików w Białołęce może wykazywać regionalne odwrócenie (regional inversion) - bliskość człowieka przyciąga w jednym klastrze, odpycha w innym. Globalny model SAR/SEM może wskazać wynik bliski zeru, jeśli te efekty się zniosą. Liczebność próby wystarczająca według punktu odniesienia Müllera - nasze 3500 zweryfikowanych zgłoszeń (lub PUB 1:1 z próbą, 3500 przy pełnej) spokojnie przekracza N=391 Müllera.\n\nMoja interpretacja: wykrywanie dryfu wymaga przepływu GWR i klastrowania współczynników (zgodnie z metodologią Müllera). Pełna analiza dryfu poza aktualnym zakresem portfolio - etap 6 publikacji koncentruje się na globalnym SAR/SEM z diagnostyką post-hoc LISA, a pełny GWR wraca po publikacji (aktualnie zaszłość techniczna).',
    rejected:
      "Bezpośredniej adopcji przepływu Müllera: GWR + testy F1/F3 Leunga + k-means klastrowania współczynników. Wymagałaby reaktywacji przepływu GWR, który świadomie oznaczono jako zaszłość techniczną (commit 88b4049). Aktualnie stosujemy podejście wyłącznie SAR/SEM z post-hoc wykrywaniem klastrów LISA HH/LL/HL/LH (research/07_diagnostics.R:299-327) - łapiemy część sygnału dryfu, ale bez pełnej regresji lokalnej. Kompromis: stabilność + prostsza architektura kontra utrata wykrywania lokalnej niestacjonarności.",
    inCode:
      "r_scripts/research/07_diagnostics.R:299-327 (moran.test na resztach modelu - test dryfu przestrzennego po estymacji SAR/SEM)",
  },
  {
    type: "paper",
    authors: "Kopczewska, K.",
    year: 2014,
    title:
      "The spatial range of local governments: does geographical distance affect governance and public service?",
    venue: "The Annals of Regional Science (Springer). ISSN: 0570-1864",
    doi: "10.1007/s00168-013-0567-z",
    adopted:
      "Z pracy Kopczewskiej zaadoptowałem konceptualny argument za wyborem granicy administracyjnej Białołęki jako obszaru analizy (AOI). Artykuł traktuje zasięg przestrzenny jako naturalną jednostkę analizy lokalnych zjawisk - przeniosłem ten argument na decyzję: granica administracyjna dzielnicy to weryfikowalny, stabilny punkt odniesienia dla zakresu analizy, nawet jeśli zjawisko (aktywność dzika) przekracza te granice.\n\nMoja interpretacja: granica administracyjna to pragmatyczny kompromis - świadomie nie odzwierciedla zasięgu ekologicznego dzika, ale daje stabilny, weryfikowalny obszar analizy. Praca Kopczewskiej dała mi językowe ramy dla tej decyzji.",
    rejected:
      "Formalna analiza zasięgu przestrzennego samorządów – nie dotyczy zjawisk przyrodniczych. Zakres administracyjny nie odzwierciedla zasięgu ekologicznego dzika (migracje przekraczają granice dzielnicy).",
    inCode:
      "r_scripts/research/01_generate_voronoi.R:92-100 (PostgreSQL query: SELECT geom FROM boundaries WHERE name = 'bialoleka')\nsrc/sightings/management/commands/init_grids.py:106-107 (to samo dla grid generation)",
  },
];

const LECTURES = [
  {
    type: "lecture",
    authors: "Kopczewska, K.",
    year: 2025,
    title: "Temat 3: Statystyki przestrzenne / Spatial statistics",
    venue:
      "Ekonometria i statystyka przestrzenna w R. Wydział Nauk Ekonomicznych UW. Updated 03.10.2025",
    doi: null,
    adopted:
      "moran.test() dla globalnej Morana I (krok 7), localmoran() → LISA quadranty, struktura workflow: Moran I OLS residuów → sygnał autokorelacji → decyzja o modelu przestrzennym.\n\nMoja interpretacja: ta struktura workflow stała się szkieletem kroku 7 przepływu: OLS, Moran I na resztach, jeśli istotny - SAR/SEM. Moran I nie jako finalna diagnostyka, ale jako kryterium selekcji: czy w ogóle model przestrzenny jest potrzebny.",
    rejected:
      "LOSH (Local Spatial Heteroscedasticity) – poza scope. Join-count test dla danych binarnych – Y jest continuous w RESEARCH mode, nie binarne.",
    inCode:
      "r_scripts/research/07_diagnostics.R: L299-327 (moran.test, krok 7 - global Moran's I) + L419-462 (localmoran → LISA HH/LL/HL/LH/NS quadrants)",
  },
  {
    type: "lecture",
    authors: "Kopczewska, K.",
    year: 2025,
    title:
      "Temat 4: Modele zależności przestrzennych / Spatial dependence models",
    venue:
      "Ekonometria i statystyka przestrzenna w R. Wydział Nauk Ekonomicznych UW. Updated 03.10.2025",
    doi: null,
    adopted:
      "Pełny opis SAR/SEM: dlaczego OLS jest obciążone (biased & inconsistent) gdy istnieje lag przestrzenny Y, jak lm.RStests() wskazuje właściwy model, estymacja przez MLE z lagsarlm()/errorsarlm(). Efekty bezpośrednie i pośrednie (impacts). W mojej implementacji używam AIC zamiast LM cascade - zob. wpis Elhorst 2010 dla uzasadnienia.",
    rejected:
      "Podejście OLS-only – jak wykazano w materiale, MNK jest obciążone i niezgodne w obecności autokorelacji przestrzennej zmiennej zależnej. Duża próba nie pomaga.",
    inCode:
      "r_scripts/02_spatial_models.R:340-408 (SAR: lagsarlm via MLE + SEM: errorsarlm via MLE)\nr_scripts/research/07_diagnostics.R:525-580 (impacts display - direct/indirect/total)",
  },
  {
    type: "lecture",
    authors: "Kopczewska, K.",
    year: 2025,
    title:
      "Temat 5: Modele interakcji przestrzennych / Spatial interactions model",
    venue:
      "Ekonometria i statystyka przestrzenna w R. Wydział Nauk Ekonomicznych UW. Updated 04.10.2025",
    doi: null,
    adopted:
      'Z wykładu zaadoptowałem ramy efektów rozlewania (spillover): aktywność dzicza w kaflu i wpływa na sąsiadów j przez człon ρWy w SAR. Tobler\'s First Law jako formalne uzasadnienie, że bliskość przestrzenna ma znaczenie - bez tego założenia kNN i tessW byłyby arbitralne.\n\nMoja interpretacja: „spatial lag transmituje ryzyko" to nie metafora - to formalny mechanizm ρWy, gdzie W = macierz wag (tessW lub kNN). Im wyższy ρ, tym silniejszy spillover. Dla dzika: ryzyko rozlewa się z obszarów koncentracji (hotspotów) do sąsiednich kafli, co SAR modeluje explicite.',
    rejected:
      "Pełny model interakcji przestrzennych (gravity model z macierzą T przepływów). Nie obserwujemy realnych przepływów dzika między kaflami, tylko zliczenia obecności per kafel.",
    inCode:
      "r_scripts/02_spatial_models.R:340-408 (ρ w SAR: lagsarlm, λ w SEM: errorsarlm)",
  },
  {
    type: "lecture",
    authors: "Kopczewska, K.",
    year: 2025,
    title: "Zajęcia 6: Regresja ważona geograficznie (GWR) & dryf przestrzenny",
    venue:
      "Ekonometria i statystyka przestrzenna w R. Wydział Nauk Ekonomicznych UW. Updated 05.10.2025",
    doi: null,
    adopted:
      'Konceptualne rozróżnienie: autokorelacja przestrzenna (podobieństwo sąsiadów) vs. dryf przestrzenny (kierunkowość efektów). Oba procesy mogą współistnieć - SAR/SEM absorbuje autokorelację, ale dryf wymaga diagnostyki reszt.\n\nFormalne równanie GWR: yᵢ = β₀(uᵢ,vᵢ) + Σₖ xᵢ,ₖ βₖ(uᵢ,vᵢ) + εᵢ, gdzie (uᵢ,vᵢ) są współrzędnymi geograficznymi, a βₖ(uᵢ,vᵢ) to lokalne współczynniki estymowane per obserwacja z ważoną metodą najmniejszych kwadratów (Brunsdon et al. 1996). Funkcje jądra: Gaussian (łagodny zanik), Bi-square (zero poza przepustowością, bandwidth), Adaptive vs Fixed. Selekcja przepustowości: AICc preferowane nad CV dla danych ekologicznych ("more robust than CV for small N").\n\nProgi stabilności (za Zajęciami 6): "N < 100: Do NOT use GWR - exploratory only. Unacceptable non-convergence; inflated Type I errors". "100 < N < 200: GWR wciąż wysoce niestabilny". "N = 500-5,000 ACCEPTABLE Stable convergence". Nasz tryb FAST (9875 cells) > akceptowalny górny próg, tryb PUB (1:1 z próbą, 3500 przy pełnej) mieści się w akceptowalnym zakresie, ale tryby FAST/PUB wybrane ze względu na szybkość i spójność metodologiczną, nie pod kątem GWR.',
    rejected:
      "Aktywnego przepływu GWR nie utrzymuję - to świadoma migracja na SAR/SEM z refaktoryzacji 2026. Powody są trzy i wszystkie sprowadzają się do jednego pytania: co da się zweryfikować? Jeden globalny model z interpretowalnym ρ/λ można skontrolować ręcznie; 3500+ lokalnych modeli z różnymi współczynnikami - już nie. Do tego SAR/SEM jest stabilny w całym naszym zakresie (PUB 1:1 z próbą, FAST 9875 cells), a architektura z jednym modelem i wykrywaniem klastrów LISA post-hoc po prostu lepiej pasuje do projektu portfolio niż pełny GWR z analizą współczynników per kafel. Po migracji zostały zaszłości: test_r_pipeline.py (@pytest.mark.skip, commit 88b4049) odwołuje się do tabel analytics_gwr_result, których w aktualnym schemacie już nie ma, a pakiet GWmodel wyleciał z Dockerfile.r (commit 61f983b).",
    inCode:
      "r_scripts/research/07_diagnostics.R:299-327 (moran.test na resztach modelu - test dryfu przestrzennego po estymacji SAR/SEM)",
  },
  {
    type: "lecture",
    authors: "Kopczewska, K.",
    year: 2025,
    title:
      "Class 9: Detection of agglomeration – tessellation, entropy, Clark-Evans test, DBSCAN",
    venue: "Spatial econometrics in R. Wydział Nauk Ekonomicznych UW",
    doi: null,
    adopted:
      'Z wykładu zaadoptowałem dwa koncepty metodologiczne. Pierwszy: tessW - macierz wag przestrzennych zbudowana na siatce Voronoi, gdzie siłę połączenia między kaflem i a j definiuje długość ich wspólnej granicy. Zaimplementowałem to własnoręcznie w PostGIS: ST_Length(ST_CollectionExtract(ST_Intersection(a.geometry, b.geometry), 2)::geography) - każda para sąsiadów otrzymuje wagę proporcjonalną do metrów wspólnej granicy, nie do odległości centroidów.\n\nDrugi: ETA (Entropy-Tessellation-Agglomeration) jako miara skupienia rozkładu przestrzennego kafli Voronoi. Entropia Shannona udziałów powierzchni kafli: H_emp = -sum(shares * log(shares)), H_rel = H_emp / H_max. Wysoka H_rel (→1) = kafle podobnej wielkości (obserwacje rozłożone równomiernie), niska H_rel (→0) = kafle silnie zróżnicowane (obserwacje skupione w jednym obszarze).\n\nMoja interpretacja: oba koncepty adresują ten sam problem - jak zmierzyć «nieregularność» tessellacji Voronoi z obserwacji terenowych. tessW przekłada tę nieregularność na wagi modelu przestrzennego; ETA raportuje ją jako diagnostykę skupienia. Wzajemnie komplementarne w tym przepływie.',
    rejected:
      'Clark-Evans test, QDC (Quick Density Clustering), FLE (Focal Local Entropy), DBSCAN - narzędzia do analizy wzorców punktowych, nie do regresji przestrzennej. Clark-Evans test zakłada dane punktowe z hipotezą zerową CSR (Complete Spatial Randomness) - brak sensownej hipotezy zerowej dla administracyjnych granic kafli Voronoi.\n\nKrytyka MAUP z wykładu Class 9 (uczciwie przyznaję): "The aggregation of point data within administrative regions generates the Modified Areal Unit Problem (MAUP), what may bias all computations". Plus: "Regular cells of the same size however, do not follow the natural spatial pattern of data, and thus are still an arbitrary division of space". DBSCAN i FLE jako metody wzorców punktowych całkowicie unikają MAUP. Mój wybór LISA via spdep wynika z kompromisu: LISA daje formalne p-wartości per kafel (testowanie hipotez) + integracja z przepływem SAR/SEM kosztem wrażliwości na MAUP. Metody wzorców punktowych (DBSCAN, QDC, FLE) pozostają uzasadnionymi alternatywami - poza aktualnym zakresem portfolio, z potencjałem po publikacji.',
    inCode:
      "r_scripts/research/05_matrix_w.R:284-314 (tessW custom: ST_Length wspólnych granic via PostGIS, wagi proporcjonalne do metrów)\nr_scripts/research/07_diagnostics.R:465-516 (ETA custom: H_emp/H_max/H_rel Shannon entropy udziałów powierzchni kafli)\nenv var: RESEARCH_RUN_ETA (1/0, default 0 - krok 7 opcjonalny)",
  },
  {
    type: "lecture",
    authors: "Kopczewska, K.",
    year: 2025,
    title: "Class 12: Bootstrapped spatial microeconometrics",
    venue:
      "Spatial econometrics in R. Wydział Nauk Ekonomicznych UW. Oparte na: Kopczewska (2023), Scandinavian Journal of Statistics",
    doi: null,
    adopted:
      'Pomysł klastrowania PAM do wyboru reprezentatywnego podzbioru danych (inspiracja dla logiki ensemble). Voronoi jako kalibracja przestrzeni przy predykcji: nowe punkty „wpadają" do istniejących kafli przez tessellację.',
    rejected:
      "Pełny przepływ BootSpatReg() - wymaga próby min. 50K obserwacji do sensownego resamplingu podpróby. Nasz tryb PUB (1:1 z próbą, zaledwie 3500 przy pełnej) lub tryb FAST (9875 cells) - bootstrap subsampling teoretycznie możliwy, ale wymaga min. 50K obserwacji dla sensownego resamplingu według specyfikacji BootSpatReg(). Poza aktualnym zakresem portfolio.",
    inCode:
      "r_scripts/05_ensemble_prediction.R:146-154 (wagi ensemble: W_DENSITY=0.30, W_SPATIAL=0.40, W_ETA=0.30)",
  },
  {
    type: "lecture",
    authors: "Kopczewska, K.",
    year: 2025,
    title:
      "Temat 7: Przestrzenno-czasowa stabilność klastrów GWR / Spatio-temporal stability of GWR clusters",
    venue:
      "Ekonometria przestrzenna w R. Wydział Nauk Ekonomicznych UW. Updated 16.10.2025. Oparte na: Kopczewska & Ćwiakowski (2021)",
    doi: null,
    adopted:
      'Algorytm STS (Kopczewska 2021, Land Use Policy): (1) estymacja GWR per okres, (2) k-means klastrowania współczynników per okres, (3) rasteryzacja + mediana ID klastra per kafel siatki, (4) porównanie podziałów między okresami z Adjusted Rand Index (ARI), (5) wyjście: macierz kolorów okres-do-okresu.\n\nKopczewska definiuje problem: "The spatio-temporal stability problem is to detect if the similarity of coefficients, indicating whether they should belong to the same cluster, is stable in time over space".\n\nMoja interpretacja: STS jest konceptem trafnym dla monitoringu fauny (wzorce sezonowe + 5-letni zakres danych), ale blokery techniczne: po pierwsze, funkcja STS() w spatialModel wymaga T≥2 okresów ("Wymagane: dane z kilku okresów (T ≥ 2, inaczej funkcja zwróci błąd)"); po drugie, podział 3500 zgłoszeń na lata daje per-period N ~700 - wciąż powyżej progu katastrofy N<500 - stabilność GWR nie jest już blokerem, ale GWR to aktualnie zaszłość techniczna (zob. wpis Zajęcia 6: N<500 catastrophic); i wreszcie GWR to aktualnie zaszłość techniczna w naszym przepływie.',
    rejected:
      "Pełnej analizy stabilności przestrzenno-czasowej w aktualnym przepływie - brak czterech warunków naraz: reaktywacja GWR (aktualnie zaszłość, zob. wpis Zajęcia 6 GWR), wystarczające N per okres, metodologia stratyfikacji sezonowej i zebranie rozszerzonej serii czasowej. BootSpatReg i STS to nie to samo, choć często mylone: BootSpatReg = przestrzenna regresja bootstrapowana z selekcją medoidów PAM dla dużych danych; STS = stabilność klastrów oparta na ARI między okresami. STS odroczone po publikacji jako rozszerzenie wielookresowe.",
    inCode:
      "r_scripts/research/07_diagnostics.R:415-462 (LISA HH/LL/HL/LH/NS counts per run)",
  },
];

const PACKAGES = [
  {
    type: "package",
    authors: "Kopczewska, K. et al.",
    year: null,
    title:
      "spatialModel (fork spatialWarsaw): Spatial econometrics tools for Warsaw-school spatial analysis",
    venue: "R package 0.9.0. GitHub: poktam/spatialWarsaw (upstream), lokalnie: spatialModel",
    doi: null,
    adopted:
      "Z pakietu spatialModel zaadoptowałem trzy koncepty metodologiczne (nie kod): tessW jako adaptacja macierzy W opartej na tessellacji, bestW jako k-NN z selekcją przez AIC, ETA jako entropia Shannona na polach kafli tessellacji.\n\nStatus: CONCEPT REF (cytowanie metodologiczne) + formalna deklaracja zależności na etapie budowania. Lokalna kopia pakietu w repozytorium, instalacja w Dockerfile.r ze źródła lokalnego: install.packages('/app/spatialModel', repos=NULL, type='source'). DESCRIPTION formalnie deklaruje 20 pakietów w Imports (spatialreg, GWmodel, spdep, sf, terra, dbscan, cluster, dplyr, ggplot2, stargazer, gridExtra, sampling, benford.analysis, DescTools, fossil, sp, rlang + 3 base R).\n\nMoja interpretacja: plan przed porządkowaniem (SPATIALWARSAW_ANALYSIS.md) zakładał pełną adopcję - konkluzja brzmiała: \"NATYCHMIAST: devtools::install_github('poktam/spatialWarsaw')\". W refaktoryzacji 2026 zmieniłem podejście na CONCEPT REF + własne implementacje z trzech powodów: stabilność (pakiet nie jest na CRAN, instalacja z GitHub wprowadza sprzężenie i ryzyko cichego błędu), audytowalność (własne implementacje są w pełni testowalne i podatne na debugowanie, funkcje spatialModel są czarną skrzynką metodologiczną), a do tego niezależność (kluczowe zależności runtime dostarcza obraz bazowy rocker niezależnie). Pakiet pozostaje cytowaniem metodologicznym - komentarze w kodzie jawnie wskazują akademicką proweniencję algorytmów.\n\nUczciwie: analiza sprzed porządkowania podnosiła trzy argumenty za pakietem - tessW() bez parametrów kontra k-NN z arbitralnym k, ETA() z automatyczną transformacją CRS do EPSG:3857, STS() jako przepływ w jednym wywołaniu. Argument o tessW() zachowuje moc - w naszym przepływie stosuję knn z selekcją k przez AIC (k wywodzone z danych zamiast arbitralnego), lecz nie eliminuje fundamentalnej krytyki. Pełna konwersja do przepływu tessW pozostaje uzasadnioną alternatywą - poza aktualnym zakresem portfolio.",
    rejected:
      "Bezpośredniego importu pakietu (library(spatialModel)) nie użyłem. Pakiet zainstalowany w Dockerfile.r ze źródła, ale nigdy nie ładowany w aktywnych skryptach R (grep library(spatialModel) = zero hits w r_scripts/).\n\nPoleganie na łańcuchu zależności przechodnich dla spatialreg - audyt CC z 2026-05-26 zweryfikował empirycznie, że spatialreg pochodzi z obrazu bazowego rocker/geospatial:4.3.2 (Built 2024-02-07), niezależnie od łańcucha spatialModel. spatialModel DESCRIPTION deklaruje spatialreg jako Imports, ale obraz bazowy wyprzedza etap spatialModel w kolejności budowania - usunięcie pakietu nie złamałoby spatialreg ani aktywnego przepływu.\n\nInstalacja z GitHub (devtools::install_github) - pakiet nie jest na CRAN, instalacja z GitHub dla produkcyjnego worker-r wprowadza sprzężenie z dostępnością zewnętrznego repozytorium + ryzyko cichego błędu instalacji (empirycznie zaobserwowane: aktualny obraz z 2026-01-18 nie ma spatialModel mimo kroku instalacji w Dockerfile.r). Wybrałem instalację ze źródła lokalnego z kopią pakietu w repozytorium.\n\nWłasna implementacja daje audytowalność każdej operacji.",
    inCode:
      'library(spatialreg) ×3 (bezpośrednio, nie via spatialModel):\nr_scripts/02_spatial_models.R:27\nr_scripts/research/05_matrix_w.R:150\nr_scripts/research/07_diagnostics.R:121\n\nMethodology references (komentarze):\nr_scripts/02_spatial_models.R:5 - "# ŹRÓDŁO: spatialWarsaw (lagsarlm, errorsarlm, sacsarlm)"\nr_scripts/research/05_matrix_w.R:284-314 - tessW reimplementation (custom)\nr_scripts/research/05_matrix_w.R:140-200 - bestW reimplementation z AIC selection\nr_scripts/research/07_diagnostics.R:465-516 - ETA Shannon entropy reimplementation\n\n0 calls library(spatialModel) w aktywnych r_scripts/\n0 calls spatialModel:: poza komentarzami',
  },
  {
    type: "package",
    authors: "Bivand, R., Pebesma, E., Gómez-Rubio, V.",
    year: null,
    title: "spatialreg: Spatial Regression Analysis",
    venue: "R package, CRAN: spatialreg",
    doi: null,
    adopted:
      "lagsarlm() – estymacja modelu SAR (Spatial Autoregressive) przez MLE. errorsarlm() – estymacja modelu SEM (Spatial Error). impacts() – efekty bezpośrednie i pośrednie (direct/indirect/total) raportowane w kroku 7.",
    rejected:
      "SLX (Spatial Lag of X) – nie przetestowano, LM tests nie wskazały potrzeby. spBreg_*() (MCMC Bayesian) – zbędna złożoność obliczeniowa dla naszej skali (PUB 1:1 z próbą, FAST 9875 cells) względem benefit nad SAR/SEM. SDM z SDM-specific impacts – Elhorst (2010) uzasadnia parsimony.",
    inCode:
      "r_scripts/02_spatial_models.R:340-408 (lagsarlm - SAR, errorsarlm - SEM, oba via MLE)\nr_scripts/research/07_diagnostics.R:525-580 (impacts display - direct/indirect/total spillovers)",
  },
];

// ─── Sekcje nawigacji ─────────────────────────────────────────────────────────

const SECTIONS = [
  { id: "papers", label: "Artykuły", count: PAPERS.length },
  { id: "lectures", label: "Mat. kursowe", count: LECTURES.length },
  { id: "packages", label: "Pakiety R", count: PACKAGES.length },
];

// ─── Główny komponent ─────────────────────────────────────────────────────────

const LiteratureTab = () => {
  const [activeSection, setActiveSection] = useState("papers");

  const entries = {
    papers: PAPERS,
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
              ${
                activeSection === sec.id
                  ? "bg-blue-600/30 text-blue-300 border border-blue-600/40"
                  : "text-gray-400 hover:text-white hover:bg-gray-700/50 border border-transparent"
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
            Każda pozycja: co zaadaptowaliśmy, co odrzuciliśmy i dlaczego, gdzie
            w kodzie.
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
      title: "Artykuły recenzowane",
      desc: "Prace naukowe, których metodologia lub koncepcje zostały wykorzystane lub świadomie odrzucone podczas budowy RESEARCH pipeline.",
    },
    lectures: {
      title: "Materiały kursowe",
      desc: 'Wykłady z kursu "Ekonometria i statystyka przestrzenna w R" (dr hab. K. Kopczewska, WNE UW, 2025). Każde zajęcia dały cegielkę do rozumienia całości.',
    },
    packages: {
      title: "Pakiety R",
      desc: "Biblioteki R i narzędzia analityczne. Aktywnie importowane w przepływie: spdep, spatialreg, RPostgres, sf i inne. Inspiracja metodologiczna (zainstalowane w Dockerfile.r jako CONCEPT REF, bez library() w skryptach R): spatialModel - koncepty zaadoptowane i zaimplementowane własnoręcznie.",
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
