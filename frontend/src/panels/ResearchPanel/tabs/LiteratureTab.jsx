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
    authors: "K. Kopczewska",
    year: 2021,
    title:
      "Entropy as measure of agglomeration. Interactions of business locations and housing transactions in Warsaw metropolitan area",
    venue:
      "in: Reggiani, Schintler, Czamanski, Patuelli (eds.), Handbook on Entropy, Complexity, and Spatial Dynamics: The Rebirth of Theory?, Edward Elgar 2021",
    doi: null,
    adopted:
      "Z tej pracy zaadaptowałem rdzeń metodologii entropia-tessellacja-aglomeracja: udziały pól kafli Voronoi traktowane jak prawdopodobieństwa, entropia Shannona policzona na tych udziałach i normalizacja przez H_max = log(n). Równania (1), (3) i (4) artykułu implementuję wiernie w 07_diagnostics.R:451-502 - H_emp = -Σ(p_i · log(p_i)), gdzie p_i = area_i / Σarea, H_max = log(n), H_rel = H_emp / H_max. Całość liczę własnym kodem, bez ładowania pakietu spatialWarsaw (w projekcie ma on status odniesienia metodologicznego) - dzięki temu każda operacja numeryczna pozostaje pod kontrolą. Ścieżką nauki tej metodologii był wykład CLASS 9 (Spatial Econometrics 09 - tesselation and entropy) K. Kopczewskiej.\n\nMoja interpretacja: artykuł rozwiązuje fundamentalny problem MAUP (Modified Areal Unit Problem) przez tessellację Voronoi - znikają arbitralne granice administracyjne. W naszym przepływie obliczeniowym H_rel gra dwie role: po pierwsze mierzy aglomerację obserwacji (główne zastosowanie z artykułu), po drugie służy jako test zdrowego rozsądku dla macierzy W - wartość bliska 1.0 potwierdza, że kafle mają zbliżone powierzchnie i W nie jest zdegenerowana. Ta druga rola to już nasz pomysł projektowy, nie pochodzi z artykułu.",
    rejected:
      "Surowego ETA jako zmiennej Y modelu nie przyjąłem - dziki nie tworzą skupisk jak firmy, ETA mierzy skupienie wzorca punktowego, nie ciągłe ryzyko na obszarze. Y musi być ciągłe na kafel - domyślnie log_intensity = log((sighting_count + 1) / area_km2), czyli logarytm intensywności zgłoszeń na pole (opcjonalnie count_pop / inv_pop / log_count), nie globalnym skalarem entropii porównującym ze stanem maksymalnego rozproszenia.\n\nEntropii dwuwymiarowej (bivariate cross-product entropy) między dwoma typami punktów nie przyjąłem - artykuł analizuje business + population OSOBNO (jednozmiennie) i porównuje wizualnie, bez łącznej formuły matematycznej.\n\nNadmiarowość Shannona O = 1 - relH (Eq 5 artykułu) - matematycznie równoważna 1 - H_rel, czyli zbędne powielanie.",
    inCode:
      "r_scripts/research/07_diagnostics.R:451-502 (H_emp, H_max, H_rel - własna implementacja entropii Shannona). Przygotowanie tessellacji w 01_generate_voronoi.R (artykuł proponuje tessellację Voronoi jako fundament metodologii).",
  },
  {
    type: "paper",
    authors: "M. Kubara, K. Kopczewska",
    year: 2024,
    title:
      "Akaike information criterion in choosing the optimal k-nearest neighbours of the spatial weight matrix",
    venue: "Spatial Economic Analysis, 19(1), 73-91",
    doi: "10.1080/17421772.2023.2176539",
    adopted:
      'M. Kubara i K. Kopczewska mierzą się z tym samym problemem: jak wybrać k w macierzy k-NN bez arbitralności? Ich odpowiedź - minimalizacja AIC modelu spatialreg po kandydatach k - przyjąłem co do zasady, z jedną świadomą różnicą. Zaimplementowałem samodzielnie: pętla po k ∈ [k_min, k_max], na każde k: buduję kNN, symetryzuję (make.sym.nb(), bo spatialreg wymaga symetrii), nb2listw(), i dopasowuję model z samym wyrazem wolnym (bez predyktorów). Różnica wobec artykułu: artykuł prowadzi selekcję k na modelu SDM (spatial Durbin, lagsarlm z Durbin=TRUE, z predyktorami i WX - "we use the spatial Durbin model (SDM) specification", s. 80), a ja na uproszczonej formie lag z samym wyrazem wolnym (lagsarlm(Y ~ 1)) - oba modele są z rodziny lag (zawierają ρWY), nie SEM. Wybrałem intercept-only lag, bo finalnie estymowany SAR w 02_spatial_models.R też jest w formie lag - chciałem, żeby kryterium doboru W odpowiadało dopasowywanemu modelowi. Zwycięski k = najniższy AIC. Nie wywołuję bestW() z pakietu spatialWarsaw - własna implementacja w 05_matrix_w.R.\n\nUczciwe zastrzeżenie: knn_aic jest operacyjnym defaultem (RESEARCH_W_METHOD=knn_aic) i to nim policzono WSZYSTKIE dotychczasowe wyniki; contiguity (przyległość) (Queen, poly2nb) oraz tessW są dostępne i metodologicznie uzasadnione (principled), ale NIE są domyślne i nie były dotąd uruchamiane. pętla po W też używa modelu z samym wyrazem wolnym (predyktory nie są dostępne na etapie budowania W), więc knn_aic ma charakter heurystyki wrażliwościowej - bardziej pryncypialnym kryterium doboru jest contiguity (przyległość) / tessW (dostępne, choć nieuruchamiane).\n\nMoja interpretacja: AIC jako kryterium selekcji sąsiedztwa to tania decyzja - jedna dodatkowa pętla, a eliminujemy całą klasę błędów doboru k. Dla dzika w Białołęce nie zakładam z góry że "5 sąsiadów to naturalny zasięg" - dane decydują.\n\nArtykuł stwierdza wprost (s. 76): "AIC outperforms the logLik, LR and J-test methods in testing non-nested spatial models" - bezpośrednie uzasadnienie empiryczne dla mojej pętli knn_aic, gdzie porównuję modele z różnymi macierzami W (non-nested case).',
    rejected:
      'Odrzuciłem stałe k narzucone z góry (klasyczna praktyka: k=5 albo k=8). Dobór k a priori jest arbitralny - nie wiemy z góry co jest "naturalnym sąsiedztwem" dla rozmieszczenia dzika w Białołęce.',
    inCode:
      "r_scripts/research/05_matrix_w.R (pętla AIC: lagsarlm(Y~1) per k ∈ [k_min, k_max], wybór min(AIC); fallback ponawia lagsarlm z Durbin=FALSE, przy braku zbieżności - contiguity poly2nb). Operacyjny default W = knn_aic (nim policzono wszystkie dotychczasowe wyniki); contiguity (przyległość) (poly2nb, Queen) / tessW dostępne i principled, ale nie domyślne i nieuruchamiane.\nsrc/analytics/models_research.py:150 (w_method default=WMethod.KNN_AIC) + :368 (eksport RESEARCH_W_METHOD=self.w_method aktywuje tę ścieżkę)",
  },
  {
    type: "paper",
    authors: "J.P. Elhorst",
    year: 2010,
    title: "Applied Spatial Econometrics: Raising the Bar",
    venue: "Spatial Economic Analysis, 5(1), 9-28",
    doi: "10.1080/17421770903541772",
    adopted:
      'Od J.P. Elhorst przejąłem dwie rzeczy. Pierwsza: taksonomię SAR/SEM/SDM jako spójną rodzinę modeli przestrzennych - to dało mi ramy do myślenia o tym, który model dobrać do danych z rozmieszczenia dzika. Druga: efekty przestrzenne direct/indirect/total (impacts z LeSage & Pace 2009, spopularyzowane przez Elhorst). W moim przepływie dla modelu SAR obliczam impacts(best_result$model, listw=listw, R=500), który rozkłada efekt predyktora na direct (jednostka sama), indirect (przez sąsiadów) i total - terminologia J.P. Elhorst/LeSage & Pace.\n\nJedno tylko odrzuciłem: LM cascade jako mechanizm auto-selekcji SAR vs SEM.\n\nInterpretację parametrów opieram na ramach Manski\'s spatial multiplier framework: ρ (interakcja endogeniczna) - decyzja jednostki przestrzennej zależy od decyzji podjętych przez inne jednostki (parafraza Elhorsta, nie cytat dosłowny) - dyfuzja szoków przez odwrotną transformację przestrzenną. θ (interakcja egzogeniczna, efekty lokalne) - zależność od zmiennych objaśniających (X) innych jednostek. λ (efekty skorelowane) - "similar unobserved environmental characteristics result in similar behaviour" - rozlewanie na niemodelowane regiony. W naszym przepływie: ρ z lagsarlm (SAR), λ z errorsarlm (SEM), porównanie AIC wybiera dopasowanie.\n\nObrona podejścia AIC-only, zgodnie z własnym zastrzeżeniem J.P. Elhorst (pp. 17): "tests for significant differences between log-likelihood function values, such as the LR-test, can formally not be used" dla non-nested models. Nasza pętla knn_aic porównuje modele z różnymi W (różne k) - to przypadek modeli nie-zagnieżdżonych (non-nested) → LR cascade formalnie nieuzasadniony → AIC uzasadniony. Plus per M. Kubara & K. Kopczewska 2024 (zob. oddzielny wpis): empiryczna wyższość AIC dla modeli nie-zagnieżdżonych w przestrzeni.\n\nUczciwie trzeba przyznać, że ta decyzja ma przeciwników. Burnham i Anderson ostrzegają przed przeszukiwaniem danych (data mining): AIC jest poprawny między kandydatami zdefiniowanymi a priori, a przy ponad 50 wariantach należałoby korygować wielokrotne testowanie. Nasza pętla ma jednak ograniczone k ∈ [k_min, min(k_max, n-1)] (k_min ∈ {2,5}, k_max ∈ {30,50}) z uzasadnieniem teoretycznym - to nie jest ślepe przeszukiwanie. Harris i Kravtsova (2009, za J.P. Elhorstem) idą dalej: selekcja W przez AIC znajduje "a local maximum among the competing models and not necessarily a correctly specified W". A Florax et al. (2003) - jak referuje J.P. Elhorst (s. 16) - pokazują, że rozszerzanie równania regresji o zmienne opóźnione przestrzennie, warunkowane wynikami testów na błędną specyfikację (kaskada LM, specific-to-general), lepiej odtwarza prawdziwy mechanizm generujący dane (DGP) niż podejście general-to-specific (model Durbina). Na oba zarzuty odpowiadamy tym samym: diagnostyki post-hoc Moran/LISA w research/07_diagnostics.R sprawdzają, czy model końcowy przechodzi kontrole autokorelacji przestrzennej. Gdyby przeszukiwanie wybrało zły model - reszty by to zdradziły.',
    rejected:
      "Odrzuciłem LM cascade (LM-Lag → LM-Error → Robust LM-Lag → Robust LM-Error → decision tree) z trzech powodów: AIC to powszechnie stosowane kryterium porównania modeli (Burnham & Anderson 2002) - niski koszt poznawczy dla odbiorcy, a LM cascade jest niszowy w ekonometrii przestrzennej. Do tego prostsza implementacja: 2 dopasowania + 1 porównanie AIC kontra 4 testy + drzewo decyzyjne. I wreszcie: AIC trywialnie rozszerza się na SDM, SLX, SAC - LM cascade wymaga osobnych rodzin testów dla każdego.\n\nAIC wskazuje model o lepszym dopasowaniu, ale nie identyfikuje mechanizmu strukturalnego - czy zależność przestrzenna tkwi w Y (SAR) czy w resztach (SEM). Zresztą, LM cascade J.P. Elhorst by to rozróżnił. Wybrałem prostotę nad pryncypialną selekcją. I to wystarczy.\n\nMoja interpretacja: J.P. Elhorst (2010) to fundament metodologiczny projektu - SAR/SEM jako właściwa odpowiedź na problem autokorelacji przestrzennej w danych aglomeracyjnych. Moją decyzją było uproszczenie mechanizmu wyboru, nie odejście od rodziny modeli.",
    inCode:
      "r_scripts/02_spatial_models.R:559-588 (# --- auto: wybor przez AIC ---; if (sar_result$AIC < sem_result$AIC) → SAR, else SEM)\nr_scripts/02_spatial_models.R:592-640 (impacts() - direct/indirect/total, J.P. Elhorst framework, SAR/SDM pooled)\nr_scripts/research/07_diagnostics.R:322-401 (lm.RStests() jako post-hoc diagnostics - obliczane i zapisywane do DB, NIE kryterium wyboru modelu)",
  },
  {
    type: "paper",
    authors: "S. Müller, P. Wilhelm, K. Haase",
    year: 2013,
    title:
      "Spatial dependencies and spatial drift in public transport seasonal ticket revenue data",
    venue: "Journal of Retailing and Consumer Services, 20, 334-348",
    doi: "10.1016/j.jretconser.2013.01.005",
    adopted:
      'Skąd w projekcie o dzikach praca o biletach komunikacji miejskiej w Dreźnie? Stąd, że S. Müller (N=391 dzielnic, 2005) pokazuje zjawisko, które może dotyczyć i nas: relacje między zmiennymi a wynikiem rzadko są stałe w przestrzeni, a ignorowanie tej niestacjonarności uśrednia efekty (averaging effects). Dosłowny cytat: "On a global scale (neglecting these spatial differences) the effect of the promotion might be averaged out."\n\nZachowanie dzików w Białołęce może wykazywać regionalne odwrócenie (regional inversion) - bliskość człowieka przyciąga w jednym klastrze, odpycha w innym. Globalny model SAR/SEM może wskazać wynik bliski zeru, jeśli te efekty się zniosą. Liczebność próby wystarczająca według punktu odniesienia S. Müllera - tryb FAST (9875 kafli) i PUB spokojnie przekraczają N=391 S. Müllera.\n\nMoja interpretacja: wykrywanie dryfu wymaga przepływu GWR i klastrowania współczynników (zgodnie z metodologią Müllera). Pełna analiza dryfu poza aktualnym zakresem portfolio - etap 6 publikacji koncentruje się na globalnym SAR/SEM z diagnostyką post-hoc LISA, a pełny GWR wraca po publikacji (aktualnie zaszłość techniczna).',
    rejected:
      "Bezpośredniego zastosowania przepływu S. Müllera: GWR + testy F1/F3 Leunga + k-means klastrowania współczynników. Wymagałaby reaktywacji przepływu GWR, który świadomie oznaczono jako zaszłość techniczną. Aktualnie stosujemy podejście wyłącznie SAR/SEM z post-hoc wykrywaniem klastrów LISA HH/LL/HL/LH (research/07_diagnostics.R:403-449) - łapiemy część sygnału dryfu, ale bez pełnej regresji lokalnej. Kompromis: stabilność + prostsza architektura kontra utrata wykrywania lokalnej niestacjonarności.",
    inCode:
      "r_scripts/research/07_diagnostics.R:287-321 (moran.test na resztach modelu - test dryfu przestrzennego po estymacji SAR/SEM)",
  },
];

const LECTURES = [
  {
    type: "lecture",
    authors: "K. Kopczewska",
    year: 2025,
    title: "Temat 3: Statystyki przestrzenne / Spatial statistics",
    venue:
      "Ekonometria i statystyka przestrzenna w R. Wydział Nauk Ekonomicznych UW. Updated 03.10.2025",
    doi: null,
    adopted:
      "moran.test() dla globalnej Morana I (krok 7), localmoran() → LISA quadranty, oraz - jako moja własna synteza, NIE z Tematu 3 - workflow: Moran reszt OLS → sygnał autokorelacji → decyzja o modelu (T3 pokazuje Morana na surowej zmiennej + LISA/Gi/LOSH + join-count, nie na resztach modelu).\n\nMoja interpretacja: ta struktura workflow stała się szkieletem kroku 7 przepływu: OLS, Moran I na resztach, jeśli istotny - SAR/SEM. Moran I nie jako finalna diagnostyka, ale jako kryterium selekcji: czy w ogóle model przestrzenny jest potrzebny.",
    rejected:
      "LOSH (Local Spatial Heteroscedasticity) - poza zakresem. Join-count test dla danych binarnych - Y jest ciągłe w trybie BADAWCZYM, nie binarne.",
    inCode:
      "r_scripts/research/07_diagnostics.R:287-321 (moran.test, krok 7 - global Moran's I) + 403-449 (localmoran → LISA HH/LL/HL/LH/NS quadrants)",
  },
  {
    type: "lecture",
    authors: "K. Kopczewska",
    year: 2025,
    title:
      "Temat 4: Modele zależności przestrzennych / Spatial dependence models",
    venue:
      "Ekonometria i statystyka przestrzenna w R. Wydział Nauk Ekonomicznych UW. Updated 03.10.2025",
    doi: null,
    adopted:
      "Pełny opis SAR/SEM: dlaczego OLS jest obciążone (biased & inconsistent) gdy istnieje lag przestrzenny Y, jak lm.RStests() wskazuje właściwy model, estymacja przez MLE z lagsarlm()/errorsarlm(). Efekty bezpośrednie i pośrednie (impacts). W mojej implementacji używam AIC zamiast LM cascade - zob. wpis J.P. Elhorst 2010 dla uzasadnienia.",
    rejected:
      "Podejście OLS-only - jak wykazano w materiale, MNK jest obciążone i niezgodne w obecności autokorelacji przestrzennej zmiennej zależnej. Duża próba nie pomaga.",
    inCode:
      "r_scripts/02_spatial_models.R:362-426 (SAR: lagsarlm via MLE + SEM: errorsarlm via MLE)\nr_scripts/research/07_diagnostics.R:508-564 (impacts display - direct/indirect/total)",
  },
  {
    type: "lecture",
    authors: "K. Kopczewska",
    year: 2025,
    title:
      "Temat 5: Modele interakcji przestrzennych / Spatial interactions model",
    venue:
      "Ekonometria i statystyka przestrzenna w R. Wydział Nauk Ekonomicznych UW. Updated 04.10.2025",
    doi: null,
    adopted:
      'Z wykładu przyjąłem ramy efektów rozlewania (spillover): aktywność dzików w kaflu i wpływa na sąsiadów j przez człon ρWy w SAR. Tobler\'s First Law jako formalne uzasadnienie, że bliskość przestrzenna ma znaczenie - bez tego założenia kNN i tessW byłyby arbitralne.\n\nMoja interpretacja: „spatial lag transmituje ryzyko" to nie metafora - to formalny mechanizm ρWy, gdzie W = macierz wag (tessW lub kNN). Im wyższy ρ, tym silniejszy spillover. Dla dzika: ryzyko rozlewa się z obszarów koncentracji (hotspotów) do sąsiednich kafli, co SAR modeluje wprost.',
    rejected:
      "Pełny model interakcji przestrzennych (gravity model z macierzą T przepływów). Nie obserwujemy realnych przepływów dzika między kaflami, tylko zliczenia obecności na kafel.",
    inCode:
      "r_scripts/02_spatial_models.R:362-426 (ρ w SAR: lagsarlm, λ w SEM: errorsarlm)",
  },
  {
    type: "lecture",
    authors: "K. Kopczewska",
    year: 2025,
    title: "Zajęcia 6: Regresja ważona geograficznie (GWR) & dryf przestrzenny",
    venue:
      "Ekonometria i statystyka przestrzenna w R. Wydział Nauk Ekonomicznych UW. Updated 05.10.2025",
    doi: null,
    adopted:
      'Kluczowe rozróżnienie: autokorelacja przestrzenna (podobieństwo sąsiadów) vs. dryf przestrzenny (kierunkowość efektów). Oba procesy mogą współistnieć - SAR/SEM absorbuje autokorelację, ale dryf wymaga diagnostyki reszt.\n\nFormalne równanie GWR: yᵢ = β₀(uᵢ,vᵢ) + Σₖ₌₁ᴾ xᵢ,ₖ βₖ(uᵢ,vᵢ), gdzie (uᵢ,vᵢ) są współrzędnymi geograficznymi, a βₖ(uᵢ,vᵢ) to lokalne współczynniki estymowane na obserwację z ważoną metodą najmniejszych kwadratów (Brunsdon et al. 1996). Funkcje jądra (z legendy rysunku w wykładzie): Uniform, Triangle, Epanechnikov, Quartic, Triweight, Gaussian, Cosine; promień (bandwidth) stały (fixed) lub zmienny (adaptive) zależnie od lokalnej gęstości. Selekcja przepustowości: wykład pokazuje dobór przez CV (min-CV); preferencję AICc nad CV dla małego N dopisuję jako własną uwagę metodologiczną (nie pada w tym wykładzie).\n\nProgi stabilności GWR (uwaga własna oparta na ogólnej literaturze GWR, NIE cytat z Zajęć 6 - w slajdach ich nie ma): N < 100 - GWR niestabilny (tylko eksploracyjnie); 100-200 - wciąż ryzykowny; ~500-5000 - akceptowalny. Nasz tryb FAST (9875 cells) > akceptowalny górny próg, tryb PUB (1:1 z próbą, 3500 przy pełnej) mieści się w akceptowalnym zakresie, ale tryby FAST/PUB wybrane ze względu na szybkość i spójność metodologiczną, nie pod kątem GWR.',
    rejected:
      "Aktywnego przepływu GWR nie utrzymuję - to świadoma migracja na SAR/SEM z refaktoryzacji 2026. Powody są trzy i wszystkie sprowadzają się do jednego pytania: co da się zweryfikować? Jeden globalny model z interpretowalnym ρ/λ można skontrolować ręcznie; 3500+ lokalnych modeli z różnymi współczynnikami - już nie. Do tego SAR/SEM jest stabilny w całym naszym zakresie (PUB 1:1 z próbą, FAST 9875 cells), a architektura z jednym modelem i wykrywaniem klastrów LISA post-hoc po prostu lepiej pasuje do projektu portfolio niż pełny GWR z analizą współczynników na kafel. ",
    inCode:
      "r_scripts/research/07_diagnostics.R:287-321 (moran.test na resztach modelu - test dryfu przestrzennego po estymacji SAR/SEM)",
  },
  {
    type: "lecture",
    authors: "K. Kopczewska",
    year: 2025,
    title:
      "Class 9: Detection of agglomeration - tessellation, entropy, Clark-Evans test, DBSCAN",
    venue: "Spatial econometrics in R. Wydział Nauk Ekonomicznych UW",
    doi: null,
    adopted:
      'Z wykładu przyjąłem dwa koncepty metodologiczne. Pierwszy: fundament tessellacji Voronoi (podział terenu na kafle, udziały powierzchni jako prawdopodobieństwa) - na nim zbudowałem tessW, macierz wag, gdzie siłę połączenia między kaflem i a j definiuje długość ich wspólnej granicy. Uwaga źródłowa: koncept tessW (macierz W na tessellacji Voronoi) pochodzi z pakietu spatialWarsaw (zob. osobny wpis), nie z tego wykładu - Class 9 używa tessellacji wyłącznie do entropii/udziałów; w samym pakiecie tessW() to binarna przyległość (poly2nb/nb2listw), a ważenie długością wspólnej granicy to moja adaptacja. Zaimplementowałem ją własnoręcznie w PostGIS: ST_Length(ST_CollectionExtract(ST_Intersection(a.geometry, b.geometry), 2)::geography) - każda para sąsiadów otrzymuje wagę proporcjonalną do metrów wspólnej granicy, nie do odległości centroidów.\n\nDrugi: ETA (Entropy-Tessellation-Agglomeration) jako miara skupienia rozkładu przestrzennego kafli Voronoi. Entropia Shannona udziałów powierzchni kafli: H_emp = -sum(shares * log(shares)), H_rel = H_emp / H_max. Wysoka H_rel (→1) = kafle podobnej wielkości (obserwacje rozłożone równomiernie), niska H_rel (→0) = kafle silnie zróżnicowane (obserwacje skupione w jednym obszarze).\n\nMoja interpretacja: oba koncepty adresują ten sam problem - jak zmierzyć «nieregularność» tessellacji Voronoi z obserwacji terenowych. tessW przekłada tę nieregularność na wagi modelu przestrzennego; ETA raportuje ją jako diagnostykę skupienia. Wzajemnie komplementarne w tym przepływie.',
    rejected:
      'Clark-Evans test, QDC (Quick Density Clustering), FLE (Focal Local Entropy), DBSCAN - narzędzia do analizy wzorców punktowych, nie do regresji przestrzennej. Clark-Evans test zakłada dane punktowe z hipotezą zerową CSR (Complete Spatial Randomness) - brak sensownej hipotezy zerowej dla administracyjnych granic kafli Voronoi.\n\nKrytyka MAUP (cytaty z pracy Kopczewska 2021 "Entropy and tesselation", s.4, nie z wykładu Class 9) (uczciwie przyznaję): "The aggregation of point data within administrative regions generates the Modified Aral [sic] Unit Problem (MAUP), what may bias all computations". Plus: "Regular cells of the same size however, do not follow the natural spatial pattern of data, and thus are still an arbitrary division of space". DBSCAN i FLE jako metody wzorców punktowych całkowicie unikają MAUP. Mój wybór LISA via spdep wynika z kompromisu: LISA daje formalne p-wartości na kafel (testowanie hipotez) + integracja z przepływem SAR/SEM kosztem wrażliwości na MAUP. Metody wzorców punktowych (DBSCAN, QDC, FLE) pozostają uzasadnionymi alternatywami - poza aktualnym zakresem portfolio, z potencjałem po publikacji.',
    inCode:
      "r_scripts/research/05_matrix_w.R:284-314 (tessW custom: ST_Length wspólnych granic via PostGIS, wagi proporcjonalne do metrów)\nr_scripts/research/07_diagnostics.R:451-502 (ETA custom: H_emp/H_max/H_rel Shannon entropy udziałów powierzchni kafli)\nenv var: RESEARCH_RUN_ETA (1/0, default 0 - krok 7 opcjonalny)",
  },
  {
    type: "lecture",
    authors: "K. Kopczewska",
    year: 2025,
    title:
      "Temat 7: Przestrzenno-czasowa stabilność klastrów GWR / Spatio-temporal stability of GWR clusters",
    venue:
      "Ekonometria przestrzenna w R. Wydział Nauk Ekonomicznych UW. Updated 16.10.2025. Oparte na: K. Kopczewska & Ćwiakowski (2021)",
    doi: null,
    adopted:
      'Algorytm STS (K. Kopczewska 2021, Land Use Policy): (1) estymacja GWR na okres, (2) k-means klastrowania współczynników na okres, (3) rasteryzacja + dominujące (modalne) ID klastra na kafel siatki, (4) porównanie podziałów między okresami z Adjusted Rand Index (ARI), (5) wyjście: macierz kolorów okres-do-okresu.\n\nK. Kopczewska definiuje problem: "The spatio-temporal stability problem is to detect if the similarity of coefficients, indicating whether they should belong to the same cluster, is stable in time over space".\n\nMoja interpretacja: STS jest podejściem trafnym dla monitoringu fauny (wzorce sezonowe + 5-letni zakres danych), ale blokery techniczne: po pierwsze, funkcja STS() w spatialWarsaw wymaga T≥2 okresów ("Wymagane: dane z kilku okresów (T ≥ 2, inaczej funkcja zwróci błąd)"); po drugie, GWR to aktualnie zaszłość techniczna (zob. wpis Zajęcia 6 GWR - progi stabilności, np. N<100 niestabilny, to uwaga własna, nie z wykładu).',
    rejected:
      "Pełnej analizy stabilności przestrzenno-czasowej w aktualnym przepływie - brak czterech warunków naraz: reaktywacja GWR (aktualnie zaszłość, zob. wpis Zajęcia 6 GWR), wystarczające N na okres, metodologia stratyfikacji sezonowej i zebranie rozszerzonej serii czasowej. BootSpatReg i STS to nie to samo, choć często mylone: BootSpatReg = przestrzenna regresja bootstrapowana z selekcją medoidów PAM dla dużych danych; STS = stabilność klastrów oparta na ARI między okresami. STS odroczone po publikacji jako rozszerzenie wielookresowe.",
    inCode:
      "r_scripts/research/07_diagnostics.R:403-449 (LISA HH/LL/HL/LH/NS counts per run)",
  },
];

const PACKAGES = [
  {
    type: "package",
    authors: "M. Kopyt, K. Kopczewska, M. Kubara, E. Dobrowolska",
    year: null,
    title:
      "spatialWarsaw: Spatial econometrics tools for Warsaw-school spatial analysis",
    venue: "R package 0.9.0. GitHub: poktam/spatialWarsaw",
    doi: null,
    adopted:
      "Z pakietu spatialWarsaw przyjąłem trzy koncepty metodologiczne (nie kod): tessW jako adaptacja macierzy W opartej na tessellacji, bestW jako k-NN z selekcją przez AIC, ETA jako entropia Shannona na polach kafli tessellacji.\n\nWybrałem własne implementacje zamiast bezpośredniego użycia pakietu z trzech powodów: stabilność (pakiet nie jest na CRAN, instalacja z GitHub wprowadza ryzyko cichego błędu), audytowalność (własne implementacje są w pełni testowalne, funkcje spatialWarsaw są czarną skrzynką metodologiczną), niezależność (kluczowe zależności w czasie działania dostarcza obraz bazowy). Pakiet pozostaje cytowaniem metodologicznym - komentarze w kodzie wskazują skąd pochodzi każdy algorytm.\n\nUczciwie: trzy argumenty za pakietem zachowują moc - tessW() bez parametrów kontra k-NN z arbitralnym k, ETA() z automatyczną transformacją CRS do EPSG:3857, STS() jako przepływ w jednym wywołaniu. W naszym przepływie stosuję knn z selekcją k przez AIC (k wywodzone z danych zamiast arbitralnego), lecz nie eliminuje to fundamentalnej krytyki. Pełna konwersja do przepływu tessW pozostaje uzasadnioną alternatywą.",
    rejected:
      "Bezpośredniego importu pakietu nie użyłem - nigdy nie ładowany w aktywnych skryptach R.\n\nInstalacja z GitHub wprowadza sprzężenie z dostępnością zewnętrznego repozytorium i ryzyko cichego błędu; pakiet nie jest na CRAN. Wybrałem instalację ze źródła lokalnego.\n\nWłasna implementacja daje możliwość weryfikacji każdej operacji.",
    inCode:
      'library(spatialreg) ×3 (bezpośrednio, nie przez spatialWarsaw):\nr_scripts/02_spatial_models.R:24\nr_scripts/research/05_matrix_w.R:148\nr_scripts/research/07_diagnostics.R:122\n\nOdniesienia metodologiczne (komentarze):\nr_scripts/02_spatial_models.R:3 - "# ŹRÓDŁO: spatialreg (lagsarlm, errorsarlm, sacsarlm); workflow wzorowany na spatialWarsaw::BootSpatReg"\nr_scripts/research/05_matrix_w.R:279-369 - tessW - własna implementacja (contiguity (przyległość) królowej + dl. wspólnych granic)\nr_scripts/research/05_matrix_w.R - bestW - własna implementacja z selekcją AIC (lagsarlm(Y~1)) w gałęzi knn_aic = operacyjny default wg RESEARCH_W_METHOD\nr_scripts/research/07_diagnostics.R:451-502 - ETA - własna implementacja entropii Shannona\n\n0 calls library(spatialWarsaw) w aktywnych r_scripts/\n0 wykonywalnych wywołań spatialWarsaw:: (token tylko w komentarzach i stringach źródłowych, np. 03_inverse_area_risk.R:28)',
  },
  {
    type: "package",
    authors: "R. Bivand, E. Pebesma, V. Gómez-Rubio",
    year: null,
    title: "spatialreg: Spatial Regression Analysis",
    venue: "R package, CRAN: spatialreg",
    doi: null,
    adopted:
      "lagsarlm() - estymacja modelu SAR (Spatial Autoregressive) przez MLE. errorsarlm() - estymacja modelu SEM (Spatial Error). impacts() - efekty bezpośrednie i pośrednie (direct/indirect/total) raportowane w kroku 7.",
    rejected:
      "SLX (Spatial Lag of X) - nie przetestowano, LM tests nie wskazały potrzeby. spBreg_*() (MCMC Bayesian) - zbędna złożoność obliczeniowa dla naszej skali (PUB 1:1 z próbą, FAST 9875 cells) względem przewagi nad SAR/SEM. SDM jest dostępny jako model wymuszony (model_type=sdm, z impacts direct/indirect/total), ale wykluczony z auto-selekcji AIC - auto porównuje tylko SAR vs SEM (parsymonia, Elhorst 2010).",
    inCode:
      "r_scripts/02_spatial_models.R:362-426 (lagsarlm - SAR, errorsarlm - SEM, oba przez MLE)\nr_scripts/research/07_diagnostics.R:508-564 (impacts display - direct/indirect/total spillovers)",
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
      desc: "Biblioteki R i narzędzia analityczne. Aktywnie importowane w przepływie: spdep, spatialreg, RPostgres, sf i inne. Inspiracja metodologiczna (zainstalowane w Dockerfile.r jako odniesienie metodologiczne, bez library() w skryptach R): spatialWarsaw - koncepty zaadaptowane i zaimplementowane własnoręcznie.",
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
