"""
Agency Runner — Haupteinstiegspunkt.

Verwendung:
    python -m agency "Erstelle einen Business Plan für AI-Beratung"
    python -m agency  (interaktiver Modus)
"""

import sys
import json
from agency.orchestrator import plan, run_agent, consolidate


def _print_plan(plan_data: dict):
    """Zeigt den Projektplan übersichtlich an."""
    print(f"\n{'='*60}")
    print(f"PROJEKT: {plan_data.get('project_title', '?')}")
    print(f"{'='*60}")
    print(f"\n{plan_data.get('summary', '')}\n")

    questions = plan_data.get('clarifying_questions', [])
    if questions:
        print("RÜCKFRAGEN AN DEN KUNDEN:")
        for i, q in enumerate(questions, 1):
            print(f"  {i}. {q}")
        print()

    print("TEAM:")
    for role in plan_data.get('roles', []):
        deps = f" (braucht: {', '.join(role['depends_on'])})" if role.get('depends_on') else ""
        print(f"  [{role['id']}] {role['title']}{deps}")
        print(f"         {role['task'][:80]}...")
    print()

    print("PHASEN:")
    for i, phase in enumerate(plan_data.get('phases', []), 1):
        roles = ", ".join(phase.get('roles_involved', []))
        print(f"  {i}. {phase['name']}")
        print(f"     Team: {roles}")
        print(f"     Deliverable: {phase.get('deliverable', '?')}")
    print()


def _resolve_dependencies(roles: list) -> list[list[dict]]:
    """
    Sortiert Rollen in Ausführungsreihenfolge (Batches).
    Rollen ohne Abhängigkeiten kommen zuerst.
    """
    done = set()
    batches = []
    remaining = list(roles)

    while remaining:
        batch = []
        for role in remaining:
            deps = set(role.get('depends_on', []))
            if deps.issubset(done):
                batch.append(role)

        if not batch:
            # Zirkuläre Abhängigkeit — alle verbleibenden in einen Batch
            batch = remaining
            remaining = []
        else:
            remaining = [r for r in remaining if r not in batch]

        batches.append(batch)
        done.update(r['id'] for r in batch)

    return batches


def run(prompt: str, context: str = ""):
    """Führt den kompletten Agency-Workflow aus."""

    # Phase 1: Planung
    print("\n[Orchestrator] Analysiere Auftrag...")
    plan_data = plan(prompt, context)

    if 'error' in plan_data:
        print(f"\nFEHLER: {plan_data['error']}")
        if 'raw' in plan_data:
            print(f"\nRohe Antwort:\n{plan_data['raw']}")
        return

    _print_plan(plan_data)

    # Rückfragen?
    questions = plan_data.get('clarifying_questions', [])
    if questions and sys.stdin.isatty():
        print("Möchtest du die Rückfragen beantworten? (Enter = überspringen)")
        try:
            answers = input("> ").strip()
            if answers:
                context += f"\nAntworten auf Rückfragen: {answers}"
                print("\n[Orchestrator] Überarbeite Plan mit neuen Infos...")
                plan_data = plan(prompt, context)
                _print_plan(plan_data)
        except EOFError:
            pass

    # Phase 2: Agenten ausführen
    print(f"{'='*60}")
    print("AUSFÜHRUNG")
    print(f"{'='*60}")

    roles = plan_data.get('roles', [])
    batches = _resolve_dependencies(roles)
    results = {}

    for batch_num, batch in enumerate(batches, 1):
        batch_names = ", ".join(r['title'] for r in batch)
        print(f"\n[Batch {batch_num}] {batch_names}")

        for role in batch:
            print(f"\n  [{role['id']}] {role['title']} arbeitet...")

            # Kontext von Abhängigkeiten sammeln
            agent_context = {}
            for dep_id in role.get('depends_on', []):
                if dep_id in results:
                    agent_context[dep_id] = results[dep_id]

            result = run_agent(role, agent_context if agent_context else None)
            results[role['id']] = result

            # Kurze Vorschau
            preview = result[:150].replace('\n', ' ')
            print(f"  [{role['id']}] Fertig ({len(result)} Zeichen)")
            print(f"         {preview}...")

    # Phase 3: Konsolidierung
    print(f"\n{'='*60}")
    print("[Orchestrator] Konsolidiere Ergebnisse...")
    print(f"{'='*60}\n")

    final = consolidate(plan_data, results)
    print(final)

    # Ergebnis speichern
    output_file = "agency_result.md"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(f"# {plan_data.get('project_title', 'Ergebnis')}\n\n")
        f.write(final)
        f.write("\n\n---\n\n## Einzelergebnisse der Experten\n\n")
        for role in roles:
            if role['id'] in results:
                f.write(f"### {role['title']}\n\n")
                f.write(results[role['id']])
                f.write("\n\n")

    print(f"\n[Gespeichert: {output_file}]")


def main():
    if len(sys.argv) > 1:
        prompt = " ".join(sys.argv[1:])
    else:
        print("AGENCY — Multi-Agent Orchestrator")
        print("="*40)
        print("Beschreibe deinen Auftrag:")
        prompt = input("> ").strip()
        if not prompt:
            print("Kein Auftrag. Abbruch.")
            return

    run(prompt)


if __name__ == '__main__':
    main()
