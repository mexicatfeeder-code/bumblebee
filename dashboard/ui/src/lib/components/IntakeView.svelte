<script lang="ts">
  import { projectsStore, selectedProject } from '$lib/stores/projects';
  import type { Project } from '$lib/stores/projects';
  import ChecklistStepper from './intake/ChecklistStepper.svelte';
  import IdentitySection from './intake/IdentitySection.svelte';
  import PrdUpload from './intake/PrdUpload.svelte';
  import ImageUpload from './intake/ImageUpload.svelte';
  import SettingsSection from './intake/SettingsSection.svelte';
  // AIConfigSection removed — decomposition uses cloud model by default
  import QAChat from './intake/QAChat.svelte';
  import DecompReview from './intake/DecompReview.svelte';
  import ExecutorControl from './intake/ExecutorControl.svelte';

  import ActionButtons from './intake/ActionButtons.svelte';
  import ErrorBanner from './intake/ErrorBanner.svelte';

  // Form state for new project creation
  let formName = '';
  let formSlug = '';
  let formDescription = '';
  let formCodeFolder = '';
  let formTargetSystem = 'local';
  // AI config state
  let aiQaModelSource = 'lemonade';
  let aiQaModelId = '';
  let aiDecompModelSource = 'lemonade';
  let aiDecompModelId = '';
  let aiForgeModelSource = 'custom';
  let aiForgeModelId = '';
  let aiVisionModelSource = 'custom';
  let aiVisionModelId = '';
  let aiCustomApiBaseUrl = '';
  let aiCustomApiKey = '';
  let aiConfigLoaded = false;
  let prdFilename: string | null = null;
  let prdText = '';
  let refImages: Array<{ url: string; name: string }> = [];
  let errorMessage = '';
  let actionLoading = false;

  // Sync form state when selected project changes
  $: project = $selectedProject;
  $: isNewProject = !project;

  // Stored source files from registry
  $: storedPrdPath = project?.prd_path ?? null;
  $: storedPrdName = storedPrdPath ? storedPrdPath.split(/[\\/]/).pop() ?? 'prd' : null;
  $: storedRefs = (() => {
    const raw = project?.ref_paths;
    if (!raw) return [];
    const arr: string[] = Array.isArray(raw) ? raw : (typeof raw === 'string' && raw.startsWith('[') ? JSON.parse(raw) : raw ? [raw] : []);
    return arr.filter(Boolean).map((p: string) => ({
      path: p,
      name: p.split(/[\\/]/).pop() ?? p,
    }));
  })();
  $: hasSourceFiles = !!storedPrdPath || storedRefs.length > 0;
  // Sync form state when project changes (or reset for new project)
  let lastProjectSlug: string | null = null;
  $: {
    const newSlug = project?.slug ?? null;
    if (newSlug !== lastProjectSlug) {
      lastProjectSlug = newSlug;
      if (project) {
        formName = project.name;
        formSlug = project.slug;
        formDescription = project.description;
        formCodeFolder = project.deliverable_root;
        formTargetSystem = project.target_system;
      } else {
        formName = '';
        formSlug = '';
        formDescription = '';
        formCodeFolder = '';
        formTargetSystem = 'local';
      }
      // Load global AI config defaults on first mount
      if (!aiConfigLoaded) {
        loadAIConfig();
        aiConfigLoaded = true;
      }
      // Reset transient state on any project switch
      prdFilename = project?.prd_path ? (project.prd_path.split(/[\\/]/).pop() ?? 'prd.md') : null;
      prdText = '';
      // Pre-populate ref images from stored paths
      const refs = project?.ref_paths;
      const refArr: string[] = Array.isArray(refs) ? refs : [];
      refImages = refArr.map(r => ({
        url: `/api/intake/projects/${project!.slug}/refs/${r.split(/[\\/]/).pop()}`,
        name: r.split(/[\\/]/).pop() ?? 'ref'
      }));
      errorMessage = '';
      actionLoading = false;
    }
  }

  // Determine if form is editable (only during intake phase)
  $: formDisabled = project ? !['intake'].includes(project.status) : false;

  // Default checklist for new projects
  $: checklist = project?.checklist ?? {
    named: false, prd_uploaded: false, refs_uploaded: false,
    qa_complete: false, approved: false, scaffolded: false, running: false
  };
  $: status = project?.status ?? 'intake';

  function onIdentityChange(e: CustomEvent<{ field: string; value: string }>) {
    const { field, value } = e.detail;
    if (field === 'name') formName = value;
    else if (field === 'slug') formSlug = value;
    else if (field === 'description') formDescription = value;
    else if (field === 'codeFolder') formCodeFolder = value;
  }

  function onSettingsChange(e: CustomEvent<{ field: string; value: string }>) {
    if (e.detail.field === 'targetSystem') formTargetSystem = e.detail.value;
  }

  function onAIConfigChange(e: CustomEvent<{ field: string; value: string }>) {
    const { field, value } = e.detail;
    if (field === 'qaModelSource') aiQaModelSource = value;
    else if (field === 'qaModelId') aiQaModelId = value;
    else if (field === 'decompModelSource') aiDecompModelSource = value;
    else if (field === 'decompModelId') aiDecompModelId = value;
    else if (field === 'forgeModelSource') aiForgeModelSource = value;
    else if (field === 'forgeModelId') aiForgeModelId = value;
    else if (field === 'visionModelSource') aiVisionModelSource = value;
    else if (field === 'visionModelId') aiVisionModelId = value;
    else if (field === 'customApiBaseUrl') aiCustomApiBaseUrl = value;
    else if (field === 'customApiKey') aiCustomApiKey = value;
  }

  async function loadAIConfig() {
    try {
      const resp = await fetch('/api/ai/config');
      if (resp.ok) {
        const data = await resp.json();
        aiQaModelSource = data.qa_model_source || 'lemonade';
        aiQaModelId = data.qa_model_id || '';
        aiDecompModelSource = data.decomp_model_source || 'lemonade';
        aiDecompModelId = data.decomp_model_id || '';
        aiForgeModelSource = data.forge_model_source || 'custom';
        aiForgeModelId = data.forge_model_id || '';
        aiVisionModelSource = data.vision_model_source || 'custom';
        aiVisionModelId = data.vision_model_id || '';
        aiCustomApiBaseUrl = data.custom_api_base_url || '';
        // Don't load masked key back
      }
    } catch {
      // Will use defaults
    }
  }

  async function onPrdFile(e: CustomEvent<{ file: File }>) {
    if (!project) {
      // Save locally until project is created
      prdFilename = e.detail.file.name;
      return;
    }
    const form = new FormData();
    form.append('file', e.detail.file);
    try {
      const resp = await fetch(`/api/intake/projects/${project.slug}/upload/prd`, {
        method: 'POST', body: form
      });
      if (!resp.ok) throw new Error((await resp.json()).detail || resp.statusText);
      prdFilename = e.detail.file.name;
      projectsStore.fetchProjects();
    } catch (err: any) {
      errorMessage = `PRD upload failed: ${err.message}`;
    }
  }

  function onPrdPaste(e: CustomEvent<{ text: string }>) {
    prdText = e.detail.text;
  }

  function onPrdClear() {
    prdFilename = null;
    prdText = '';
  }

  // Pending image files to upload after project creation
  let pendingImageFiles: File[] = [];

  async function onImageAdd(e: CustomEvent<{ files: FileList }>) {
    const files = Array.from(e.detail.files);
    if (!project) {
      // Store locally until project is created
      for (const f of files) {
        pendingImageFiles = [...pendingImageFiles, f];
        refImages = [...refImages, { url: URL.createObjectURL(f), name: f.name }];
      }
      return;
    }
    const form = new FormData();
    for (const f of files) {
      form.append('files', f);
    }
    try {
      const resp = await fetch(`/api/intake/projects/${project.slug}/upload/refs`, {
        method: 'POST', body: form
      });
      if (!resp.ok) throw new Error((await resp.json()).detail || resp.statusText);
      projectsStore.fetchProjects();
    } catch (err: any) {
      errorMessage = `Image upload failed: ${err.message}`;
    }
  }

  function onImageRemove(e: CustomEvent<{ index: number }>) {
    const idx = e.detail.index;
    // Revoke object URL to avoid memory leak
    if (refImages[idx]?.url?.startsWith('blob:')) {
      URL.revokeObjectURL(refImages[idx].url);
    }
    refImages = refImages.filter((_, i) => i !== idx);
    pendingImageFiles = pendingImageFiles.filter((_, i) => i !== idx);
  }

  async function createProject(): Promise<string | null> {
    try {
      // Save AI config as global defaults
      const aiConfig: Record<string, string> = {
        qa_model_source: aiQaModelSource,
        qa_model_id: aiQaModelId,
        decomp_model_source: aiDecompModelSource,
        decomp_model_id: aiDecompModelId,
        forge_model_source: aiForgeModelSource,
        forge_model_id: aiForgeModelId,
        vision_model_source: aiVisionModelSource,
        vision_model_id: aiVisionModelId,
        custom_api_base_url: aiCustomApiBaseUrl,
      };
      // Only include key if user entered a new one (not empty)
      if (aiCustomApiKey) {
        aiConfig.custom_api_key = aiCustomApiKey;
      }
      try {
        await fetch('/api/ai/config', {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(aiConfig)
        });
      } catch { /* non-fatal */ }

      const resp = await fetch('/api/intake/projects', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: formName,
          slug: formSlug,
          description: formDescription,
          deliverable_root: formCodeFolder,
          target_system: formTargetSystem,
          ai_config: aiConfig
        })
      });
      if (!resp.ok) throw new Error((await resp.json()).detail || resp.statusText);
      const data = await resp.json();
      await projectsStore.fetchProjects();
      projectsStore.selectProject(data.slug, 'intake');

      // Upload any pending image files
      if (pendingImageFiles.length > 0) {
        const imgForm = new FormData();
        for (const f of pendingImageFiles) {
          imgForm.append('files', f);
        }
        try {
          const imgResp = await fetch(`/api/intake/projects/${data.slug}/upload/refs`, {
            method: 'POST', body: imgForm
          });
          if (!imgResp.ok) {
            const detail = (await imgResp.json()).detail || imgResp.statusText;
            errorMessage = `Image upload failed: ${detail}`;
          }
        } catch (imgErr: any) {
          errorMessage = `Image upload failed: ${imgErr.message}`;
        }
        pendingImageFiles = [];
        await projectsStore.fetchProjects();
      }

      return data.slug;
    } catch (err: any) {
      errorMessage = `Failed to create project: ${err.message}`;
      return null;
    }
  }

  async function onBeginQA() {
    actionLoading = true;
    errorMessage = '';
    try {
      // Create project first if it doesn't exist
      let slug = project?.slug;
      if (!slug) {
        slug = await createProject();
        if (!slug) { actionLoading = false; return; }
      }
      // Transition to qa_pending — starts the Q&A chat flow
      const resp = await fetch(`/api/intake/projects/${slug}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: 'qa_pending' })
      });
      if (!resp.ok) throw new Error((await resp.json()).detail || resp.statusText);
      projectsStore.fetchProjects();
    } catch (err: any) {
      errorMessage = `Begin Q&A failed: ${err.message}`;
    }
    actionLoading = false;
  }

  async function onApprove() {
    if (!project) return;
    actionLoading = true;
    errorMessage = '';
    try {
      const resp = await fetch(`/api/intake/projects/${project.slug}/approve`, { method: 'POST' });
      if (!resp.ok) throw new Error((await resp.json()).detail || resp.statusText);
      projectsStore.fetchProjects();
    } catch (err: any) {
      errorMessage = `Approve failed: ${err.message}`;
    }
    actionLoading = false;
  }

  async function onBeginBuild() {
    if (!project) return;
    actionLoading = true;
    errorMessage = '';
    try {
      const resp = await fetch(`/api/intake/projects/${project.slug}/begin-build`, { method: 'POST' });
      if (!resp.ok) throw new Error((await resp.json()).detail || resp.statusText);
      projectsStore.fetchProjects();
    } catch (err: any) {
      errorMessage = `Begin Build failed: ${err.message}`;
    }
    actionLoading = false;
  }
</script>

<div class="intake-view">
  <!-- Page header -->
  <div class="intake-header">
    <h1 class="intake-title">
      {#if isNewProject}
        New Project
      {:else}
        {project?.name ?? 'Project'}
      {/if}
    </h1>
    {#if project}
      <span class="intake-meta">{project.slug} · Created {new Date(project.created_at).toLocaleDateString()}</span>
    {/if}
  </div>

  <!-- Status checklist -->
  {#if project}
    <ChecklistStepper {checklist} {status} />
  {/if}



  <!-- Error banner -->
  <ErrorBanner
    message={errorMessage}
    retryable={false}
    on:dismiss={() => errorMessage = ''}
  />

  <!-- Form panels -->
  <div class="intake-panels">
    <IdentitySection
      name={formName}
      slug={formSlug}
      description={formDescription}
      codeFolder={formCodeFolder}
      disabled={formDisabled}
      on:change={onIdentityChange}
    />

    <PrdUpload
      disabled={formDisabled}
      uploadedFilename={prdFilename}
      pastedText={prdText}
      on:file={onPrdFile}
      on:paste={onPrdPaste}
      on:clear={onPrdClear}
    />

    <ImageUpload
      images={refImages}
      disabled={formDisabled}
      on:add={onImageAdd}
      on:remove={onImageRemove}
    />

    <SettingsSection
      targetSystem={formTargetSystem}
      disabled={formDisabled}
      on:change={onSettingsChange}
    />


  </div>

  <!-- Q&A Chat (shown after project is created and in qa_pending status) -->
  {#if project && ['qa_pending', 'qa_complete'].includes(status)}
    <QAChat
      slug={project.slug}
      disabled={status === 'qa_complete'}
      on:finished={() => projectsStore.fetchProjects()}
    />
  {/if}

  <!-- Decomposition review (shown after Q&A is complete) -->
  {#if project && status === 'qa_complete'}
    <DecompReview
      slug={project.slug}
      on:committed={() => projectsStore.fetchProjects()}
    />
  {/if}

  <!-- Executor control (shown after tickets are committed) -->
  {#if project && ['approved', 'scaffolded', 'running'].includes(status)}
    <ExecutorControl slug={project.slug} />
  {/if}

  <!-- Action button -->
  <ActionButtons
    {status}
    checklist={{ named: !!formName, prd_uploaded: !!prdFilename || !!prdText, qa_complete: checklist.qa_complete, approved: checklist.approved, scaffolded: checklist.scaffolded }}
    loading={actionLoading}
    on:begin-qa={onBeginQA}
    on:approve={onApprove}
    on:begin-build={onBeginBuild}
  />
</div>

<style>
  .intake-view {
    max-width: 760px;
    margin: 0 auto;
    display: flex;
    flex-direction: column;
    gap: var(--spacing-panel-gap);
    padding-bottom: 40px;
  }

  .intake-header {
    margin-bottom: 4px;
  }

  .intake-title {
    font-size: 1.25rem;
    font-weight: 600;
    color: var(--color-text-primary);
    margin: 0;
  }

  .intake-meta {
    font-size: 0.75rem;
    color: var(--color-text-muted);
  }

  .intake-panels {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-panel-gap);
  }


</style>
