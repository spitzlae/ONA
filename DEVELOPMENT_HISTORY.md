# Development History: AI-Assisted Software Engineering

**Author:** Edgar Spitzlay  
**Period:** May 6 – May 12, 2026 (7 days)  
**Background:** Non-programmer, 60 years old, 15 years SAP Program Management at Roche  
**Tools used:** Claude (via Roche AI Gateway), Google Colab, Gitpod/ONA, Eclipse ADT, SAP BTP Trial  
**Repository:** github.com/spitzlae/ONA  

---

## Phase 1: Crossword Puzzle Solver (May 6–7)

**Starting point:** A single 8,200-line Google Colab notebook for solving German crossword puzzles.

**Work performed:**
- Refactored monolithic notebook into a modular Python package (`kreuzwort/`, 2,014 lines, 12 modules)
- CNN Scanner: TensorFlow/Keras model for grid cell detection
- OCR Pipeline: Tesseract-based text extraction with custom cleaning rules
- 3-Stage Lexikon Lookup: Local SQLite database → Web scraper (Playwright) → LLM fallback
- Backtracking CSP Solver: Constraint satisfaction with arc consistency
- Docker fallback for Playwright browser download in restricted environments
- Built persistent lexikon database (170+ entries for test puzzle)

**Technical decisions:**
- Playwright for web scraping (kreuzwort.ch, kreuzwort-hilfe.de)
- SQLite for lexikon persistence across runs
- Modular architecture: scanner → OCR → lexikon → solver pipeline

---

## Phase 2: Multi-Agent Orchestrator Framework (May 6–8)

**Starting point:** No prior experience with agent architectures.

**Work performed:**
- Built `agency/` package from scratch (~650 lines, 4 files)
- Orchestrator: Analyzes a single prompt, determines required roles (max 5), creates project plan with phases and dependencies
- Agent Runner: Separate LLM instance per role with isolated context
- Dependency Resolution: Agents organized into execution batches based on `depends_on` graph
- Consolidation: Final merge of all agent outputs into coherent document
- Tested with two use cases: Business Plan generation, Gartenbau (landscaping) project

**LLM Integration:**
- Primary: Claude Sonnet via Roche AI Gateway (eu.build-cli.roche.com)
- Fallback: Groq (Llama)
- Authentication: AWS Cognito token flow with `x-build-cli-tool: claude` header
- Fixed header issue blocking Roche proxy access

**Subsequent enhancements (May 8):**
- `--rounds N` parameter for iterative multi-pass refinement with feedback loops between rounds
- HTML export: Markdown → styled HTML with CSS, auto-opens in Windows browser via WSL (`wslpath -w` + `explorer.exe`)
- Timeout handling: 300s timeout, 3 retries with exponential backoff for large consolidation prompts
- Per-round file saving (initial/draft/final)

---

## Phase 3: Investment Portfolio Analysis (May 10)

**Starting point:** Personal multi-position portfolio (stocks, active funds, ETFs). No prior data analysis experience in Python.

**Work performed:**
- Built Colab notebook using `yfinance` for Yahoo Finance data retrieval
- Downloaded historical monthly prices for all positions + DAX benchmark
- Automated purchase price verification against Yahoo historical data
- Calculated yearly performance per position vs. benchmark index
- Dividend impact analysis across all positions
- Identified and corrected data discrepancies (share counts, ticker mismatches, purchase dates)
- Proved that positions appearing as losses were breakeven or positive when dividends included

**Output:** JSON export for further processing, reusable prompt template

---

## Phase 4: SAP BTP ABAP Cloud Environment Setup (May 11–12)

**Starting point:** No Eclipse IDE, no SAP BTP account, no ABAP Cloud experience.

**Work performed:**
- Created SAP BTP Trial account (US East VA, AWS, 90-day trial)
- Activated ABAP Environment booster, downloaded service key
- Installed Eclipse IDE for Java Developers
- Installed ABAP Development Tools (ADT) from tools.hana.ondemand.com
- Connected Eclipse to BTP Trial via service key authentication (browser-based OAuth)
- Created development package `Z_AI_DEMO` under ZLOCAL
- Created first ABAP Cloud class `ZCL_HELLO_AI`

**ABAP programs written and executed:**
- Hello World with system variables (`sy-uname`, `sy-datum`)
- SELECT on CDS Views (`/dmo/i_flight`, `/dmo/i_airport`, `/dmo/i_connection`)
- JSON export using `/ui2/cl_json=>serialize()` — 30 delivery records as JSON output

**Key learnings documented:**
- ABAP Cloud restrictions vs. classic ABAP (no WRITE, no FORM/PERFORM, no direct table access, no SAP GUI)
- Inline declarations (`@DATA()`, escape character `@` in SQL context)
- Released Objects concept (only whitelisted APIs available)
- Joule (SAP AI assistant) not available in Trial accounts
- Correct activation shortcut: Ctrl+Shift+F3 (not F1)

---

## Phase 5: SAP API Hub Integration + Logistics Optimization (May 12)

**Starting point:** No knowledge of SAP Business Accelerator Hub or OR-Tools.

**Work performed:**

### SAP API Hub Sandbox
- Registered on api.sap.com, obtained API Key
- Called three OData APIs from Python (Colab):
  - `API_SALES_ORDER_SRV` — 500 Sales Orders with line items (`$expand=to_Item`)
  - `API_PRODUCT_SRV` — 2,711 Products with descriptions (`$expand=to_Description`)
  - `API_BUSINESS_PARTNER` — 4,000 Business Partners
- Mapped classic SAP tables to OData equivalents: VBAK→SalesOrder, VBRK→BillingDocument, MARA→Product, KNA1→BusinessPartner
- Filtered for finished goods (FERT): 707 products, 98 with weight data
- Joined Orders + Products + Business Partners into consolidated report

### Logistics Optimization
- Assigned realistic city coordinates (GPS) to 27 customer locations across US, Canada, Latin America
- Implemented Haversine distance calculation for great-circle distances
- Built three optimization levels:

**Level 1 — Random baseline:**
- Random week assignment, random route order
- Result: 53 tours, 276,400 km, 138,200 EUR

**Level 2 — Custom optimization (Nearest Neighbor + 2-opt):**
- Distance-based clustering, nearest neighbor heuristic, 2-opt local search improvement
- Brute force for tours ≤7 stops
- Result: 52 tours, 231,770 km, 115,885 EUR (16% reduction)

**Level 3 — Google OR-Tools (industry standard):**
- Installed `ortools` library
- Implemented Vehicle Routing Problem (VRP) with capacity constraints
- Heterogeneous fleet: PKW (100 KG, 5L/100km), Transporter (1000 KG, 10L/100km), LKW (3000 KG, 20L/100km)
- Diesel cost calculation at 1.80 EUR/L
- OR-Tools selected optimal vehicle type per tour automatically
- Result: 3 tours, 23,266 km, 6,678 EUR (**58% cost reduction** vs. baseline)

### Architecture Understanding
- Identified network constraints: BTP Cloud cannot reach Roche proxy, localhost, or Colab
- Evaluated deployment options: Google Cloud Run, AWS Lambda, BTP Free Tier
- Designed target architecture: ABAP (data + UI) ↔ HTTP ↔ Python/Cloud Run (optimization + AI)
- Identified SAP BTP Free Tier vs. Trial differences (persistence, Python deployment, credit card requirement)

---

## Technical Inventory

### Code Written (in repository)
| Package | Lines | Files | Purpose |
|---|---|---|---|
| `kreuzwort/` | 2,014 | 12 | Crossword puzzle solver |
| `agency/` | 648 | 4 | Multi-agent orchestrator |
| `notebooks/` | 139 | 1 | Portfolio analysis |
| **Total** | **2,801** | **17** | |

### Code Written (not in repository)
| Location | Purpose |
|---|---|
| SAP BTP Eclipse | ABAP Cloud class with SELECT + JSON export |
| Google Colab | SAP API Hub integration + OR-Tools optimization (~300 lines) |
| Google Colab | Portfolio analysis with yfinance (~200 lines) |

### Technologies Used
| Category | Technologies |
|---|---|
| Languages | Python, ABAP Cloud |
| AI/LLM | Claude Sonnet (Roche Gateway), Groq (Llama) |
| ML | TensorFlow/Keras (CNN), Tesseract (OCR) |
| SAP | BTP Trial, ABAP Cloud, ADT, CDS Views, OData, API Hub Sandbox |
| Optimization | Google OR-Tools (VRP), 2-opt, Nearest Neighbor, Brute Force |
| Data | yfinance, SQLite, JSON, OData |
| Infrastructure | WSL, Docker, Playwright, Eclipse IDE |
| Platforms | Gitpod/ONA, Google Colab, SAP BTP |

### APIs Integrated
| API | Source | Method |
|---|---|---|
| Roche AI Gateway (Claude) | eu.build-cli.roche.com | Cognito OAuth + REST |
| Groq | api.groq.com | API Key + REST |
| Yahoo Finance | yfinance library | Python SDK |
| SAP Sales Order | sandbox.api.sap.com | OData + API Key |
| SAP Product Master | sandbox.api.sap.com | OData + API Key |
| SAP Business Partner | sandbox.api.sap.com | OData + API Key |

---

## Timeline

| Date | Milestone |
|---|---|
| May 6 | First commit. Multi-agent Hello World. Kreuzwort module created. |
| May 7 | Crossword solver operational. Lexikon database built. OCR pipeline complete. |
| May 8 | Agency package complete. Claude integration fixed. Iterative rounds + HTML export added. |
| May 10 | Portfolio analysis: 17 positions analyzed, performance vs. DAX calculated, JSON exported. |
| May 11 | SAP BTP Trial created. Eclipse + ADT installed. First ABAP Cloud program executed. |
| May 12 | SAP API Hub integrated. OR-Tools logistics optimization: 58% cost reduction achieved. ABAP JSON export working. |
