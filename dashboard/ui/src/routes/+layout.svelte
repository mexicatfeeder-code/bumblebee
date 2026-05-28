<script lang="ts">
  import { onMount } from 'svelte';
  import '../app.css';
  import { connection } from '$lib/stores/connection';
  import { projectsStore } from '$lib/stores/projects';
  import { researchStore } from '$lib/stores/research';
  import { drawerOpen, drawerMode, closeDrawer } from '$lib/stores/drawer';
  import StatusBanner from '$lib/components/StatusBanner.svelte';
  import Drawer from '$lib/components/Drawer.svelte';
  import IntakeView from '$lib/components/IntakeView.svelte';
  import ResearchIntakeView from '$lib/components/ResearchIntakeView.svelte';

  onMount(() => {
    connection.start();
    projectsStore.startPolling();
    researchStore.startPolling();
    return () => {
      connection.stop();
      projectsStore.stopPolling();
      researchStore.stopPolling();
    };
  });

  $: mode = $drawerMode;
  $: drawerTitle = mode === 'sift' ? 'New Research Request' : 'New Project';
</script>

<div class="layout-root">
  <main class="main-content">
    <StatusBanner />
    <slot />
  </main>

  <Drawer open={$drawerOpen} title={drawerTitle} on:close={closeDrawer}>
    {#if mode === 'sift'}
      <ResearchIntakeView />
    {:else}
      <IntakeView on:decompose-started={closeDrawer} />
    {/if}
  </Drawer>
</div>

<style>
  .layout-root {
    display: flex;
    min-height: 100vh;
    width: 100%;
    position: relative;
  }

  .main-content {
    flex: 1;
    min-width: 0;
    overflow-x: hidden;
    overflow-y: auto;
    padding: var(--spacing-panel-gap);
  }
</style>
