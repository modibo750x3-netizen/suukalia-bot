"""
Suukalia Agent Team — Orchestrator.

Routes commands to the right specialist agent:
  ContentAgent  → /ig /t /fanvue /th /ppv
  StrategyAgent → /ign /reel1 /reel2
  PromptAgent   → /prompt
  Orchestrator  → /day  (tool use: ContentAgent + StrategyAgent → combined plan)
"""

import logging

import anthropic

from . import content_agent, growth_agent, prompt_agent, strategy_agent
from prompts import PROMPTS

logger = logging.getLogger(__name__)

# ── Routing table ──────────────────────────────────────────────────────────────
_ROUTING: dict[str, str] = {
    "ig":     "content",
    "t":      "content",
    "fanvue": "content",
    "th":     "content",
    "ppv":    "content",
    "ign":    "strategy",
    "reel1":  "strategy",
    "reel2":  "strategy",
    "prompt": "prompt",
    "day9":   "prompt",
    "day":    "orchestrator",
    "igrow":  "growth",
}

# ── Orchestrator (for /day) ────────────────────────────────────────────────────
_ORCHESTRATOR_SYSTEM = """Tu es l'Orchestrateur de la Team Suukalia.

Tu coordonnes deux agents spécialisés pour créer le meilleur plan quotidien possible:
• ContentAgent  — contenu social (IG, Twitter, Threads, Fanvue, PPV)
• StrategyAgent — planning, timing, scripts

MISSION: Produire un plan quotidien complet et actionnable pour Suukalia.

PROCESSUS:
1. Appelle ContentAgent pour lister les contenus à créer aujourd'hui
2. Appelle StrategyAgent pour structurer le timing et les actions
3. Synthétise en un plan cohérent format ⏰ [heure] | [plateforme] | [action]

OUTPUT FINAL: max 15 lignes, sous 150 mots, prêt à copier-coller."""

_TOOLS = [
    {
        "name": "call_content_agent",
        "description": (
            "Appelle l'Agent Contenu — spécialiste captions IG, tweets, "
            "posts Threads, idées PPV Fanvue."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "La tâche précise à confier à l'Agent Contenu.",
                }
            },
            "required": ["task"],
        },
    },
    {
        "name": "call_strategy_agent",
        "description": (
            "Appelle l'Agent Stratégie — spécialiste planning horaire, "
            "scripts reels, timing optimal par plateforme."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "La tâche précise à confier à l'Agent Stratégie.",
                }
            },
            "required": ["task"],
        },
    },
]


async def _orchestrate_day(client: anthropic.AsyncAnthropic) -> str:
    """Coordinate ContentAgent + StrategyAgent via tool use to produce a daily plan."""
    messages: list[dict] = [
        {
            "role": "user",
            "content": (
                "Crée un plan quotidien complet pour Suukalia. "
                "Utilise tes agents pour couvrir: stories matin, shooting après-midi, "
                "publication soir, engagement nuit. "
                "Plateformes: Instagram, Twitter, Threads, Fanvue."
            ),
        }
    ]

    for _ in range(8):  # safety limit: max 8 iterations
        resp = await client.messages.create(
            model="claude-opus-4-6",
            max_tokens=3000,
            thinking={"type": "adaptive"},
            system=_ORCHESTRATOR_SYSTEM,
            tools=_TOOLS,
            messages=messages,
        )

        if resp.stop_reason == "end_turn":
            return "\n".join(b.text for b in resp.content if b.type == "text").strip()

        if resp.stop_reason != "tool_use":
            break

        # Execute tool calls
        messages.append({"role": "assistant", "content": resp.content})
        tool_results = []
        for block in resp.content:
            if block.type != "tool_use":
                continue
            task = block.input.get("task", "")
            if block.name == "call_content_agent":
                logger.info("[Orchestrator] → ContentAgent: %s", task[:60])
                result = await content_agent.run(task, 700, client)
            elif block.name == "call_strategy_agent":
                logger.info("[Orchestrator] → StrategyAgent: %s", task[:60])
                result = await strategy_agent.run(task, 700, client)
            else:
                result = f"Agent inconnu: {block.name}"
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": result,
            })
        messages.append({"role": "user", "content": tool_results})

    return "❌ L'orchestrateur n'a pas pu compléter le plan. Réessaie."


# ── Public entry point ─────────────────────────────────────────────────────────
async def run(command_key: str, client: anthropic.AsyncAnthropic) -> str:
    """Route a command to the appropriate specialist agent and return the result."""
    agent_name = _ROUTING.get(command_key)
    if agent_name is None:
        raise ValueError(f"Unknown command key: {command_key!r}")

    if agent_name == "orchestrator":
        logger.info("[Team] Orchestrator → /day")
        return await _orchestrate_day(client)

    prompt, max_tokens = PROMPTS[command_key]
    logger.info("[Team] %sAgent → /%s", agent_name.capitalize(), command_key)

    if agent_name == "content":
        return await content_agent.run(prompt, max_tokens, client)
    if agent_name == "strategy":
        return await strategy_agent.run(prompt, max_tokens, client)
    if agent_name == "prompt":
        return await prompt_agent.run(prompt, max_tokens, client)
    if agent_name == "growth":
        return await growth_agent.run(prompt, max_tokens, client)

    raise ValueError(f"Unhandled agent: {agent_name!r}")
