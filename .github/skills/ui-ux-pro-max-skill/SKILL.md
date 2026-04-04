```skill
---
name: ui-ux-pro-max-skill
description: "AI skill that provides design intelligence for building professional UI/UX across multiple platforms and frameworks. Use for design system generation, UI recommendations, code scaffolding and reviews."
---

This skill integrates guidance, templates, and a reasoning engine to generate design systems, landing pages, dashboards, component specs, and stack-specific implementation hints.

Purpose
-------
- Provide fast, opinionated design system recommendations tailored to product type.
- Generate implementation-friendly UI specs and example code (HTML+Tailwind, React, Vue, SwiftUI, Jetpack Compose, Flutter).
- Surface accessibility, anti-patterns and pre-delivery checks.

Key Features
------------
- Intelligent Design System Generation: outputs pattern, style, palette, typography, effects and anti-patterns.
- 161 industry-specific reasoning rules and 67 UI styles.
- Stack-aware output: HTML+Tailwind (default), React/Next.js, Vue/Nuxt, React Native, SwiftUI, Jetpack Compose, Flutter.
- CLI & scripts for local generation and persistence (optional).

Quick Install (recommended via CLI)
---------------------------------
1. Install the CLI globally (optional):

```
npm install -g uipro-cli
```

2. Initialize for your assistant (example for Claude):

```
uipro init --ai claude
```

Usage (example prompts)
-----------------------
- "Build a landing page for my SaaS product"
- "Design a dashboard for healthcare analytics with accessible colors"
- "Create a mobile app UI for e-commerce in React Native"

Advanced Commands (local scripts)
--------------------------------
- Generate a design system (ASCII):

```
python3 .claude/skills/ui-ux-pro-max/scripts/search.py "beauty spa wellness" --design-system -p "Serenity Spa"
```

- Generate Markdown output:

```
python3 .claude/skills/ui-ux-pro-max/scripts/search.py "fintech banking" --design-system -f markdown
```

How it works
------------
1. User request: natural language prompt describing product or page.
2. Multi-domain search and rule matching across styles, palettes, layouts and typography.
3. Reasoning engine composes a design system and stack-specific implementation suggestions.
4. Optional persistence to a `design-system/` folder (MASTER + per-page overrides).

Guidance for agents (best practices)
----------------------------------
- Ask clarifying questions for platform, responsiveness, target audiences and accessibility.
- Prefer explicit instructions when a specific stack or library is required (e.g., shadcn/ui, Tailwind config).
- Always validate contrast ratios and keyboard focus states for accessibility.
- Provide a minimal runnable code sample and a short explanation of where to plug it in.

Supported stacks
----------------
- HTML + Tailwind (default)
- React / Next.js / shadcn/ui
- Vue / Nuxt.js
- Angular
- React Native
- Flutter
- SwiftUI
- Jetpack Compose

Files & Structure (when installed locally)
-----------------------------------------
- `src/ui-ux-pro-max/` – core templates, rules, and scripts
- `cli/` – CLI installer and assets
- `.claude/skills/ui-ux-pro-max/` – local install layout for Claude Code

License
-------
This skill is distributed under the MIT License. When copying or referencing content, keep attribution and license where applicable.

Examples & Edge Cases
---------------------
- If the user asks for "dark mode only", recommend accessible palettes and outline trade-offs for contrast.
- When asked for a complex dashboard, suggest data density, card sizes, and chart types with brief reasoning.
- If a requested stack lacks component support, provide plain HTML + Tailwind or general CSS fallback.
```
