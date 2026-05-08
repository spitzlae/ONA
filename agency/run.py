"""
Agency Runner — Haupteinstiegspunkt.

Verwendung:
    python -m agency "Erstelle einen Business Plan für AI-Beratung"
    python -m agency  (interaktiver Modus)
"""

import sys
import json
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

    # Ergebnis speichern — Markdown
    output_md = "agency_result.md"
    md_content = f"# {plan_data.get('project_title', 'Ergebnis')}\n\n"
    md_content += final
    md_content += "\n\n---\n\n## Einzelergebnisse der Experten\n\n"
    for role in roles:
        if role['id'] in results:
            md_content += f"### {role['title']}\n\n"
            md_content += results[role['id']]
            md_content += "\n\n"

    with open(output_md, 'w', encoding='utf-8') as f:
        f.write(md_content)

    # Ergebnis speichern — HTML
    output_html = "agency_result.html"
    _save_html(md_content, plan_data.get('project_title', 'Ergebnis'), output_html)

    print(f"\n[Gespeichert: {output_md}]")
    print(f"[Gespeichert: {output_html}]")

    # Auf WSL automatisch im Browser öffnen
    import shutil
    if shutil.which("explorer.exe"):
        import subprocess
        try:
            import os
            abs_path = os.path.abspath(output_html)
            win_path = subprocess.run(
                ["wslpath", "-w", abs_path],
                capture_output=True, text=True
            ).stdout.strip()
            if win_path:
                subprocess.Popen(["explorer.exe", win_path])
        except Exception:
            pass


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
