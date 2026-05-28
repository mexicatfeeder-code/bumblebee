<script lang="ts">
  import { onMount } from 'svelte';
  import { ticketStore } from '$lib/stores/tickets';
  import { telemetry } from '$lib/stores/telemetry';
  import { projectsStore, selectedProject } from '$lib/stores/projects';
  import PipelineView from '$lib/components/PipelineView.svelte';

  // Auto-select first project if none selected
  $: if (!$selectedProject && $projectsStore.projects.length > 0) {
    projectsStore.selectProject($projectsStore.projects[0].slug, 'dashboard');
  }

  // Connect ticket store to the selected project's DB
  let connectedSlug = '';
  $: currentSlug = $selectedProject?.slug ?? '';
  $: if (currentSlug && currentSlug !== connectedSlug) {
    connectedSlug = currentSlug;
    ticketStore.connect(currentSlug);
  }

  onMount(() => {
    telemetry.start();
    return () => {
      ticketStore.disconnect();
      telemetry.stop();
    };
  });
</script>

<PipelineView
  slug={$selectedProject?.slug ?? ''}
  projectName={$selectedProject?.name ?? 'Agent Swarm'}
  projectStatus={$selectedProject?.status ?? ''}
/>
