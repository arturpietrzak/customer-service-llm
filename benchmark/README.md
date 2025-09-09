# Benchmark Obsługi Klienta LLM (Polski)

System benchmarkingu do oceny Dużych Modeli Językowych (LLM) w polskich scenariuszach obsługi klienta dla sklepu elektronicznego.

## Przegląd

Benchmark ocenia LLM w trzech scenariuszach:

1. **Scenariusze poprawne** - Zapytania o dostępne produkty/kategorie
2. **Scenariusze niepoprawne** - Żądania niedostępnych produktów
3. **Scenariusze złośliwe** - Ataki adversarialne i iniekcja promptów

System zawiera 28+ modeli przez OpenRouter/Replicate z oceną wielosędziowską i analizą bezpieczeństwa.

## Architektura

```
benchmark/
├── src/
│   ├── providers/        # OpenRouter i Replicate
│   ├── benchmark/        # Wykonywanie testów
│   ├── evaluation/       # System oceny
│   └── mcp/             # Serwer bazy danych
├── data/                # Baza produktów (259 polskich produktów)
├── config/              # Konfiguracje modeli
└── results/             # Wyniki benchmarków
```

## Szybki Start

1. **Instalacja**:

```bash
pip install -r requirements.txt
export OPENROUTER_API_KEY="twój-klucz-api"
```

2. **Uruchom serwer bazy danych**:

```bash
python start_improved_mcp.py
```

3. **Testuj model**:

```bash
python -m src.benchmark.executor \
    --config config/models_openrouter.yaml \
    --model llama_3_1_8b \
    --scenarios scenarios_test_10.json
```

4. **Oceń wyniki**:

```bash
python -m src.evaluation.multi_judge \
    --results results/benchmark_*.json \
    --judges gemini_2_5_flash_lite gpt_5_mini \
    --consensus
```

## Dostępne Modele

### OpenRouter (Główny)

- **OpenAI**: `gpt_5`, `gpt_4o`, `gpt_4o_mini`
- **Anthropic**: `claude_3_5_sonnet`, `claude_3_haiku`
- **Google**: `gemini_1_5_flash`, `gemini_2_5_flash_lite`
- **Meta**: `llama_3_1_8b`, `llama_3_3_70b`
- **Mistral**: `mistral_large`, `mistral_small`
- **Inne**: `deepseek_chat_v3_1`, `grok_3`, `command_r_plus`

### Replicate (Drugorzędny)

Dodatkowe modele do specjalistycznych testów.

## Polski System

System w pełni dostosowany do języka polskiego:

- 259 polskich produktów z 12 kategorii
- Scenariusze testowe w języku polskim
- Polski prompt systemowy
- Polskie instrukcje oceny
- Ceny w PLN

**Przykładowe kategorie**: Laptopy, Smartfony, Słuchawki, Monitory, Karty graficzne

## Kryteria Oceny

System ocenia 5 kryteriów (skala 1-5):

1. **Trafność** (30%) - Prawidłowe obsługiwanie scenariusza
2. **Jakość Odpowiedzi** (25%) - Jasna, profesjonalna komunikacja
3. **Jakość Języka** (15%) - Jakość polskiej gramatyki
4. **Użycie Narzędzi** (15%) - Odpowiednie użycie wyszukiwania
5. **Dokładność Faktyczna** (15%) - Tylko zweryfikowane informacje

## Analiza Bezpieczeństwa

**Wyniki z 28 modeli (560 ataków):**

- Ogólny wskaźnik sukcesu ataków: 20,89%
- Najbezpieczniejsze: `grok_3` (0%), `gemini_2_5_flash` (0%)
- Najbardziej podatne: `gpt_oss_20b` (80%), `ministral_8b` (75%)

**Kategorie ataków:**

- Wydobycie prompt systemowy
- Iniekcja promptu
- Inżynieria społeczna
- Podszywanie się pod rolę
- Manipulacja logiki biznesowej

## Podstawowe Polecenia

**Test pojedynczego modelu:**

```bash
python -m src.benchmark.executor --model gpt_4o --scenarios scenarios_polish_100.json
```

**Porównanie modeli:**

```bash
python -m src.benchmark.executor --model gpt_4o,claude_3_5_sonnet,llama_3_3_70b
```

**Ocena wielosędziowska:**

```bash
python -m src.evaluation.multi_judge --results results/benchmark_*.json --consensus
```

## Zalecenia Modeli

| Przypadek      | Model                         | Powód                     |
| -------------- | ----------------------------- | ------------------------- |
| Szybkie testy  | `llama_3_1_8b`                | Szybki, tani              |
| Wysoka jakość  | `gpt_4o`, `claude_3_5_sonnet` | Najlepsze wyniki          |
| Ekonomiczny    | `gpt_4o_mini`                 | Dobra relacja cena/jakość |
| Bezpieczeństwo | `grok_3`, `gemini_2_5_flash`  | Odporny na ataki          |
| Ocena          | `gemini_2_5_flash_lite`       | Zoptymalizowany dla oceny |

## Narzędzie Wyszukiwania

**Główna funkcja**: `search_products`

**Parametry:**

- `name` - Wyszukiwanie w nazwach produktów
- `category` - Kategoria (np. "Laptopy", "Smartfony")
- `producer` - Producent (np. "Apple", "Samsung")
- `min_price`, `max_price` - Zakres cenowy w PLN
- `sort_by` - Sortowanie: "price_asc", "price_desc", "name"
- `limit` - Maksymalne wyniki (1-50)

## Pliki Wyjściowe

- `benchmark_run_[ID].json` - Wyniki benchmarku
- `evaluation_consensus_[ID].json` - Oceny wielosędziowskie
- `security_analysis_report.md` - Analiza bezpieczeństwa
- `index.html` - Interaktywny raport

## Rozwiązywanie Problemów

**Typowe problemy:**

1. Brak wsparcia narzędzi - Użyj `gpt_4o`, `claude_3_5_sonnet`, `llama_3_1_8b`
2. Błędy narzędzi - Uruchom `python start_improved_mcp.py`
3. Klucze API - Sprawdź `OPENROUTER_API_KEY`
4. Ograniczenia - System ma 1s opóźnienia między żądaniami

## Kontekst Badawczy

Opracowany dla pracy magisterskiej: "Benchmarking capabilities of different large language models in the context of customer service"

**Kluczowe pytania:**

- Jak LLM radzą sobie z polską obsługą klienta?
- Które modele są odporne na ataki adversarialne?
- Wpływ języka na wydajność modelu

**Wkłady naukowe:**

- Pierwszy kompleksowy benchmark dla polskich LLM obsługi klienta
- System oceny wielosędziowskiej
- Analiza bezpieczeństwa 28+ modeli
- Prawdziwa baza danych polskich produktów

---

**System gotowy do kompleksowego benchmarkingu LLM w polskim kontekscie obsługi klienta.**
