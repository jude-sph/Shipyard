# Engineering Context & Domain Knowledge

> **For future Claude instances:** This document captures tribal knowledge from building the reqdecomp and MBSE tools with Jude and his engineering team at Davie shipyard. This context is not in the code -- it's from conversations, engineer emails, and iterative feedback.

## Who Is This For

Jude manages a team of systems engineers at Davie (Chantier Davie Canada Inc.), a shipbuilder in Lévis, Québec. They're building Canadian Coast Guard (CCG) Polar Icebreakers. The engineering tools (reqdecomp, MBSE) are internal tools Jude commissions for his team to accelerate their MBSE and requirements work.

## The Engineer's Mindset

The primary engineer user gave critical insight that shaped the entire MBSE tool. Direct quotes:

### "We Are NOT Designing a Ship"

> "The important thing here is that I am not designing a ship, but rather defining to the customer how it is used to achieve their missions. The example I used for the presentation is the coast guard's Search & Rescue (SAR) mandated mission."

This is the most important principle for anyone working on these tools. The Arcadia Operational Analysis stage models the **operational reality** (missions, actors, interactions) BEFORE touching the vessel's physical design. The LLM prompts must understand this distinction -- it's modeling mission capability, not hardware specifications.

### Small Batch Workflow

> "There will never be a case of +100k requirement inputs. Typically the worst case is perhaps 5k requirements."
>
> "Most of these requirements would not require MBSE output, but be better suited to the reqdecomp app."
>
> "There is no need to one-shot the entire requirements series. I'm envisioning a workflow of uploading 1-5 requirements at a time."
>
> "I'm thinking the best approach is to enable the user to upload source requirement file on each shot. This allows me to remotely organize batches by creating a requirement set grouped by subject, section or system."

The tools are designed for **small batch processing** (1-10 requirements at a time), not bulk processing. The engineer groups requirements offline by capability/system, then processes each group. The MBSE app's project workspace and batch history features were built specifically for this workflow.

### Dependencies Are Huge

> "All MBSE elements have dependencies and keeping track of them is huge."

Traceability is the core value proposition. The coverage indicator, link tracking, and the chat agent's coverage analysis tools were all driven by this feedback.

### The Real Workflow

> "For example, let's say I get a list of 10k requirements to work on. Offline I would organize them by grouping them into subjects, sections or systems. I would then create a source input file with perhaps 1-10 requirements focusing on a particular vessel capability or mission system. I would then use the reqdecomp to break out the requirements. I'd take this list of decomposed mission specific requirements and create an MBSE requirements source file for the MBSE app."

So the pipeline is: raw requirements → manual grouping → reqdecomp → MBSE → Capella/Rhapsody.

## The Arcadia Process (What the Engineer Actually Does)

The engineer gave a detailed presentation (in `/Users/jude/Documents/projects/MBSE/CDCI Internal Presentation -MBSE Summary Guide.pdf`) showing how they took a real DIG requirement (DIG-5967, SAR Keep Station) through the full Arcadia process.

### The SAR Example

DIG-5967: "The PIB must include the capability to Keep Station within a 10-meter radius from a fixed geographical position for a short duration in WMO Sea State 6, while creating a lee of approximately 20 degrees heading off the wind for the purpose of search and rescue (SAR), specifically recovery of a person in the water, or for the launch and recovery of the fast rescue craft (FRC) from the davit."

This single compound requirement was decomposed into 7 sub-requirements (REQ-SAR-001 through REQ-SAR-007), each addressing a distinct engineering concern:
- GMDSS monitoring (communications)
- On-scene coordination
- Emergency towing
- Station keeping (dynamic positioning)
- Lee creation (hull hydrodynamics)
- Environmental constraints (Sea State 6)
- FRC launch/recovery (deck operations)

The key point: **one sentence from the client dictates three completely different engineering disciplines**. MBSE allows splitting these up and assigning them to the right teams while keeping them linked.

### Arcadia Diagram Types (What Each "Blank" Is)

The engineer uses specific diagram types in Capella. These are the outputs the MBSE tool generates instructions for:

- **OEBD** (Operational Entity Breakdown) -- shows WHO exists in the world (PIB Icebreaker, JRCC, MCTS, etc.)
- **OCB** (Operational Capability Blank) -- shows WHAT missions entities participate in
- **OES** (Operational Entity Scenario) -- shows the TIMELINE of a mission (sequence diagram)
- **OAB** (Operational Architecture Blank) -- shows the NETWORK MAP of a mission
- **SAB** (System Architecture Blank) -- treats the vessel as a "black box" and maps functions
- **MCB** (Mission Capability Blank) -- system-level capabilities
- **SFBD** (System Functional Breakdown) -- function hierarchy
- **LAB** (Logical Architecture Blank) -- opens the black box into subsystems
- **LFBD** (Logical Functional Breakdown) -- subsystem function hierarchy
- **PAB** (Physical Architecture Blank) -- deploys logic onto physical hardware
- **PFBD** (Physical Functional Architecture Blank) -- physical function hierarchy

### The 5-Stage Arcadia Flow

```
1. Operational (Mission)      → "Here is the environment and here is the target"
2. System (The Black Box)     → "What the vessel must do, from the outside"
3. Logical (The Subsystems)   → "How we decompose the vessel internally"
4. Physical (The Hardware)    → "What actual hardware implements the logic"
5. EPBS (The Products)        → "What we buy, build, or configure"
```

The engineer's slide said it best: "We modeled the problem before we ever touched the solution."

## Technical Decisions & Why

### Why Local LLM Support Exists But Isn't Primary

The engineer wanted local LLM support (≤3B parameters). Jude's direction: "The engineers are really interested in local models so we should definitely include them as a possibility at least. OpenRouter should be available as I expect it to be a lot worse local."

The resolution: local is available as an option, but prompts are designed for quality (not constrained to fit small context windows). If a local model can't handle a prompt, the app surfaces a message suggesting OpenRouter.

### Why DeepSeek V3 Keeps Failing on Instructions

During testing, the instruct stage repeatedly failed with DeepSeek V3 (the engineer's chosen cheap model). The JSON responses were getting truncated at 34K+ characters. Fix: split instruction generation per-layer instead of all-at-once. Also added JSON sanitization (strip control characters, fix trailing commas) to handle cheaper model output quality.

### Why the Parser Has So Many Column Aliases

The MBSE parser detects columns like `node_id`, `technical_requirement`, `dig_id` because that's what reqdecomp outputs. But it also handles `DNG`, `DIG Text` because that's the raw GTR-SDS.xlsx format the engineers might upload directly. And it handles plain `id`, `text` for simple manual files.

### Why Coverage Tracking Matters

The engineer explicitly asked: "Please find why we don't have 100% link coverage." Coverage (which requirements have traceability links to model elements) is a critical metric. The chat agent now has `get_uncovered_requirements` and `get_coverage_summary` tools specifically because the engineer wanted to investigate gaps.

### Why the Chat Agent Gets Full Model Context

Initially the agent only got a summary (layer names, element counts). The engineer asked about uncovered requirements and the agent couldn't answer because it couldn't see the actual data. Now `_build_model_context()` passes all requirements, all elements (IDs + names), all links, and an explicit uncovered requirements list to the agent.

## UI/UX Feedback That Shaped the App

### Progress View
The engineer saw the first progress view (plain text with stage names) and said "it does not fit with the theme of the webapp and it doesn't look like anything is happening." This led to the animated pipeline tracker with pulsing icons, elapsed timers, and stage-by-stage progress bars.

### Chat Agent
Initially had a collapse/expand toggle. The engineer found it "counter intuitive" -- couldn't tell how to access the input. Now always-visible with a welcome state showing example prompts. Also: markdown rendering for agent responses, resizable panel, persistent chat history.

### Provider Toggle
Originally Anthropic / OpenRouter / Local. The engineer (Jude) pointed out this was redundant: "the Anthropic vs OpenRouter question is solved by our choice of API model in Settings." Simplified to API / Local.

### Instructions Tab
The engineer pasted a wall of instruction text showing it was hard to read. Redesigned into grouped step cards per layer with copy buttons.

### Clarification Modal
The engineer uploaded 19 requirements and the clarification modal was too long to see. Made scrollable with 85vh max height.

## Reference Documents

These documents were provided by the engineer and are in the MBSE project:

### In `/Users/jude/Documents/projects/MBSE/`
- `AligningShipDesignandMBSEMethodologiesJan2024.pdf` -- Academic paper on MBSE in ship design (Marion & Herber, Colorado State University). Good background on why MBSE matters for shipbuilding.
- `CDCI Internal Presentation -MBSE Summary Guide.pdf` -- The engineer's presentation showing the full SAR example through Arcadia. Best reference for understanding the real workflow.

### In `/Users/jude/Documents/projects/MBSE/new-info/`
- `Arcadia Reference - Data Model_copy.pdf` -- Thales 2023 reference defining all Arcadia element types and relationships. The source of truth for element definitions in prompts.
- `Capella_User_Manual.pdf` -- 297-page Capella tool manual. Section 14 (Properties) has exact element property pages. Critical for accurate recreation instructions.
- `Microsoft Word - Arcadia User Guide.docx` -- Arcadia methodology overview.

## The Davie Context

- **Company:** Chantier Davie Canada Inc. (Davie), Lévis, Québec
- **Program:** Canadian Coast Guard Polar Icebreaker (PIB)
- **Client:** Canadian Coast Guard (CCG), with oversight from Department of Fisheries and Oceans (DFO)
- **Requirements source:** GTR-SDS.xlsx contains Design Instructions & Guidelines (DIGs) from the CCG
- **Mission examples:** Search & Rescue (SAR), Ice Escort, Harbour Breakout, Arctic Resupply, Scientific Research, Border Patrol
- **Engineering approach:** Arcadia/Capella for MBSE (some Rhapsody/SysML use planned for future)
- **Key stakeholders mentioned in models:** PIB Icebreaker, JRCC (Joint Rescue Coordination Centre), MCTS (Marine Communications and Traffic Services), Transport Canada, DFO, RCMP/CBSA

## Future Directions Discussed

1. **Reqdecomp + MBSE combination** -- Engineer wants seamless flow from decomposition to modeling without file downloads. See `docs/integration-guide.md` for detailed technical plan.

2. **Web hosting** -- Jude has a personal Flask website on a VPS at `/Users/jude/Documents/hawraniweb-f/hawraniweb-flask` with webhook auto-deploy. Goal: host the combined tool there with authentication.

3. **Rhapsody/SysML expansion** -- Engineer said: "That's a whole different kettle of fish. That will be a future update." The current Rhapsody option has basic models but hasn't been expanded to the same depth as Capella.

4. **Batching for large documents** -- For 100+ requirements, discussed thematic batching (group by DIG/chapter/system), two-pass approach (skeleton first, detail second), and incremental generation. Not implemented yet -- current small-batch workflow serves the engineer's needs.
