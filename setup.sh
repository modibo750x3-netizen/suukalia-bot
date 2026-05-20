#!/usr/bin/env bash
# Setup complet pour Suukalia OFM IA — à lancer sur ta machine locale.
# Réinstalle skills Claude Code, Higgsfield CLI, Playwright MCP.

set -e

GREEN="\033[0;32m"
YELLOW="\033[1;33m"
NC="\033[0m"

info() { echo -e "${GREEN}==>${NC} $1"; }
warn() { echo -e "${YELLOW}!!${NC} $1"; }

# ── 1. Skills Claude Code ─────────────────────────────────────────────────────
info "Installation des skills Claude Code dans ~/.claude/skills/"
mkdir -p ~/.claude/skills
cd ~/.claude/skills

clone_if_missing() {
    local repo="$1"
    local target="$2"
    if [ -d "$target" ]; then
        warn "$target existe déjà — skip"
    else
        git clone --depth 1 "$repo" "$target"
    fi
}

clone_if_missing https://github.com/nidhinjs/prompt-master.git prompt-master
clone_if_missing https://github.com/AKCodez/higgsfield-claude-skills.git higgsfield-claude-skills
clone_if_missing https://github.com/higgsfield-ai/skills.git higgsfield-official
clone_if_missing https://github.com/OSideMedia/higgsfield-ai-prompt-skill.git higgsfield-ai-prompt-skill
clone_if_missing https://github.com/moboutrig/instagram-claude-skill.git instagram-automation

# Symlink sub-skills (AKCodez + Higgsfield officiel ont chacun plusieurs skills dans des sous-dossiers)
info "Activation des sous-skills via symlinks"
for d in higgsfield-claude-skills/*/; do
    name=$(basename "$d")
    [ -f "$d/SKILL.md" ] && ln -sfn "$(pwd)/$d" "akc-$name"
done
for d in higgsfield-official/*/; do
    name=$(basename "$d")
    [ -f "$d/SKILL.md" ] && ln -sfn "$(pwd)/$d" "$name"
done

# ── 2. Higgsfield CLI ─────────────────────────────────────────────────────────
info "Installation Higgsfield CLI v0.1.1"
if command -v higgsfield >/dev/null 2>&1; then
    warn "higgsfield déjà installé — skip"
else
    curl -fsSL https://raw.githubusercontent.com/higgsfield-ai/cli/main/install.sh | sh -s -- --tag v0.1.1
fi

# ── 3. Playwright + MCP ───────────────────────────────────────────────────────
info "Installation Playwright MCP (scope user)"
if command -v claude >/dev/null 2>&1; then
    claude mcp add playwright npx @playwright/mcp@latest --scope user 2>/dev/null || \
        warn "Playwright MCP déjà configuré ou erreur — vérifie ~/.claude.json"
else
    warn "Claude Code CLI introuvable — installe-le d'abord : https://claude.ai/code"
fi

info "Installation deps système Playwright (peut demander sudo)"
npx playwright install-deps 2>&1 | tail -5 || warn "playwright install-deps a échoué — relance manuellement"

# ── 4. Actions manuelles ──────────────────────────────────────────────────────
cat <<EOF

${GREEN}✅ Setup automatique terminé.${NC}

${YELLOW}Étapes manuelles restantes :${NC}

  1. Auth Higgsfield (navigateur) :
     ${GREEN}higgsfield auth login${NC}

  2. Tokens Instagram (Meta Developer Portal) :
     • https://developers.facebook.com/ → crée une app Business
     • Connecte tes comptes IG Business (@suukalia, @suuki03)
     • Récupère un long-lived access token + business account ID
     • Copie .env.example vers .env et remplis les variables

  3. Redémarre Claude Code pour activer les nouveaux skills + MCP

EOF
