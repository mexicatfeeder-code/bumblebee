<script lang="ts">
  import { projectsStore, selectedProject } from '$lib/stores/projects';

  function selectProject(slug: string) {
    projectsStore.selectProject(slug, 'intake');
  }

  function newProject() {
    projectsStore.selectProject(null, 'intake');
  }

  $: projects = $projectsStore.projects;
  $: currentSlug = $selectedProject?.slug ?? null;

  function statusDot(status: string): string {
    if (status === 'running') return '#63d38f';
    if (status === 'scaffolded' || status === 'approved') return '#ffd166';
    return 'var(--color-accent-primary)';
  }

  function statusLabel(status: string): string {
    const map: Record<string, string> = {
      intake: 'intake',
      qa_pending: 'Q&A',
      qa_complete: 'ready to decompose',
      approved: 'approved',
      scaffolded: 'building',
      running: 'live',
    };
    return map[status] ?? status;
  }
</script>

<div class="project-list-section">
  <div class="list-header">
    <span class="list-title">PROJECTS</span>
    <button class="new-btn" on:click={newProject} class:active={!currentSlug}>
      + New
    </button>
  </div>

  {#if projects.length > 0}
    <div class="project-chips">
      {#each projects as p (p.slug)}
        <button
          class="project-chip"
          class:selected={currentSlug === p.slug}
          on:click={() => selectProject(p.slug)}
        >
          <span class="chip-dot" style="background: {statusDot(p.status)}"></span>
          <span class="chip-name">{p.name}</span>
          <span class="chip-status">{statusLabel(p.status)}</span>
        </button>
      {/each}
    </div>
  {/if}
</div>

<style>
  .project-list-section {
    margin-bottom: 20px;
    padding-bottom: 16px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  }

  .list-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 10px;
  }

  .list-title {
    font-size: 0.62rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: var(--color-text-muted);
  }

  .new-btn {
    font-size: 0.7rem;
    font-weight: 600;
    color: var(--color-accent-primary);
    background: transparent;
    border: 1px solid rgba(58, 190, 255, 0.3);
    border-radius: 4px;
    padding: 3px 10px;
    cursor: pointer;
    font-family: var(--font-ui);
    transition: background 0.15s;
  }

  .new-btn:hover, .new-btn.active {
    background: rgba(58, 190, 255, 0.1);
  }

  .project-chips {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .project-chip {
    display: flex;
    align-items: center;
    gap: 8px;
    width: 100%;
    padding: 8px 10px;
    background: transparent;
    border: 1px solid transparent;
    border-radius: 6px;
    cursor: pointer;
    font-family: var(--font-ui);
    text-align: left;
    transition: background 0.15s, border-color 0.15s;
  }

  .project-chip:hover {
    background: rgba(255, 255, 255, 0.04);
  }

  .project-chip.selected {
    background: rgba(58, 190, 255, 0.08);
    border-color: rgba(58, 190, 255, 0.2);
  }

  .chip-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    flex-shrink: 0;
  }

  .chip-name {
    flex: 1;
    font-size: 0.8rem;
    font-weight: 500;
    color: var(--color-text-primary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .chip-status {
    font-size: 0.65rem;
    color: var(--color-text-muted);
    flex-shrink: 0;
  }
</style>
