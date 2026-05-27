# Dashboard Redesign — Conference Demo

**Priority: Ship tonight (2026-05-27)**

## Layout

### Top: Remove existing header panels
- Kill the KPI/hardware/loop-health panels that currently fill the top
- Reclaim vertical space for the three-phase pipeline view

### Left: Sliding Drawer (intake + project queue)
- **Top of drawer**: project list — active project highlighted, queued projects below
- **Drawer body**: intake form (name, PRD upload, Q&A chat)
- **Trigger**: "New Project" button opens drawer; decompose closes it automatically
- Drawer slides over the main content, doesn't push it

### Center: Three-Phase Pipeline (main view)

```
[ Creating Tickets ]  →  [    Coding    ]  →  [  QA Review  ]
     (cloud)               (local/Forge)        (cloud/Pixel)
```

#### Creating Tickets (left block)
- Shows streaming decomposition — tickets appear one by one as GPT-4.1-mini generates them
- Counter goes UP as tickets are created (e.g. "12 tickets")
- Cloud badge/indicator
- Once complete, tickets begin flowing to Coding block

#### Coding (center block)
- Shows Forge processing tickets from the queue
- Counter shows remaining (decreases as Forge completes them)
- Current ticket name/description visible
- Local badge/indicator — $0.00 cost emphasis
- Visual flow: tickets move from Creating → Coding → QA as they progress

#### QA Review (right block)
- Completed tickets land here
- Once Pixel cleanup is done and app is ready: **"Launch App" button** appears
- Human clicks to verify the built app
- Cloud badge (for Pixel cleanup step)

### Bottom: Metrics Row
- Keep existing metrics/cost comparison
- Cloud tokens + cost on left, local tokens + $0.00 on right
- Running time visible

## Visual Flow
- Tickets are the unit of visual progress
- Creating block count goes UP (generating)
- Coding block count goes DOWN (processing queue)
- QA block count goes UP (completed)
- Creates a natural left-to-right animation feel

## Key Interactions
1. Open drawer → fill in project → Q&A with local model → hit Decompose
2. Drawer closes, Creating Tickets block activates with streaming
3. Tickets flow to Coding block, Forge starts building
4. Completed tickets flow to QA block
5. Pixel does cleanup pass (unknown scope until we try)
6. "Launch App" button appears when ready
7. Human clicks to verify

## Open Questions
- How much cleanup does Pixel need post-Forge? TBD after first real build attempt
- Do we show individual ticket names in the Coding block, or just count?
- Settings/config access — gear icon? Or drawer has a settings tab?
