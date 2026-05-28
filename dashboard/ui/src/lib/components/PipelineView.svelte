<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { pipelineStore } from '$lib/stores/pipeline';
  import { ticketStore } from '$lib/stores/tickets';
  import type { PipelineState } from '$lib/stores/pipeline';
  import PixelActivity from '$lib/components/PixelActivity.svelte';
  import HardwarePanel from '$lib/components/HardwarePanel.svelte';
  import LocalAIPanel from '$lib/components/LocalAIPanel.svelte';

  export let slug: string = '';
  export let projectName: string = '';
  /** Project status from the projects store */
  export let projectStatus: string = '';

  let state: PipelineState;
  const unsub = pipelineStore.subscribe(s => state = s);

  // Cost data from API
  let cloudCost = 0;
  let localCost = 0;
  let costPoller: ReturnType<typeof setInterval> | null = null;

  // Auto-detect pipeline phase from project status on load
  let lastAutoSlug = '';
  $: if (slug && slug !== lastAutoSlug) {
    lastAutoSlug = slug;
    if (costPoller) clearInterval(costPoller);
    // If project is already in a build state, start polling
    if (['scaffolded', 'running', 'approved'].includes(projectStatus) && state.phase === 'idle') {
      pipelineStore.startCoding(slug);
    }
    // Poll costs
    fetchCosts(slug);
    costPoller = setInterval(() => fetchCosts(slug), 10000);
  }

  async function fetchCosts(s: string) {
    if (!s) return;
    try {
      const resp = await fetch(`/api/costs/${s}`);
      if (resp.ok) {
        const data = await resp.json();
        cloudCost = data.cloud_costs?.gpt4o ?? 0;
        localCost = data.local_cost ?? 0;
      }
    } catch { /* ignore */ }
  }

  // Sync pipeline store from ticket SSE
  let ticketUnsub: (() => void) | null = null;
  $: if (slug) {
    ticketUnsub?.();
    ticketUnsub = ticketStore.subscribe(ts => {
      if (ts.tickets.length > 0) {
        pipelineStore.updateFromTickets(ts.tickets);
      }
    });
  }

  onDestroy(() => {
    unsub();
    ticketUnsub?.();
    if (costPoller) clearInterval(costPoller);
  });

  // Show welcome state when no project is selected
  $: noProject = !slug;



  // Formatted elapsed time
  $: elapsed = formatTime(state.elapsedSeconds);

  function formatTime(s: number): string {
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return m > 0 ? `${m}m ${sec}s` : `${sec}s`;
  }

  // Phase activity states
  $: creatingActive = state.phase === 'creating';
  $: codingActive = state.phase === 'coding';
  $: qaActive = state.phase === 'qa' || state.phase === 'done';

  // Block values
  $: creatingCount = state.createdTickets;
  $: creatingTotal = state.totalTickets;
  $: codingCount = state.codingRemaining;
  $: qaCount = state.qaVerified;
  $: qaFailed = state.qaFailed;

  // Phase completion checks
  $: creatingDone = state.totalTickets > 0 && state.phase !== 'creating';
  $: codingDone = state.phase === 'qa' || state.phase === 'done';
  $: allDone = state.phase === 'done';
</script>

{#if noProject}
<div class="welcome-container">
  <div class="welcome-graphic">
    <svg width="80" height="80" viewBox="0 0 80 80" fill="none">
      <rect x="8" y="20" width="18" height="40" rx="4" fill="rgba(58,190,255,0.15)" stroke="rgba(58,190,255,0.4)" stroke-width="1.5"/>
      <rect x="31" y="12" width="18" height="56" rx="4" fill="rgba(89,227,138,0.15)" stroke="rgba(89,227,138,0.4)" stroke-width="1.5"/>
      <rect x="54" y="24" width="18" height="32" rx="4" fill="rgba(58,190,255,0.15)" stroke="rgba(58,190,255,0.4)" stroke-width="1.5"/>
      <path d="M28 40 L30 40" stroke="rgba(255,255,255,0.3)" stroke-width="1.5"/>
      <path d="M51 40 L53 40" stroke="rgba(255,255,255,0.3)" stroke-width="1.5"/>
    </svg>
  </div>
  <h2 class="welcome-title">Build Pipeline</h2>
  <p class="welcome-sub">Select a project from the sidebar, or create a new one to start building.</p>
</div>
{:else}
<div class="pipeline-container">
  <!-- Header -->
  <div class="pipeline-header">
    <div class="header-left">
      <span class="header-label">BUILD PIPELINE</span>
      <span class="header-project">{projectName}</span>
    </div>
    <div class="header-right">
      {#if state.phase !== 'idle'}
        <span class="elapsed-badge">{elapsed}</span>
      {/if}
      {#if state.error}
        <span class="error-badge">⚠ Error</span>
      {/if}
    </div>
  </div>

  <!-- Three-phase blocks -->
  <div class="phase-row">
    <!-- Creating Tickets -->
    <div class="phase-block" class:active={creatingActive} class:done={creatingDone} class:idle={!creatingActive && !creatingDone}>
      <div class="phase-top">
        <span class="phase-badge cloud">☁ Cloud</span>
        {#if creatingActive}
          <span class="phase-status pulse">Creating...</span>
        {:else if creatingDone}
          <span class="phase-status check">✓ Done</span>
        {/if}
      </div>
      <h3 class="phase-title">Creating Tickets</h3>
      <div class="phase-metric">
        <span class="metric-big">{creatingCount}</span>
        {#if creatingTotal > 0 && creatingDone}
          <span class="metric-sub">tickets created</span>
        {:else}
          <span class="metric-sub">tickets{creatingActive ? '...' : ''}</span>
        {/if}
      </div>
      {#if state.decompCost > 0}
        <span class="cost-label">~${state.decompCost.toFixed(2)}</span>
      {/if}
      {#if creatingActive}
        <div class="progress-bar">
          <div class="progress-fill pulse-bar"></div>
        </div>
      {/if}
    </div>

    <!-- Arrow -->
    <div class="phase-arrow" class:visible={creatingDone || codingActive}>
      <svg width="32" height="24" viewBox="0 0 32 24">
        <path d="M0 12 L24 12 M18 6 L24 12 L18 18" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
    </div>

    <!-- Coding -->
    <div class="phase-block" class:active={codingActive} class:done={codingDone} class:idle={!codingActive && !codingDone}>
      <div class="phase-top">
        <span class="phase-badge local">⚡ Local</span>
        {#if codingActive}
          <span class="phase-status pulse">Building...</span>
        {:else if codingDone}
          <span class="phase-status check">✓ Done</span>
        {/if}
      </div>
      <h3 class="phase-title">Coding</h3>
      <div class="phase-metric">
        {#if codingActive || codingDone}
          <span class="metric-big">{codingCount}</span>
          <span class="metric-sub">remaining</span>
        {:else}
          <span class="metric-big">--</span>
          <span class="metric-sub">waiting</span>
        {/if}
      </div>
      <span class="cost-label">$0.00</span>
      {#if state.codingCurrentId}
        <div class="current-ticket">
          <span class="current-label">Now:</span>
          <span class="current-id">{state.codingCurrentId}</span>
        </div>
      {/if}
      {#if codingActive}
        <div class="progress-bar">
          {#if state.totalTickets > 0}
            <div class="progress-fill" style="width: {Math.round(((state.totalTickets - codingCount) / state.totalTickets) * 100)}%"></div>
          {:else}
            <div class="progress-fill pulse-bar"></div>
          {/if}
        </div>
      {/if}
    </div>

    <!-- Arrow -->
    <div class="phase-arrow" class:visible={codingDone || qaActive}>
      <svg width="32" height="24" viewBox="0 0 32 24">
        <path d="M0 12 L24 12 M18 6 L24 12 L18 18" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
    </div>

    <!-- QA Review -->
    <div class="phase-block" class:active={qaActive && !allDone} class:done={allDone} class:idle={!qaActive}>
      <div class="phase-top">
        <span class="phase-badge cloud">☁ Cloud</span>
        {#if qaActive && !allDone}
          <span class="phase-status pulse">Reviewing...</span>
        {:else if allDone}
          <span class="phase-status check">✓ Ready</span>
        {/if}
      </div>
      <h3 class="phase-title">QA Review</h3>
      <div class="phase-metric">
        {#if qaActive || codingDone}
          <span class="metric-big">{qaCount}</span>
          <span class="metric-sub">verified</span>
        {:else}
          <span class="metric-big">--</span>
          <span class="metric-sub">waiting</span>
        {/if}
      </div>
      {#if qaFailed > 0}
        <span class="failed-badge">{qaFailed} blocked</span>
      {/if}
      {#if allDone}
        <button class="launch-btn" on:click={() => window.open(`/app/${slug}`, '_blank')}>
          🚀 Launch App
        </button>
      {/if}
    </div>
  </div>

  <!-- Error display -->
  {#if state.error}
    <div class="error-bar">
      <span class="error-icon">⚠</span>
      <span class="error-text">{state.error}</span>
    </div>
  {/if}

  <!-- System & Cost Metrics -->
  <div class="metrics-section">
    <!-- Row 1: Costs -->
    <div class="metrics-row">
      <div class="metric-card">
        <span class="mc-label">Total Tickets</span>
        <span class="mc-value">{state.totalTickets || state.createdTickets || '--'}</span>
      </div>
      <div class="metric-card">
        <span class="mc-label">Cloud Cost</span>
        <span class="mc-value cloud-cost">{cloudCost > 0 ? `$${cloudCost.toFixed(2)}` : state.decompCost > 0 ? `~$${state.decompCost.toFixed(2)}` : '$0.00'}</span>
      </div>
      <div class="metric-card">
        <span class="mc-label">Local Cost</span>
        <span class="mc-value local-cost">$0.00</span>
      </div>
      <div class="metric-card">
        <span class="mc-label">Elapsed</span>
        <span class="mc-value">{state.phase !== 'idle' ? elapsed : '--'}</span>
      </div>
    </div>

    <!-- Row 2: System Panels (Pixel Activity | Hardware | Local AI) -->
    <div class="three-col-row">
      <div class="panel">
        <PixelActivity />
      </div>
      <div class="panel">
        <HardwarePanel />
      </div>
      <div class="panel">
        <LocalAIPanel />
      </div>
    </div>
  </div>
</div>
{/if}

<style>
  /* Welcome state */
  .welcome-container {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 16px;
    min-height: 400px;
    opacity: 0.7;
  }

  .welcome-graphic {
    opacity: 0.6;
  }

  .welcome-title {
    font-size: 1.25rem;
    font-weight: 600;
    color: var(--color-text-primary);
    margin: 0;
  }

  .welcome-sub {
    font-size: 0.85rem;
    color: var(--color-text-muted);
    margin: 0;
    text-align: center;
    max-width: 360px;
  }

  .pipeline-container {
    display: flex;
    flex-direction: column;
    gap: 20px;
    width: 100%;
  }

  /* Header */
  .pipeline-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
  }

  .header-left {
    display: flex;
    flex-direction: column;
    gap: 3px;
  }

  .header-label {
    font-size: 0.7rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    color: var(--color-text-muted);
  }

  .header-project {
    font-size: 1rem;
    font-weight: 600;
    color: var(--color-text-primary);
  }

  .header-right {
    display: flex;
    gap: 8px;
    align-items: center;
  }

  .elapsed-badge {
    font-size: 0.75rem;
    font-family: var(--font-mono);
    color: var(--color-text-secondary);
    background: rgba(255, 255, 255, 0.06);
    padding: 3px 10px;
    border-radius: var(--radius-pill);
  }

  .error-badge {
    font-size: 0.7rem;
    color: var(--color-alert-blocked);
    background: rgba(255, 107, 107, 0.12);
    padding: 3px 10px;
    border-radius: var(--radius-pill);
  }

  /* Phase row */
  .phase-row {
    display: flex;
    align-items: stretch;
    gap: 0;
  }

  .phase-arrow {
    display: flex;
    align-items: center;
    padding: 0 8px;
    color: var(--color-text-muted);
    opacity: 0.2;
    transition: opacity 0.4s ease;
    flex-shrink: 0;
  }

  .phase-arrow.visible {
    opacity: 0.7;
    color: var(--color-accent-primary);
  }

  /* Phase block */
  .phase-block {
    flex: 1;
    background: var(--color-bg-panel);
    border: 1px solid rgba(255, 255, 255, 0.07);
    border-radius: var(--radius-panel);
    padding: 20px 24px;
    display: flex;
    flex-direction: column;
    gap: 10px;
    transition: border-color 0.3s ease, box-shadow 0.3s ease;
    min-width: 0;
  }

  .phase-block.idle {
    opacity: 0.4;
  }

  .phase-block.active {
    border-color: rgba(58, 190, 255, 0.4);
    box-shadow: 0 0 20px rgba(58, 190, 255, 0.08), inset 0 1px 0 rgba(255, 255, 255, 0.04);
    opacity: 1;
  }

  .phase-block.done {
    border-color: rgba(89, 227, 138, 0.3);
    box-shadow: 0 0 12px rgba(89, 227, 138, 0.06);
    opacity: 1;
  }

  /* Phase top row */
  .phase-top {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .phase-badge {
    font-size: 0.6rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    padding: 2px 8px;
    border-radius: var(--radius-pill);
  }

  .phase-badge.cloud {
    background: rgba(58, 190, 255, 0.12);
    color: var(--color-accent-primary);
  }

  .phase-badge.local {
    background: rgba(89, 227, 138, 0.12);
    color: var(--color-accent-worker);
  }

  .phase-status {
    font-size: 0.65rem;
    font-weight: 600;
    color: var(--color-text-muted);
  }

  .phase-status.pulse {
    color: var(--color-accent-primary);
    animation: statusPulse 2s ease-in-out infinite;
  }

  .phase-status.check {
    color: var(--color-accent-worker);
  }

  @keyframes statusPulse {
    0%, 100% { opacity: 0.6; }
    50% { opacity: 1; }
  }

  .phase-title {
    font-size: 0.85rem;
    font-weight: 600;
    color: var(--color-text-primary);
    margin: 0;
  }

  /* Phase metric */
  .phase-metric {
    display: flex;
    align-items: baseline;
    gap: 8px;
  }

  .metric-big {
    font-size: 2.2rem;
    font-weight: 700;
    font-family: var(--font-mono);
    color: var(--color-text-primary);
    line-height: 1;
  }

  .metric-sub {
    font-size: 0.75rem;
    color: var(--color-text-muted);
  }

  .cost-label {
    font-size: 0.7rem;
    font-family: var(--font-mono);
    color: var(--color-text-muted);
  }

  /* Current ticket indicator */
  .current-ticket {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 0.7rem;
    margin-top: 2px;
  }

  .current-label {
    color: var(--color-text-muted);
  }

  .current-id {
    font-family: var(--font-mono);
    color: var(--color-accent-primary);
    font-weight: 600;
  }

  /* Progress bar */
  .progress-bar {
    width: 100%;
    height: 3px;
    background: rgba(255, 255, 255, 0.06);
    border-radius: 2px;
    overflow: hidden;
    margin-top: auto;
  }

  .progress-fill {
    height: 100%;
    background: var(--color-accent-primary);
    border-radius: 2px;
    transition: width 0.5s ease;
  }

  .pulse-bar {
    width: 100%;
    background: linear-gradient(90deg, transparent, var(--color-accent-primary), transparent);
    animation: progressPulse 2s ease-in-out infinite;
  }

  @keyframes progressPulse {
    0% { transform: translateX(-100%); }
    100% { transform: translateX(100%); }
  }

  /* Failed badge */
  .failed-badge {
    font-size: 0.65rem;
    font-weight: 600;
    color: var(--color-alert-blocked);
    background: rgba(255, 107, 107, 0.12);
    padding: 2px 8px;
    border-radius: var(--radius-pill);
    width: fit-content;
  }

  /* Launch button */
  .launch-btn {
    margin-top: 8px;
    padding: 10px 20px;
    background: linear-gradient(135deg, var(--color-accent-worker), #2BC5A5);
    border: none;
    border-radius: 8px;
    color: #0B1220;
    font-family: var(--font-ui);
    font-size: 0.85rem;
    font-weight: 700;
    cursor: pointer;
    transition: transform 0.15s ease, box-shadow 0.15s ease;
  }

  .launch-btn:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 16px rgba(89, 227, 138, 0.3);
  }

  /* Error bar */
  .error-bar {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 16px;
    background: rgba(255, 107, 107, 0.08);
    border: 1px solid rgba(255, 107, 107, 0.2);
    border-radius: 8px;
    font-size: 0.8rem;
    color: var(--color-alert-blocked);
  }

  .error-icon { font-size: 1rem; }

  /* Bottom metrics row */
  .metrics-row {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
  }

  .metric-card {
    background: var(--color-bg-panel);
    border: 1px solid rgba(255, 255, 255, 0.07);
    border-radius: 8px;
    padding: 12px 16px;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .mc-label {
    font-size: 0.6rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--color-text-muted);
  }

  .mc-value {
    font-size: 1.1rem;
    font-weight: 700;
    font-family: var(--font-mono);
    color: var(--color-text-primary);
  }

  .mc-value.cloud-cost {
    color: var(--color-accent-primary);
  }

  .mc-value.local-cost {
    color: var(--color-accent-worker);
  }

  /* System panels row */
  .metrics-section {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .three-col-row {
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    gap: var(--spacing-row-gap);
  }

  .panel {
    background: var(--color-bg-panel);
    border: 1px solid rgba(255, 255, 255, 0.07);
    border-radius: var(--radius-panel);
    box-shadow: 0 4px 32px rgba(0, 0, 0, 0.5), inset 0 1px 0 rgba(255, 255, 255, 0.04);
    padding: var(--spacing-panel-pad);
    min-height: 200px;
  }

  /* Responsive */
  @media (max-width: 900px) {
    .phase-row {
      flex-direction: column;
      gap: 12px;
    }
    .phase-arrow {
      transform: rotate(90deg);
      padding: 4px 0;
      justify-content: center;
    }
    .metrics-row {
      grid-template-columns: repeat(2, 1fr);
    }
    .three-col-row {
      grid-template-columns: 1fr 1fr;
    }
  }
</style>
