"""
Orchestrator — analysiert einen Prompt und stellt ein Team zusammen.

Der Orchestrator:
1. Analysiert die Aufgabe
2. Stellt Rückfragen (optional)
3. Ermittelt benötigte Rollen dynamisch
4. Erstellt einen Projektplan mit Phasen
5. Weist Aufgaben an Agenten zu
6. Konsolidiert die Ergebnisse
"""

import json
from agency.llm import ask


ORCHESTRATOR_SYSTEM = """Du bist ein erfahrener Projektleiter.
Deine Aufgabe: Analysiere den Auftrag des Kunden und erstelle einen Projektplan.

Du musst folgendes als JSON zurückgeben (NUR JSON, kein anderer Text):
{
    "project_title": "Kurzer Projekttitel",
    "summary": "Was soll erreicht werden (2-3 Sätze)",
    "clarifying_questions": ["Frage 1", "Frage 2"],
    "roles": [
        {
            "id": "researcher",
            "title": "Marktforscher",
            "why": "Warum diese Rolle gebraucht wird",
            "task": "Konkrete Aufgabe für diese Rolle",
            "depends_on": []
        }
    ],
    "phases": [
        {
            "name": "Phase 1: Recherche",
            "roles_involved": ["researcher"],
            "deliverable": "Was am Ende dieser Phase vorliegt"
        }
    ]
}

Regeln:
- Maximal 5 Rollen
- Maximal 4 Phasen
- Jede Rolle hat eine klar abgegrenzte Aufgabe
- depends_on enthält IDs von Rollen deren Ergebnis benötigt wird
- Rollen können parallel arbeiten wenn keine Abhängigkeit besteht
- clarifying_questions: Fragen die du dem Kunden stellen würdest (max 3)
"""


def plan(user_prompt: str, context: str = "") -> dict:
    """
    Analysiert den User-Prompt und erstellt einen Projektplan.

    Args:
        user_prompt: Der Auftrag des Kunden
        context: Zusätzlicher Kontext (z.B. Antworten auf Rückfragen)

    Returns:
        Projektplan als Dict
    """
    full_prompt = user_prompt
    if context:
        full_prompt += f"\n\nZusätzlicher Kontext vom Kunden:\n{context}"

    response = ask(
        system_prompt=ORCHESTRATOR_SYSTEM,
        user_prompt=full_prompt,
        temperature=0.3,  # Wenig Kreativität für Planung
        max_tokens=3000,
    )

    # JSON aus der Antwort extrahieren
    try:
        # Versuche direkt zu parsen
        return json.loads(response)
    except json.JSONDecodeError:
        # Suche nach JSON-Block in der Antwort
        start = response.find('{')
        end = response.rfind('}') + 1
        if start >= 0 and end > start:
            try:
                return json.loads(response[start:end])
            except json.JSONDecodeError:
                pass

    return {"error": "Konnte Plan nicht parsen", "raw": response}


def run_agent(role: dict, context: dict = None) -> str:
    """
    Führt einen einzelnen Agenten aus.

    Args:
        role: Rollen-Definition aus dem Plan
        context: Ergebnisse von Agenten auf die dieser abhängt

    Returns:
        Ergebnis des Agenten als String
    """
    system = (
        f"Du bist ein {role['title']}.\n"
        f"Deine Aufgabe: {role['task']}\n\n"
        "Liefere ein strukturiertes, detailliertes Ergebnis.\n"
        "Nutze Fakten und Zahlen wo möglich.\n"
        "Wenn du etwas nicht weißt, sage es ehrlich."
    )

    user = f"Aufgabe: {role['task']}"

    if context:
        user += "\n\nErgebnisse von anderen Teammitgliedern:"
        for role_id, result in context.items():
            user += f"\n\n--- {role_id} ---\n{result}"

    return ask(
        system_prompt=system,
        user_prompt=user,
        temperature=0.5,
        max_tokens=3000,
    )


def consolidate(plan_data: dict, results: dict) -> str:
    """
    Konsolidiert alle Agenten-Ergebnisse zu einem Gesamtergebnis.

    Args:
        plan_data: Der ursprüngliche Projektplan
        results: {role_id: ergebnis_text}

    Returns:
        Konsolidierter Bericht
    """
    system = """Du bist ein erfahrener Projektleiter.
Du hast ein Team von Experten beauftragt. Jetzt konsolidierst du deren Ergebnisse
zu einem einheitlichen, professionellen Dokument.

Regeln:
- Fasse die Ergebnisse zusammen, wiederhole nicht alles
- Hebe Widersprüche zwischen den Experten hervor
- Gib eine klare Empfehlung
- Strukturiere das Dokument mit Überschriften
- Schreibe für einen Entscheider, nicht für Techniker
"""

    user = f"Projekttitel: {plan_data.get('project_title', 'Unbekannt')}\n"
    user += f"Zusammenfassung: {plan_data.get('summary', '')}\n\n"
    user += "Ergebnisse der Experten:\n"

    for role in plan_data.get('roles', []):
        role_id = role['id']
        if role_id in results:
            user += f"\n{'='*60}\n"
            user += f"{role['title']} ({role_id})\n"
            user += f"{'='*60}\n"
            user += results[role_id]
            user += "\n"

    return ask(
        system_prompt=system,
        user_prompt=user,
        temperature=0.3,
        max_tokens=4000,
    )
