"""
Agency Runner — Haupteinstiegspunkt.

Verwendung:
    python -m agency "Erstelle einen Business Plan für AI-Beratung"
    python -m agency --rounds 3 "Erstelle einen Business Plan für AI-Beratung"
    python -m agency  (interaktiver Modus)
"""

import sys
import json
import os
from agency.orchestrator import plan, run_agent, consolidate


def _save_html(md_content: str, title: str, output_path: str):
    """Konvertiert Markdown zu HTML mit einfachem CSS."""
    import re

    html = md_content
    # Headers
    html = re.sub(r'^#### (.+)$', r'<h4>\1</h4>', html, flags=re.MULTILINE)
    html = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
    html = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
    html = re.sub(r'^# (.+)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)
    # Bold & Italic
    html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
    html = re.sub(r'\*(.+?)\*', r'<em>\1</em>', html)
    # Horizontal rules
    html = re.sub(r'^---+$', '<hr>', html, flags=re.MULTILINE)
    # Tables
    lines = html.split('\n')
    in_table = False
    result = []
    for line in lines:
        stripped = line.strip()
        if '|' in stripped and stripped.startswith('|'):
            cells = [c.strip() for c in stripped.split('|')[1:-1]]
            if all(re.match(r'^[-:]+$', c) for c in cells):
                continue  # separator row
            if not in_table:
                result.append('<table>')
                tag = 'th'
                in_table = True
            else:
                tag = 'td'
            row = ''.join(f'<{tag}>{c}</{tag}>' for c in cells)
            result.append(f'<tr>{row}</tr>')
        else:
            if in_table:
                result.append('</table>')
                in_table = False
            result.append(line)
    if in_table:
        result.append('</table>')
    html = '\n'.join(result)
    # Lists
    html = re.sub(r'^- (.+)$', r'<li>\1</li>', html, flags=re.MULTILINE)
    html = re.sub(r'(<li>.*</li>\n?)+', lambda m: f'<ul>{m.group(0)}</ul>', html)
    # Paragraphs — wrap remaining text lines
    html = re.sub(r'^([^<\n].+)$', r'<p>\1</p>', html, flags=re.MULTILINE)

    page = f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<title>{title}</title>
<style>
  body {{ font-family: 'Segoe UI', sans-serif; max-width: 900px; margin: 40px auto; padding: 0 20px; line-height: 1.6; color: #333; }}
  h1 {{ color: #1a5276; border-bottom: 2px solid #1a5276; padding-bottom: 10px; }}
  h2 {{ color: #2c3e50; margin-top: 30px; }}
  h3 {{ color: #34495e; }}
  table {{ border-collapse: collapse; width: 100%; margin: 15px 0; }}
  th, td {{ border: 1px solid #ddd; padding: 8px 12px; text-align: left; }}
  th {{ background: #1a5276; color: white; }}
  tr:nth-child(even) {{ background: #f9f9f9; }}
  hr {{ border: none; border-top: 1px solid #ccc; margin: 30px 0; }}
  ul {{ padding-left: 20px; }}
  strong {{ color: #1a5276; }}
</style>
</head>
<body>
{html}
</body>
</html>"""

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(page)


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


def _run_single_round(prompt: str, context: str = "") -> tuple[dict, dict, str]:
    """Führt eine einzelne Runde aus: Planung → Agenten → Konsolidierung.

    Returns:
        (plan_data, results, consolidated_text)
    """
    # Planung
    print("\n[Orchestrator] Analysiere Auftrag...")
    plan_data = plan(prompt, context)

    if 'error' in plan_data:
        print(f"\nFEHLER: {plan_data['error']}")
        if 'raw' in plan_data:
            print(f"\nRohe Antwort:\n{plan_data['raw']}")
        return plan_data, {}, ""

    _print_plan(plan_data)

    # Rückfragen nur in der ersten Runde (kein previous_result im context)
    if "ERGEBNIS DER VORHERIGEN RUNDE" not in context:
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

    # Agenten ausführen
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

            agent_context = {}
            for dep_id in role.get('depends_on', []):
                if dep_id in results:
                    agent_context[dep_id] = results[dep_id]

            result = run_agent(role, agent_context if agent_context else None)
            results[role['id']] = result

            preview = result[:150].replace('\n', ' ')
            print(f"  [{role['id']}] Fertig ({len(result)} Zeichen)")
            print(f"         {preview}...")

    # Konsolidierung
    print(f"\n{'='*60}")
    print("[Orchestrator] Konsolidiere Ergebnisse...")
    print(f"{'='*60}\n")

    final = consolidate(plan_data, results)
    print(final)

    return plan_data, results, final


def _save_round(plan_data: dict, results: dict, final: str,
                round_num: int, total_rounds: int, open_browser: bool = True):
    """Speichert Ergebnis einer Runde als .md und .html."""
    title = plan_data.get('project_title', 'Ergebnis')
    roles = plan_data.get('roles', [])

    # Dateinamen
    if total_rounds == 1:
        suffix = ""
    else:
        labels = {1: "initial", total_rounds: "final"}
        label = labels.get(round_num, f"draft{round_num - 1}")
        suffix = f"_{label}"

    output_md = f"agency_result{suffix}.md"
    output_html = f"agency_result{suffix}.html"

    # Markdown zusammenbauen
    round_info = ""
    if total_rounds > 1:
        round_info = f"\n*Runde {round_num}/{total_rounds}*\n\n"

    md_content = f"# {title}\n\n{round_info}"
    md_content += final
    md_content += "\n\n---\n\n## Einzelergebnisse der Experten\n\n"
    for role in roles:
        if role['id'] in results:
            md_content += f"### {role['title']}\n\n"
            md_content += results[role['id']]
            md_content += "\n\n"

    with open(output_md, 'w', encoding='utf-8') as f:
        f.write(md_content)

    _save_html(md_content, f"{title} (Runde {round_num})" if total_rounds > 1 else title, output_html)

    print(f"\n[Gespeichert: {output_md}]")
    print(f"[Gespeichert: {output_html}]")

    # Auf WSL automatisch im Browser öffnen
    if open_browser:
        import shutil
        if shutil.which("explorer.exe"):
            import subprocess
            try:
                abs_path = os.path.abspath(output_html)
                win_path = subprocess.run(
                    ["wslpath", "-w", abs_path],
                    capture_output=True, text=True
                ).stdout.strip()
                if win_path:
                    subprocess.Popen(["explorer.exe", win_path])
            except Exception:
                pass

    return md_content


def run(prompt: str, context: str = "", rounds: int = 1):
    """Führt den Agency-Workflow aus, optional mit mehreren Runden.

    Args:
        prompt: Der Auftrag
        context: Zusätzlicher Kontext
        rounds: Anzahl Runden (1=einmalig, 2+=iterativ mit Feedback)
    """
    round_context = context

    for round_num in range(1, rounds + 1):
        is_last = (round_num == rounds)

        if rounds > 1:
            labels = {1: "Initial", rounds: "Final"}
            label = labels.get(round_num, f"Draft {round_num - 1}")
            print(f"\n{'#'*60}")
            print(f"  RUNDE {round_num}/{rounds}: {label}")
            print(f"{'#'*60}")

        plan_data, results, final = _run_single_round(prompt, round_context)

        if 'error' in plan_data or not final:
            return

        # Speichern (Browser nur bei letzter Runde öffnen)
        md_content = _save_round(plan_data, results, final,
                                 round_num, rounds, open_browser=is_last)

        # Nach jeder Runde außer der letzten: Feedback einholen
        if not is_last and sys.stdin.isatty():
            print(f"\n{'='*60}")
            print(f"REVIEW — Runde {round_num}/{rounds} abgeschlossen")
            print(f"{'='*60}")
            print("Was soll in der nächsten Runde verbessert werden?")
            print("(Enter = ohne Feedback weiter)")
            try:
                feedback = input("> ").strip()
            except EOFError:
                feedback = ""

            # Kontext für nächste Runde aufbauen
            round_context = context
            round_context += f"\n\n--- ERGEBNIS DER VORHERIGEN RUNDE (Runde {round_num}) ---\n"
            round_context += final[:8000]  # Gekürzt um Token-Limit nicht zu sprengen
            if feedback:
                round_context += f"\n\n--- FEEDBACK DES KUNDEN ---\n{feedback}"
            round_context += "\n\nBitte überarbeite und verbessere das Ergebnis basierend auf dem Feedback."


def main():
    args = sys.argv[1:]
    rounds = 1

    # --rounds N parsen
    if "--rounds" in args:
        idx = args.index("--rounds")
        try:
            rounds = int(args[idx + 1])
            args = args[:idx] + args[idx + 2:]
        except (IndexError, ValueError):
            print("Fehler: --rounds braucht eine Zahl (z.B. --rounds 3)")
            return

    if args:
        prompt = " ".join(args)
    else:
        print("AGENCY — Multi-Agent Orchestrator")
        print("="*40)
        if rounds > 1:
            print(f"[{rounds} Runden: Initial → Draft → Final]")
        print("Beschreibe deinen Auftrag:")
        prompt = input("> ").strip()
        if not prompt:
            print("Kein Auftrag. Abbruch.")
            return

    run(prompt, rounds=rounds)


if __name__ == '__main__':
    main()
