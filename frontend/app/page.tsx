"use client";

import { useEffect, useRef, useState } from "react";
import { Aperture, ArrowDownToLine, ArrowLeft, ArrowRight, AudioLines, Check, ChevronDown, CircleHelp, Clapperboard, Clock3, FileText, Film, FolderOpen, Fullscreen, Image as ImageIcon, Layers3, LoaderCircle, Maximize2, Music2, Pause, Play, Plus, Redo2, Scissors, Settings2, ShieldCheck, Sparkles, Trash2, Undo2, Upload, WandSparkles, X, ZoomIn, ZoomOut } from "lucide-react";

type Clip = { asset_id: string; start: number; end: number; zoom: number; volume: number; reason: string };
type MotionGraphic = { template: "kinetic_title" | "callout" | "lower_third" | "framecraft"; text: string; detail: string; start: number; duration: number; position: string; palette: string };
type Timeline = { clips: Clip[]; grade: string; aspect: "landscape" | "portrait"; captions: string; title: string; fade_out: boolean; music_asset_id: string | null; music_volume: number; motion_graphics?: MotionGraphic[] };
type Asset = { id: string; name: string; kind: "video" | "image" | "audio" | "text"; url: string; thumbnail_url: string; metadata: { duration: number; width?: number; height?: number; has_audio: boolean; word_count?: number; generated?: boolean } };
type Project = { id: string; name: string; revision: number; timeline: Timeline; assets: Asset[] };
type Style = { id: string; name: string; kind: "skill" | "reference" | "template"; description: string; default?: boolean; bundled?: boolean; slug?: string };
type DirectorConfig = { base_url: string; company_id: string; agent_id: string; key_configured: boolean };
type Job = { id: string; kind: string; status: string; progress: number; message: string; error: string | null; result: { summary?: string; warnings?: string[]; timeline?: Timeline; base_revision?: number; revision?: number; output_url?: string; verification_url?: string; style_id?: string; caption_cues?: number; actual_duration?: number; width?: number; height?: number } | null };
const blank: Timeline = { clips: [], grade: "none", aspect: "landscape", captions: "none", title: "", fade_out: false, music_asset_id: null, music_volume: .12 };
const duration = (t: Timeline) => t.clips.reduce((sum, c) => sum + c.end - c.start, 0);
const time = (t: number) => `${Math.floor(Math.max(0, t) / 60).toString().padStart(2, "0")}:${Math.floor(Math.max(0, t) % 60).toString().padStart(2, "0")}`;
const precise = (t: number) => { const c = Math.round(Math.max(0,t)*100); return `${time(Math.floor(c/100))}.${(c%100).toString().padStart(2,"0")}`; };
async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = { "X-Editor-Client": "video-use" };
  if (!(options.body instanceof FormData)) headers["Content-Type"] = "application/json";
  const result = await fetch(`/api${path}`, { ...options, headers: { ...headers, ...options.headers } });
  if (!result.ok) {
    const error = await result.json().catch(() => ({}));
    if (result.status === 401 && error.login === true) window.location.assign('/login');
    throw new Error(typeof error.detail === "string" ? error.detail : JSON.stringify(error.detail || "Request failed"));
  }
  return result.json();
}

export default function Studio() {
  const [projects, setProjects] = useState<{ id: string; name: string }[]>([]);
  const [project, setProject] = useState<Project | null>(null);
  const [timeline, setTimeline] = useState<Timeline>(blank);
  const [styles, setStyles] = useState<Style[]>([]);
  const [selectedStyle, setSelectedStyle] = useState("");
  const [generationAssetIds, setGenerationAssetIds] = useState<string[]>([]);
  const [tab, setTab] = useState("media");
  const [jobs, setJobs] = useState<Job[]>([]);
  const [prompt, setPrompt] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [uploading, setUploading] = useState(false);
  const [saving, setSaving] = useState(0);
  const [selected, setSelected] = useState(0);
  const [playhead, setPlayhead] = useState(0);
  const [activeClip, setActiveClip] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [useRender, setUseRender] = useState(true);
  const [zoom, setZoom] = useState(65);
  const [history, setHistory] = useState<Timeline[]>([]);
  const [future, setFuture] = useState<Timeline[]>([]);
  const [refIds, setRefIds] = useState<string[]>([]);
  const [referenceUrl, setReferenceUrl] = useState("");
  const [styleModal, setStyleModal] = useState<Style | null>(null);
  const [markdown, setMarkdown] = useState("");
  const [modal, setModal] = useState<"settings" | "export" | "new" | "transcript" | null>(null);
  const [transcriptDraft, setTranscriptDraft] = useState("");
  const [apiConfig, setApiConfig] = useState({ provider: "OpenAI", key: "", model: "", endpoint: "" });
  const [directorConfig, setDirectorConfig] = useState<DirectorConfig>({base_url:"https://agenticorg.hackathon.pinelabs.com",company_id:"",agent_id:"",key_configured:false});
  const [directorKey, setDirectorKey] = useState("");
  const [directorSaving, setDirectorSaving] = useState(false);
  const [directorLoading, setDirectorLoading] = useState(false);
  const [enhancing, setEnhancing] = useState(false);
  const [previousPrompt, setPreviousPrompt] = useState<string | null>(null);
  const directorPending = useRef(false);
  const generationPending = useRef(false);
  const [newName, setNewName] = useState("");
  const [runtime, setRuntime] = useState<{ authenticated_with_chatgpt: boolean; message: string; transcription: string } | null>(null);
  async function openSettings() {
    setModal("settings");
    setRuntime(null);
    setDirectorLoading(true);
    try { await Promise.all([api<NonNullable<typeof runtime>>("/runtime").then(setRuntime),api<DirectorConfig>("/director/config").then(setDirectorConfig)]); }
    catch (e) { fail(e); } finally { setDirectorLoading(false); }
  }
  const video = useRef<HTMLVideoElement>(null);
  const upload = useRef<HTMLInputElement>(null);
  const saveChain = useRef<Promise<void>>(Promise.resolve());
  const revision = useRef(0);
  const pendingSeek = useRef<number | null>(0);
  const processedRefs = useRef(new Set<string>());
  const processedGenerations = useRef(new Set<string>());
  const projectRef = useRef<string | null>(null);
  const total = duration(timeline);
  const active = jobs.find(j => ["queued", "running"].includes(j.status));
  const plan = jobs.find(j => j.kind === "plan" && j.status === "completed" && j.result?.base_revision === project?.revision);
  const rendered = jobs.find(j => ["generate", "preview", "export"].includes(j.kind) && j.status === "completed" && j.result?.revision === project?.revision);
  const showRendered = !!(rendered && useRender && saving === 0);
  const clip = timeline.clips[selected];
  const asset = project?.assets.find(a => a.id === timeline.clips[activeClip]?.asset_id);
  const videoSource = showRendered ? rendered?.result?.output_url : asset?.url;

  async function refreshProjects() {
    const list = await api<{ id: string; name: string }[]>("/projects"); setProjects(list); return list;
  }
  async function load(id: string) {
    await saveChain.current;
    const p = await api<Project>(`/projects/${id}`);
    projectRef.current = p.id; revision.current = p.revision;
    setGenerationAssetIds([]);
    setPreviousPrompt(null);
    setProject(p); setTimeline(p.timeline); setHistory([]); setFuture([]); setPlayhead(0); setSelected(0); setActiveClip(0); setPlaying(false); setUseRender(true); setSelectedStyle(""); setRefIds([]); setError("");
    localStorage.setItem("video-use-project", id);
    const availableStyles = await api<Style[]>(`/projects/${id}/styles`);
    setStyles(availableStyles);
    setSelectedStyle(availableStyles.find(s => s.default)?.id || "");
    setJobs(await api<Job[]>(`/projects/${id}/jobs`));
  }
  useEffect(() => { (async () => {
    try {
      const list = await refreshProjects();
      const remembered = localStorage.getItem("video-use-project");
      if (list.length) await load(list.find(p => p.id === remembered)?.id || list[0].id);
      else { const p = await api<Project>("/projects", { method: "POST", body: JSON.stringify({ name: "My first cut" }) }); await refreshProjects(); await load(p.id); }
      setRuntime(await api("/runtime"));
    } catch (e) { setError((e as Error).message + " · Check that the local backend is running."); }
  })(); }, []);
  useEffect(() => {
    if (!project) return;
    const id = project.id;
    let alive = true;
    const timer = setInterval(async () => {
      try {
        const list = await api<Job[]>(`/projects/${id}/jobs`);
        if (!alive || projectRef.current !== id) return;
        setJobs(list);
        for (const j of list) if (j.kind === "generate" && j.status === "completed" && !processedGenerations.current.has(j.id)) {
          processedGenerations.current.add(j.id);
          if ((j.result?.revision ?? 0) <= revision.current) continue;
          const updated = await api<Project>(`/projects/${id}`);
          if (!alive || projectRef.current !== id) return;
          revision.current = updated.revision;
          setProject(updated); setTimeline(updated.timeline); setSelected(0); setActiveClip(0);
          setHistory([]); setFuture([]); setUseRender(true); setPlaying(false); setPlayhead(0); pendingSeek.current = 0;
          setNotice("Your video is ready on the timeline");
          await refreshProjects();
        }
        for (const j of list) if (j.kind === "reference" && j.status === "completed" && !processedRefs.current.has(j.id)) {
          processedRefs.current.add(j.id);
          setStyles(await api<Style[]>(`/projects/${id}/styles`));
          if (j.result?.style_id) setSelectedStyle(j.result.style_id);
        }
      } catch (e) { if (alive) setError((e as Error).message); }
    }, 1600);
    return () => { alive = false; clearInterval(timer); };
  }, [project?.id]);
  useEffect(() => { if (!notice) return; const t = setTimeout(() => setNotice(""), 4500); return () => clearTimeout(t); }, [notice]);
  useEffect(() => {
    if (!video.current) return;
    const v = video.current;
    const update = () => {
      const target = pendingSeek.current ?? (showRendered ? playhead : timeline.clips[activeClip]?.start || 0);
      v.currentTime = target; pendingSeek.current = null;
      if (playing) v.play().catch(() => setPlaying(false));
    };
    if (v.readyState >= 1) update();
    else v.addEventListener("loadedmetadata", update, { once: true });
    return () => v.removeEventListener("loadedmetadata", update);
  }, [videoSource, activeClip, showRendered, timeline]);

  function fail(e: unknown) { setError((e as Error).message); }
  function commit(next: Timeline, record = true) {
    if (!project) return;
    if (active?.kind === "generate") { setNotice("Your video is generating. Timeline edits will be available when it is ready."); return; }
    const remaining = duration(next);
    next = { ...next, motion_graphics: (next.motion_graphics || []).filter(g => remaining-g.start >= (g.template === "framecraft" ? 3 : .3)).map(g => ({ ...g, duration: Math.min(g.duration, remaining-g.start) })) };
    if (record) { setHistory(h => [...h.slice(-39), timeline]); setFuture([]); }
    pendingSeek.current = next.clips[0]?.start || 0;
    setPlayhead(0); setActiveClip(0);
    setTimeline(next); setUseRender(false); setPlaying(false); video.current?.pause(); setSaving(s => s + 1);
    const id = project.id;
    saveChain.current = saveChain.current.then(async () => {
      const p = await api<Project>(`/projects/${id}/timeline`, { method: "PUT", body: JSON.stringify({ revision: revision.current, timeline: next }) });
      revision.current = p.revision; if (projectRef.current === id) setProject(p);
    }).catch(async e => {
      fail(e);
      try {
        const saved = await api<Project>(`/projects/${id}`);
        revision.current = saved.revision;
        if (projectRef.current === id) { setProject(saved); setTimeline(saved.timeline); }
      } catch { /* The error toast remains visible; reconnect and reopen the project. */ }
    }).finally(() => setSaving(s => s - 1));
    // Mark the rejection handled while retaining it for dependent actions.
    saveChain.current.catch(() => {});
  }
  function undo() { if (!history.length) return; const previous = history[history.length-1]; setHistory(h => h.slice(0, -1)); setFuture(f => [timeline, ...f]); commit(previous, false); }
  function redo() { if (!future.length) return; setHistory(h => [...h, timeline]); const next = future[0]; setFuture(f => f.slice(1)); commit(next, false); }
  function seekTo(t: number) {
    const target = Math.max(0, Math.min(t, total - .001)); setPlayhead(target);
    if (showRendered) { if (video.current) video.current.currentTime = target; return; }
    let offset = 0;
    for (let i = 0; i < timeline.clips.length; i++) {
      const c = timeline.clips[i], len = c.end - c.start;
      if (target < offset + len || i === timeline.clips.length - 1) {
        const sourceTime = c.start + target - offset;
        pendingSeek.current = sourceTime;
        if (i === activeClip && video.current) { video.current.currentTime = sourceTime; pendingSeek.current = null; }
        setActiveClip(i); return;
      }
      offset += len;
    }
  }
  function togglePlayback() {
    const v = video.current; if (!v) return;
    if (playing) { v.pause(); setPlaying(false); }
    else { if (playhead >= total - .06) seekTo(0); v.play().then(() => setPlaying(true)).catch(fail); }
  }
  function tick() {
    const v = video.current; if (!v || !playing) return;
    if (showRendered) { setPlayhead(Math.min(total, v.currentTime)); return; }
    const c = timeline.clips[activeClip]; if (!c) return;
    const offset = timeline.clips.slice(0, activeClip).reduce((s, c) => s + c.end - c.start, 0);
    setPlayhead(Math.min(total, offset + v.currentTime - c.start));
    if (v.currentTime >= c.end - .03) {
      if (activeClip + 1 < timeline.clips.length) { pendingSeek.current = timeline.clips[activeClip+1].start; setActiveClip(activeClip+1); }
      else { v.pause(); setPlaying(false); setPlayhead(total); }
    }
  }
  async function importFiles(files: FileList | File[] | null, asReference = false) {
    if (!files || !project) return; setUploading(true); setError("");
    try {
      const imported: Asset[] = [];
      for (const file of Array.from(files)) {
        if (!["127.0.0.1", "localhost"].includes(window.location.hostname)) {
          const upload = await api<{id:string;chunk_size:number}>("/bridge/uploads",{method:"POST",body:JSON.stringify({project_id:project.id,name:file.name,size:file.size})});
          for(let offset=0;offset<file.size;offset+=upload.chunk_size) await api(`/bridge/uploads/${upload.id}?offset=${offset}`,{method:"PATCH",headers:{"Content-Type":"application/octet-stream"},body:file.slice(offset,offset+upload.chunk_size)});
          imported.push(await api<Asset>(`/bridge/uploads/${upload.id}/finish`,{method:"POST"}));
        } else {
          const form = new FormData(); form.append("file", file); imported.push(await api<Asset>(`/projects/${project.id}/assets`, { method: "POST", body: form }));
        }
      }
      const p = await api<Project>(`/projects/${project.id}`); setProject(p);
      if (asReference) setRefIds(imported.filter(a => ["video","image"].includes(a.kind)).map(a => a.id));
      else setGenerationAssetIds(imported.filter(a => ["video","audio","text"].includes(a.kind)).map(a => a.id));
      setNotice(`Imported ${imported.length} file${imported.length === 1 ? "" : "s"}`);
    } catch (e) { fail(e); } finally { setUploading(false); if (upload.current) upload.current.value = ""; }
  }
  function addClip(a: Asset) {
    setGenerationAssetIds([]);
    const end = Math.min(a.metadata.duration, 180 - total);
    if (end < .12) { setError("Timeline limit reached (180 seconds)."); return; }
    commit({ ...timeline, clips: [...timeline.clips, { asset_id: a.id, start: 0, end, zoom: 1, volume: 1, reason: "Added manually" }] });
    setSelected(timeline.clips.length);
  }
  function changeClip(patch: Partial<Clip>) { if (!clip) return; commit({ ...timeline, clips: timeline.clips.map((c, i) => i === selected ? { ...c, ...patch } : c) }); }
  function moveClip(from: number, to: number) { if (to < 0 || to >= timeline.clips.length || from === to) return; const clips = [...timeline.clips]; const [moved] = clips.splice(from, 1); clips.splice(to, 0, moved); commit({ ...timeline, clips }); setSelected(to); }
  function split() {
    let offset = 0;
    for (let i = 0; i < timeline.clips.length; i++) {
      const c = timeline.clips[i], len = c.end-c.start, at = c.start + playhead-offset;
      if (playhead >= offset && playhead <= offset+len) {
        if (at-c.start < .12 || c.end-at < .12) { setError("Move the playhead at least 0.12 seconds from either clip edge."); return; }
        const clips = [...timeline.clips]; clips.splice(i, 1, { ...c, end: at }, { ...c, start: at }); commit({ ...timeline, clips }); setSelected(i+1); return;
      } offset += len;
    }
  }
  async function startJob(kind: string, extra: Record<string, unknown> = {}) {
    if (!project) return; setError("");
    try { await saveChain.current; const j = await api<Job>(`/projects/${project.id}/jobs`, { method: "POST", body: JSON.stringify({ kind, ...extra }) }); setJobs(list => [j, ...list]); if (["preview", "export"].includes(kind)) setUseRender(true); }
    catch (e) { fail(e); }
  }
  async function generateVideo() {
    if (!prompt.trim() || active || uploading || saving || directorPending.current || generationPending.current) return;
    generationPending.current=true;
    try { await startJob("generate", { prompt, style_id: selectedStyle || null, aspect: timeline.aspect, input_asset_ids: generationAssetIds }); }
    finally { generationPending.current=false; }
  }
  async function enhanceDirector() {
    if (!project || !prompt.trim() || active || directorPending.current) return;
    directorPending.current=true; setEnhancing(true); setError("");
    const id=project.id, original=prompt;
    try {
      const result=await api<{prompt:string;provider:string}>(`/projects/${id}/enhance`,{method:"POST",body:JSON.stringify({prompt:original,style_id:selectedStyle || null,aspect:timeline.aspect,input_asset_ids:generationAssetIds})});
      if(projectRef.current===id){setPreviousPrompt(original);setPrompt(result.prompt);setNotice("Director prompt enhanced with Pine Labs AgenticOrg");}
    } catch(e){fail(e);} finally{directorPending.current=false;setEnhancing(false);}
  }
  async function saveDirectorConnection() {
    setDirectorSaving(true);setError("");
    try {
      const config=await api<DirectorConfig>("/director/config",{method:"PUT",body:JSON.stringify({base_url:directorConfig.base_url,company_id:directorConfig.company_id,agent_id:directorConfig.agent_id,api_key:directorKey || null})});
      setDirectorConfig(config);setDirectorKey("");setNotice("AgenticOrg connection settings saved");
    } catch(e){fail(e);}finally{setDirectorSaving(false);}
  }
  async function importTranscript() {
    if (!project || !transcriptDraft.trim()) return;
    setUploading(true);
    try {
      const imported = await api<Asset>(`/projects/${project.id}/transcript`, { method: "POST", body: JSON.stringify({ text: transcriptDraft.trim() }) });
      setGenerationAssetIds([imported.id]);
      setProject(await api<Project>(`/projects/${project.id}`));
      setModal(null); setTranscriptDraft(""); setNotice("Transcript imported. Choose a style and describe your video.");
    } catch (e) { fail(e); } finally { setUploading(false); }
  }
  async function approve() {
    if (!plan) return;
    try {
      await saveChain.current;
      const approved = await api<{ project: Project; job: Job }>(`/jobs/${plan.id}/approve`, { method: "POST" });
      setHistory(h => [...h, timeline]); setFuture([]); setTimeline(approved.project.timeline); setProject(approved.project); revision.current = approved.project.revision; setJobs(js => [approved.job, ...js]); setUseRender(true); seekTo(0);
    } catch (e) { fail(e); }
  }
  async function inspectStyle(s: Style) { try { setMarkdown((await api<{ markdown: string }>(`/projects/${project!.id}/styles/${s.id}`)).markdown); setStyleModal(s); } catch (e) { fail(e); } }
  async function importUrl() { if (!referenceUrl || !project) return; setUploading(true); try { const a = await api<Asset>(`/projects/${project.id}/reference-url`, { method: "POST", body: JSON.stringify({ url: referenceUrl }) }); setProject(await api(`/projects/${project.id}`)); setRefIds([a.id]); setReferenceUrl(""); setNotice("Reference downloaded. Ready to analyze."); } catch (e) { fail(e); } finally { setUploading(false); } }
  const assets = project?.assets || [];
  const offsetOf = (i: number) => timeline.clips.slice(0,i).reduce((s,c) => s+c.end-c.start, 0);

  return <main className="studio">
    <header className="topbar">
      <a className="brand" href="/" aria-label="ImaginePro"><span className="brand-icon"><svg width="23" height="23" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M5 4.5h5M5 4.5v15h5M14 5l6 7-6 7V5Z" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/></svg></span><span className="brand-wordmark">Imagine<span>Pro</span></span><span className="brand-label">CREATIVE STUDIO</span></a>
      <div className="project-picker"><FolderOpen size={15}/><select aria-label="Current project" value={project?.id || ""} onChange={e => load(e.target.value).catch(fail)}>{projects.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}</select><ChevronDown size={13}/><button className="icon-button" title="New project" onClick={() => setModal("new")}><Plus size={15}/></button></div>
      <div className="header-right"><span className="save-status">{saving ? <LoaderCircle className="spin" size={12}/> : <Check size={12}/>} {saving ? "Saving…" : "Saved locally"}</span><button className="icon-button settings-button" aria-label="AI settings" title="AI settings and system status" onClick={openSettings}><Settings2 size={16}/><span>Settings</span></button><button className="primary small" onClick={() => setModal("export")} disabled={!timeline.clips.length}><ArrowDownToLine size={15}/>Export video</button><div className="avatar" title="Local owner">N</div></div>
    </header>

    <nav className="rail" aria-label="Workspace panels"><button className={tab === "media" ? "rail-button active" : "rail-button"} onClick={() => setTab("media")} title="Media library"><FolderOpen size={21}/><span>Media</span></button><button className={tab === "styles" ? "rail-button active" : "rail-button"} onClick={() => setTab("styles")} title="Editing styles"><Layers3 size={21}/><span>Styles</span></button><button className={tab === "references" ? "rail-button active" : "rail-button"} onClick={() => setTab("references")} title="Reference analysis"><ImageIcon size={21}/><span>Reference</span></button><div className="rail-spacer"/><button className="rail-button" title="Setup and help" onClick={openSettings}><CircleHelp size={20}/><span>Help</span></button><span className="local-dot" title="Local owner mode"/></nav>

    <aside className="library">
      <div className="panel-heading"><h2>{tab === "media" ? "Project media" : tab === "styles" ? "Editing styles" : "Reference lab"}</h2><span className="counter">{tab === "styles" ? styles.length : assets.length}</span></div>
      {tab === "media" && <>
        <div className="library-subnav"><span className="selected">All assets</span><span>{assets.filter(a=>a.kind==="video").length} videos</span></div>
        <input ref={upload} className="hidden" type="file" multiple accept="video/*,audio/*,image/png,image/jpeg,image/webp,.txt,.srt,.vtt" onChange={e=>importFiles(e.target.files)}/>
        <button className="upload-zone" onClick={()=>upload.current?.click()} onDragOver={e=>e.preventDefault()} onDrop={e=>{ e.preventDefault(); importFiles(e.dataTransfer.files); }} disabled={uploading}><span className="upload-icon">{uploading ? <LoaderCircle className="spin" size={21}/> : <Upload size={21}/>}</span><strong>{uploading ? "Importing media…" : "Import video, audio or a transcript"}</strong><span>or click to browse files</span><small>Video, audio, images · TXT, SRT, VTT</small></button><button className="secondary transcript-import" onClick={()=>setModal("transcript")}><FileText size={14}/>Paste a transcript</button>
        <div className="section-label">IMPORTED <span>{assets.length}</span></div>
        <div className="asset-list">{assets.map(a=><div className="asset-card" key={a.id}>
          <div className="asset-thumbnail">{a.kind === "text" ? <FileText size={32}/> : a.kind !== "audio" ? <img src={a.thumbnail_url} alt={a.name}/> : <AudioLines size={32}/>}<span className="asset-kind">{a.kind === "video" ? <Film size={12}/> : a.kind === "audio" ? <Music2 size={12}/> : a.kind === "text" ? <FileText size={12}/> : <ImageIcon size={12}/>}</span>{a.metadata.duration > 0 && <span className="asset-duration">{time(a.metadata.duration)}</span>}{a.kind === "video" && <button className="asset-add" onClick={()=>addClip(a)} title={`Add ${a.name} to timeline`}><Plus size={15}/></button>}</div>
          <div className="asset-info"><strong title={a.name}>{a.name}</strong><span>{a.kind === "video" ? `${a.metadata.width} × ${a.metadata.height}` : a.kind === "audio" ? "Voiceover / audio" : a.kind === "text" ? `${a.metadata.word_count || 0} words · transcript` : "Reference image"}{a.kind === "video" && <button onClick={()=>addClip(a)} aria-label={`Add ${a.name}`}>Add to timeline <Plus size={11}/></button>}</span></div>
        </div>)}{!assets.length && <p className="empty-hint">Start with footage, a voiceover or a transcript.<br/>Then choose a style and describe your video.</p>}</div>
        {rendered && <><div className="section-label">GENERATED</div><a className="generated-asset" href={rendered.result?.output_url + "?download=true"}><Clapperboard size={18}/><div><strong>{rendered.kind === "generate" ? "Generated video" : `Edited ${rendered.kind}`}</strong><span>H.264 · {rendered.result?.width} × {rendered.result?.height}</span></div><ArrowDownToLine size={15}/></a></>}
        <div className="library-footer"><ShieldCheck size={14}/><span>Original footage stays untouched</span></div>
      </>}
      {tab === "styles" && <div className="styles-body">
        <div className="style-intro"><span className="eyebrow">FIND YOUR SIGNATURE</span><p>Choose a visual direction for your next edit. Style guides shape the plan using supported effects.</p></div>
        <button className={`style-card ${!selectedStyle ? "chosen" : ""}`} onClick={()=>setSelectedStyle("")}><span className="style-swatch natural"><Aperture size={22}/></span><span className="style-copy"><strong>Let the footage lead</strong><small>Prompt only · no style selected</small></span>{!selectedStyle && <Check size={14}/>}</button>
        {styles.map(s=><div key={s.id} className={`style-card ${selectedStyle===s.id ? "chosen" : ""}`}>
          <button className="style-select" onClick={()=>setSelectedStyle(s.id)} aria-pressed={selectedStyle===s.id}>
            <span className={`style-swatch ${s.kind}`} data-style={s.slug || s.id} aria-hidden="true">
              {s.slug === "kinetic-typography" ? <span className="type-mark">Aa</span> : s.slug === "vox-explainer" ? <span className="editorial-mark">V.</span> : s.slug === "apple-launch-film" ? <Maximize2 size={22}/> : s.slug === "hand-drawn-cartoon" ? <svg width="28" height="28" viewBox="0 0 32 32" fill="none"><path d="M6 17C4 8 11 4 18 5c8 0 10 7 9 14-1 7-8 9-14 7-5 0-7-4-7-9Z" stroke="currentColor" strokeWidth="1.6"/><path d="M11 20q5 4 10-1" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"/><circle cx="12" cy="14" r="1.3" fill="currentColor"/><circle cx="21" cy="13" r="1.3" fill="currentColor"/></svg> : <Layers3 size={20}/>}
            </span>
            <span className="style-copy"><strong>{s.name}</strong><small>{s.kind === "template" ? "Default template · Framecraft.md" : s.kind === "reference" ? "Reference · clean.md" : s.bundled ? "Installed style guide" : "Manual · SKILL.md"}</small>{s.bundled && <span className="style-description">{s.description}</span>}</span>
          </button>
          <button className="text-button" onClick={()=>inspectStyle(s)} title={`Inspect ${s.name}`}>View</button>
        </div>)}
        <button className="secondary full" onClick={()=>setTab("references")}><Plus size={15}/>Create style from reference</button>
      </div>}
      {tab === "references" && <div className="references-body"><div className="reference-intro"><WandSparkles size={25}/><h3>Learn the look.</h3><p>Extract a reusable style from one video or up to eight images.</p></div><label className="secondary full file-label"><Upload size={14}/>Upload reference<input type="file" className="hidden" accept="video/*,image/png,image/jpeg,image/webp" multiple onChange={e=>importFiles(e.target.files,true)}/></label><div className="or"><span/>or use a direct media URL<span/></div><input className="text-input" aria-label="Reference media URL" placeholder="https://example.com/reference.mp4" value={referenceUrl} onChange={e=>setReferenceUrl(e.target.value)}/><button className="secondary full" disabled={uploading || !referenceUrl} onClick={importUrl}>{uploading ? <LoaderCircle size={14} className="spin"/> : <ArrowDownToLine size={14}/>}Import URL</button><div className="section-label">SELECT REFERENCE</div><div className="reference-list">{assets.filter(a=>["video","image"].includes(a.kind)).map(a=><label className="reference-choice" key={a.id}><input type="checkbox" checked={refIds.includes(a.id)} onChange={e=>setRefIds(ids=>e.target.checked ? [...ids,a.id] : ids.filter(id=>id!==a.id))}/><img src={a.thumbnail_url} alt=""/><span>{a.name}<small>{a.kind}</small></span></label>)}</div><button className="primary full" disabled={!refIds.length || !!active} onClick={()=>startJob("reference", {reference_asset_ids:refIds})}><Sparkles size={15}/>Analyze & create clean.md</button><p className="tiny muted">Bounded scene sampling and visual analysis. Image references cannot reveal pacing, motion, or audio. Unsupported URL pages can be uploaded as permitted files.</p></div>}
    </aside>

    <section className="viewer">
      <div className="viewer-toolbar"><div className="breadcrumb"><span>Editor</span><span>/</span><strong>{project?.name || "Opening workspace…"}</strong></div><select aria-label="Video aspect ratio" value={timeline.aspect} onChange={e=>commit({...timeline,aspect:e.target.value as Timeline["aspect"]})}><option value="landscape">16:9 · Landscape</option><option value="portrait">9:16 · Portrait</option></select></div>
      <div className="preview-stage"><div className={`video-frame ${timeline.aspect}`}>
        {videoSource ? <video ref={video} src={videoSource} poster={asset?.thumbnail_url} playsInline preload="metadata" onTimeUpdate={tick} onEnded={()=>{ if(showRendered || activeClip===timeline.clips.length-1){setPlaying(false);setPlayhead(total);}else{pendingSeek.current=timeline.clips[activeClip+1].start;setActiveClip(activeClip+1);} }} onClick={togglePlayback}/> : <div className="empty-preview"><div className="empty-aperture"><Aperture size={42}/></div><h1>Imagine it. Make it.</h1><p>Import your video or transcript, choose a style, and press Enter.</p><button className="secondary" onClick={()=>{setTab("media");upload.current?.click();}}><Plus size={14}/>Import media</button></div>}
        {videoSource && <><span className="preview-badge"><span className={showRendered ? "green-dot" : "amber-dot"}/>{showRendered ? "RENDERED PREVIEW" : "SOURCE PREVIEW"}</span>{!playing && <button className="big-play" aria-label="Play preview" onClick={togglePlayback}><Play size={25} fill="currentColor"/></button>}</>}
      </div></div>
      <div className="playback-bar"><span className="timecode">{precise(playhead)}<span>/ {precise(total)}</span></span><div className="transport"><button className="icon-button" title="Start" onClick={()=>seekTo(0)} disabled={!total}><ArrowLeft size={16}/></button><button className="play-button" aria-label={playing ? "Pause" : "Play"} onClick={togglePlayback} disabled={!videoSource}>{playing ? <Pause size={18} fill="currentColor"/> : <Play size={18} fill="currentColor"/>}</button><button className="icon-button" title="End" onClick={()=>seekTo(total-.04)} disabled={!total}><ArrowRight size={16}/></button></div><div className="preview-options"><span>{showRendered ? `${rendered?.result?.height}p` : "Source"}</span><button className="icon-button" aria-label="Fullscreen preview" onClick={()=>video.current?.requestFullscreen().catch(fail)} disabled={!videoSource}><Fullscreen size={16}/></button></div></div>
      <div className="preview-note">{showRendered ? <><Check size={12}/>Verified render · matches saved timeline revision {project?.revision}</> : <><CircleHelp size={12}/>Source playback shows cuts. Render a preview to review captions, color and graphics.</>}</div>
    </section>

    <aside className="assistant-panel"><div className="assistant-heading"><span className="ai-icon"><Sparkles size={17}/></span><h2>AI editor</h2><span className="beta-tag">LOCAL</span></div><div className="assistant-scroll"><div className="assistant-welcome"><span className="eyebrow">FROM RAW TO READY</span><h2>Your idea.<br/><span>In motion.</span></h2><p>Choose a style and describe your video.<br/>Press Enter. We’ll create it on your timeline.</p></div>
      <div className="quick-prompts">{["Remove pauses and add subtitles", "Create a 30-second highlight", "Make this more cinematic"].map(text=><button key={text} onClick={()=>setPrompt(text)}><WandSparkles size={13}/>{text}<ArrowRight size={12}/></button>)}</div>
      <div className="workflow-note"><div><span>1</span>Import</div><i/><div><span>2</span>Style & prompt</div><i/><div><span>3</span>Generate</div></div>
      {active && <div className="job-progress"><div><LoaderCircle className="spin" size={16}/><strong>{active.kind === "generate" ? "Creating your video" : active.kind === "plan" ? "Building your edit" : active.kind === "reference" ? "Learning the style" : "Rendering video"}</strong><button className="icon-button" aria-label="Cancel job" onClick={()=>api(`/jobs/${active.id}/cancel`,{method:"POST"}).catch(fail)}><X size={14}/></button></div><p>{active.message}</p><div className="progress-track"><span style={{width:`${active.progress}%`}}/></div><small>{Math.round(active.progress)}% · {active.status}</small></div>}
      {plan && <div className="plan-card"><div className="plan-title"><Sparkles size={15}/><strong>Your proposed edit</strong><span>REVIEW</span></div><p>{plan.result?.summary}</p><div className="plan-cuts">{plan.result?.timeline?.clips.map((c,i)=><div key={i}><span>{String(i+1).padStart(2,"0")}</span><strong>{assets.find(a=>a.id===c.asset_id)?.name || "Clip"}</strong><code>{c.start.toFixed(2)}–{c.end.toFixed(2)}s</code></div>)}</div>{!!plan.result?.timeline?.motion_graphics?.length && <div className="plan-cuts"><strong className="muted tiny">ANIMATED OVERLAYS</strong>{plan.result.timeline.motion_graphics.map((g,i)=><div key={i}><span>{g.start.toFixed(1)}–{(g.start+g.duration).toFixed(1)}s</span><strong title={g.text}>{g.text}</strong><code>{g.template.replace("_"," ")}</code></div>)}</div>}{plan.result?.warnings?.map((w,i)=><p className="plan-warning" key={i}>{w}</p>)}<button className="primary full" onClick={approve} disabled={!!active || saving>0}><Check size={15}/>Approve & render preview</button><p className="tiny muted">Approval replaces the timeline. You can undo it.</p></div>}
      {!active && jobs[0]?.status === "failed" && <div className="job-error"><strong>That job needs attention</strong><p>{jobs[0].error}</p><small>Adjust the request or settings and try again.</small></div>}
      {!active && rendered && <div className="render-ready"><Check size={16}/><div><strong>{rendered.kind === "generate" ? "Your video is ready" : `Your ${rendered.kind} is ready`}</strong><span>{rendered.result?.actual_duration?.toFixed(1)}s · {rendered.result?.width} × {rendered.result?.height}</span><button className="text-button" onClick={()=>{setUseRender(true);seekTo(0);}}>Show rendered video</button></div></div>}
      {jobs.length>0 && <details className="job-history"><summary>Activity <span>{jobs.length}</span></summary>{jobs.slice(0,10).map(j=><div key={j.id}><span className={`job-dot ${j.status}`}/><span>{j.kind}</span><small>{j.status}</small>{j.status==="completed" && j.result?.output_url && <a href={j.result.output_url+"?download=true"} title="Download this render"><ArrowDownToLine size={13}/></a>}</div>)}</details>}
    </div><div className="prompt-area"><div className="selected-style"><Layers3 size={12}/><select aria-label="Selected editing style" value={selectedStyle} onChange={e=>setSelectedStyle(e.target.value)}><option value="">No style · follow my prompt</option>{styles.map(s=><option key={s.id} value={s.id}>{s.name}</option>)}</select><ChevronDown size={11}/></div><div className="director-tools"><button className="enhance-director" onClick={enhanceDirector} disabled={!prompt.trim() || enhancing || !!active || uploading} title="Improve your video prompt with Pine Labs AgenticOrg">{enhancing ? <LoaderCircle className="spin" size={13}/> : <WandSparkles size={13}/>}<span>{enhancing ? "Enhancing…" : "Enhance Director"}</span></button><span className="director-credit">Pine Labs · AgenticOrg</span>{previousPrompt!==null && !enhancing && <button className="text-button" onClick={()=>{setPrompt(previousPrompt);setPreviousPrompt(null);}}>Undo</button>}</div><div className="prompt-box"><textarea aria-label="AI editing instructions" disabled={enhancing} placeholder="Describe your video: the story, style, pacing and animation…" maxLength={6000} value={prompt} onChange={e=>setPrompt(e.target.value)} onKeyDown={e=>{if(e.key==="Enter" && !e.shiftKey){e.preventDefault();generateVideo();}}}/><div><span><Sparkles size={12}/>Codex</span><button className="send-button" aria-label="Generate video" onClick={generateVideo} disabled={!prompt.trim() || uploading || !!active || saving>0 || enhancing}><Sparkles size={14}/><span>Generate</span></button></div></div><p><ShieldCheck size={11}/>Runs locally with your ChatGPT account</p></div></aside>

    <section className="timeline-panel"><div className="timeline-toolbar"><div className="timeline-tools"><h2>Timeline</h2><span className="divider"/><button className="icon-button" title="Undo" onClick={undo} disabled={!history.length || saving>0}><Undo2 size={16}/></button><button className="icon-button" title="Redo" onClick={redo} disabled={!future.length || saving>0}><Redo2 size={16}/></button><span className="divider"/><button className="tool-button" onClick={split} disabled={!total}><Scissors size={15}/>Cut</button><button className="tool-button" title="Delete selected clip" onClick={()=>{commit({...timeline,clips:timeline.clips.filter((_,i)=>i!==selected)});setSelected(Math.max(0,selected-1));}} disabled={!clip}><Trash2 size={15}/>Delete</button></div><div className="timeline-tools"><span className="timeline-duration">{timeline.clips.length} clips · {total.toFixed(1)}s</span><button className="icon-button" aria-label="Zoom out timeline" onClick={()=>setZoom(z=>Math.max(20,z-15))}><ZoomOut size={15}/></button><input aria-label="Timeline zoom" type="range" min="20" max="150" value={zoom} onChange={e=>setZoom(+e.target.value)}/><button className="icon-button" aria-label="Zoom in timeline" onClick={()=>setZoom(z=>Math.min(150,z+15))}><ZoomIn size={15}/></button><button className="secondary small" disabled={!total || !!active || saving>0} onClick={()=>startJob("preview")}><Play size={13}/>Render preview</button></div></div>
      <div className="timeline-body"><div className="track-labels"><div className="ruler-label"><Clock3 size={13}/></div><div><Film size={14}/><span>Video 1</span></div><div><AudioLines size={14}/><span>Source audio</span></div></div><div className="timeline-scroll"><div className="timeline-canvas" style={{width:Math.max(900,(total+3)*zoom)}}><div className="ruler" onClick={e=>seekTo((e.clientX-e.currentTarget.getBoundingClientRect().left)/zoom)}>{Array.from({length:Math.ceil(Math.max(20,total+3)/2)},(_,i)=><span key={i} style={{left:i*2*zoom}}>{time(i*2)}</span>)}</div><div className="video-track">{timeline.clips.map((c,i)=>{const a=assets.find(a=>a.id===c.asset_id);return <button className={`timeline-clip ${selected===i?"selected":""}`} key={`${i}-${c.asset_id}`} style={{left:offsetOf(i)*zoom,width:Math.max(10,(c.end-c.start)*zoom-3)}} draggable onDragStart={e=>e.dataTransfer.setData("text/plain",String(i))} onDragOver={e=>e.preventDefault()} onDrop={e=>{e.preventDefault();const from=Number(e.dataTransfer.getData("text/plain"));if(Number.isInteger(from))moveClip(from,i);}} onClick={()=>{setSelected(i);seekTo(offsetOf(i));}} title={`${a?.name} · ${c.start.toFixed(2)}–${c.end.toFixed(2)}s. Drag to reorder.`}><span className="clip-handle"/><div className="clip-filmstrip" style={{backgroundImage:`url(${a?.thumbnail_url})`}}/><span className="clip-label"><Film size={11}/>{a?.name}</span><span className="clip-end-handle"/></button>;})}{!timeline.clips.length && <div className="empty-track"><Plus size={16}/>Add footage from your media library to start editing</div>}</div><div className="audio-track">{timeline.clips.map((c,i)=><div className="audio-clip" key={i} style={{left:offsetOf(i)*zoom,width:Math.max(10,(c.end-c.start)*zoom-3)}}><AudioLines size={15}/><span>{assets.find(a=>a.id===c.asset_id)?.metadata.has_audio ? `Source audio · ${Math.round(c.volume*100)}%` : "Silent source"}</span></div>)}</div><div className="playhead" style={{left:playhead*zoom}}><span/></div></div></div></div>
      <div className="inspector">{clip ? <><span className="inspector-label">CLIP {selected+1}</span><label>In <input aria-label="Clip start seconds" type="number" min="0" max={clip.end-.12} step="0.05" value={+clip.start.toFixed(3)} onChange={e=>{const v=+e.target.value;if(v>=0&&v<clip.end-.12)changeClip({start:v});}}/><span>s</span></label><label>Out <input aria-label="Clip end seconds" type="number" min={clip.start+.12} max={assets.find(a=>a.id===clip.asset_id)?.metadata.duration} step="0.05" value={+clip.end.toFixed(3)} onChange={e=>{const v=+e.target.value;if(v>clip.start+.12)changeClip({end:v});}}/><span>s</span></label><label>Zoom <select aria-label="Clip zoom effect" value={clip.zoom} onChange={e=>changeClip({zoom:+e.target.value})}><option value="1">100%</option><option value="1.1">110%</option><option value="1.2">120%</option><option value="1.3">130%</option></select></label><label>Volume <select aria-label="Clip audio volume" value={clip.volume} onChange={e=>changeClip({volume:+e.target.value})}><option value="0">Muted</option><option value="0.5">50%</option><option value="1">100%</option><option value="1.5">150%</option><option value="2">200%</option></select></label><button className="icon-button" title="Move clip left" onClick={()=>moveClip(selected,selected-1)} disabled={!selected}><ArrowLeft size={14}/></button><button className="icon-button" title="Move clip right" onClick={()=>moveClip(selected,selected+1)} disabled={selected===timeline.clips.length-1}><ArrowRight size={14}/></button></> : <span className="muted">Select a clip to trim, split, reorder, or adjust it.</span>}<span className="inspector-end">Non-destructive editing</span></div>
    </section>

    <footer className="statusbar"><span><span className="green-dot"/>Local workspace</span><span>ImaginePro<span className="status-separator">·</span>Originals preserved<span className="status-separator">·</span>Revision {project?.revision || 0}</span><span>MP4 / H.264</span></footer>
    {error && <div className="error-toast" role="alert"><div><strong>Something needs attention</strong><p>{error}</p></div><button className="icon-button" aria-label="Dismiss error" onClick={()=>setError("")}><X size={16}/></button></div>}
    {notice && <div className="notice-toast" role="status"><Check size={15}/>{notice}</div>}

    {modal && <div className="modal-scrim" onMouseDown={e=>{if(e.target===e.currentTarget)setModal(null);}}><section className="modal" role="dialog" aria-modal="true" aria-label={modal === "export" ? "Export video" : modal === "new" ? "New project" : modal === "transcript" ? "Import transcript" : "AI settings"}><div className="modal-heading"><h2>{modal === "export" ? "Make it ready to share." : modal === "new" ? "Start a new story." : modal === "transcript" ? "Start with your words." : "AI settings"}</h2><button className="icon-button" aria-label="Close dialog" onClick={()=>setModal(null)}><X size={18}/></button></div>
      {modal==="transcript" && <><p className="muted">Paste the script or narration you want to turn into a video.</p><textarea className="text-input transcript-editor" aria-label="Transcript text" autoFocus value={transcriptDraft} onChange={e=>setTranscriptDraft(e.target.value)} maxLength={20000} placeholder="Paste your transcript here…"/><button className="primary full" disabled={!transcriptDraft.trim() || uploading} onClick={importTranscript}>{uploading ? <LoaderCircle className="spin" size={15}/> : <FileText size={15}/>}Import transcript</button></>}
      {modal==="new" && <><label className="field-label">Project name<input className="text-input" autoFocus value={newName} onChange={e=>setNewName(e.target.value)} placeholder="Weekend in the mountains" maxLength={100}/></label><button className="primary full" disabled={!newName.trim()} onClick={async()=>{try{const p=await api<Project>("/projects",{method:"POST",body:JSON.stringify({name:newName.trim()})});await refreshProjects();await load(p.id);setModal(null);setNewName("");}catch(e){fail(e);}}}><Plus size={15}/>Create project</button></>}
      {modal==="settings" && <><div className="runtime-card"><span className="style-swatch skill"><Sparkles size={24}/></span><div><strong>Codex CLI</strong><p>{runtime?.message || "Checking account status…"}</p><span className="pill">{!runtime ? "Checking connection…" : runtime.authenticated_with_chatgpt ? "ChatGPT account connected" : "Account sign-in required"}</span></div></div><div className="settings-row"><span>Execution</span><strong>Codex · ChatGPT account</strong></div><div className="settings-row"><span>Transcription</span><strong>Faster-Whisper · local CPU</strong></div><div className="settings-row"><span>Speaker diarization</span><strong className="muted">Unavailable locally</strong></div><p className="muted">No separate LLM API key is required. Whisper downloads model weights on first use. This server is intended for your own computer.</p><div className="api-configuration"><span className="eyebrow">API CONFIGURATION</span><label className="field-label">Provider<select value={apiConfig.provider} onChange={e=>setApiConfig({...apiConfig,provider:e.target.value})}><option>OpenAI</option><option>Kiro</option><option>Custom endpoint</option></select></label><label className="field-label">API key<input className="text-input" aria-label="Provider API key" type="password" autoComplete="off" value={apiConfig.key} onChange={e=>setApiConfig({...apiConfig,key:e.target.value})}/></label><div className="api-model-fields"><label className="field-label">Model<input className="text-input" aria-label="Provider model" value={apiConfig.model} onChange={e=>setApiConfig({...apiConfig,model:e.target.value})}/></label><label className="field-label">Base URL<input className="text-input" aria-label="Provider base URL" value={apiConfig.endpoint} onChange={e=>setApiConfig({...apiConfig,endpoint:e.target.value})}/></label></div><p className="tiny muted">Active connection: Codex · ChatGPT account.</p></div><div className="api-configuration"><span className="eyebrow">ENHANCE DIRECTOR · PINE LABS AGENTICORG</span><p className="tiny muted">{directorLoading ? "Checking saved connection…" : directorConfig.key_configured ? "API key stored on this computer." : "Add your AgenticOrg API key."} Prompt enhancement runs separately from video generation.</p><label className="field-label">API base URL<input className="text-input" aria-label="AgenticOrg API base URL" value={directorConfig.base_url} onChange={e=>setDirectorConfig({...directorConfig,base_url:e.target.value})}/></label><label className="field-label">API key<input className="text-input" aria-label="AgenticOrg API key" type="password" autoComplete="off" value={directorKey} onChange={e=>setDirectorKey(e.target.value)}/></label><div className="api-model-fields"><label className="field-label">Company ID<input className="text-input" aria-label="AgenticOrg company ID" value={directorConfig.company_id} onChange={e=>setDirectorConfig({...directorConfig,company_id:e.target.value})}/></label><label className="field-label">Director agent ID<input className="text-input" aria-label="AgenticOrg director agent ID" value={directorConfig.agent_id} onChange={e=>setDirectorConfig({...directorConfig,agent_id:e.target.value})}/></label></div><p className="tiny muted">A single company is selected automatically. ImaginePro creates its own director agent when permitted; an existing director ID can be supplied.</p><button className="secondary full" onClick={saveDirectorConnection} disabled={directorSaving}>{directorSaving ? "Saving…" : "Save AgenticOrg connection"}</button></div><details className="help-details"><summary>Setup & troubleshooting</summary><p>Run <code>codex login</code> once to sign in with ChatGPT. Install FFmpeg and the Python requirements. Start the app with <code>scripts/start.ps1</code>. See <code>docs/SETUP.md</code> for full instructions.</p><p>Install manual styles in <code>.agents/skills/&lt;style&gt;/SKILL.md</code> or configure VIDEO_EDITOR_SKILL_DIRS. Reference profiles are saved separately as <code>storage/styles/reference_&lt;id&gt;/clean.md</code>.</p><p>Limits: 500 MB/file, 5 minutes/source, 3 minutes/timeline, one worker. Failed jobs can be retried from the prompt or render button.</p></details></>}
      {modal==="export" && <><p className="muted">Render the saved timeline with captions, color, graphics and audio.</p><div className="export-spec"><Clapperboard size={31}/><div><strong>MP4 · H.264</strong><span>1080p · 30 fps · AAC audio</span></div><span className="pill">{total.toFixed(1)}s</span></div><div className="export-controls"><label className="field-label">Framing<select value={timeline.aspect} onChange={e=>commit({...timeline,aspect:e.target.value as Timeline["aspect"]})}><option value="landscape">Landscape · 1920 × 1080</option><option value="portrait">Portrait · 1080 × 1920</option></select></label><label className="field-label">Color grade<select value={timeline.grade} onChange={e=>commit({...timeline,grade:e.target.value})}><option value="none">Original</option><option value="subtle">Subtle cleanup</option><option value="auto">Automatic correction</option><option value="neutral_punch">Neutral punch</option><option value="warm_cinematic">Warm cinematic</option></select></label><label className="field-label">Captions<select value={timeline.captions} onChange={e=>commit({...timeline,captions:e.target.value})}><option value="none">Off</option><option value="static">Clean subtitles</option><option value="pop">Animated pop captions</option></select></label><label className="field-label">Background music<select value={timeline.music_asset_id||""} onChange={e=>commit({...timeline,music_asset_id:e.target.value||null})}><option value="">None</option>{assets.filter(a=>a.kind==="audio").map(a=><option key={a.id} value={a.id}>{a.name}</option>)}</select></label><label className="field-label wide">Intro title<input className="text-input" value={timeline.title} maxLength={100} placeholder="Optional title · first 2.5 seconds" onChange={e=>commit({...timeline,title:e.target.value})}/></label><label className="checkbox-label"><input type="checkbox" checked={timeline.fade_out} onChange={e=>commit({...timeline,fade_out:e.target.checked})}/>Fade out at the end</label></div>{active && <p className="muted">A job is {active.status}. You can queue an export after it finishes.</p>}<button className="primary full" disabled={!!active || !total || saving>0} onClick={()=>{startJob("export");setModal(null);}}><ArrowDownToLine size={15}/>Render 1080p export</button>{["export","generate"].includes(rendered?.kind || "") && <a className="secondary full download-link" href={rendered?.result?.output_url+"?download=true"}><ArrowDownToLine size={15}/>Download finished MP4</a>}<p className="tiny muted">The export is decoded and checked for resolution, duration and stream alignment before it becomes available.</p></>}
    </section></div>}
    {styleModal && <div className="modal-scrim"><section className="modal markdown-modal" role="dialog" aria-modal="true" aria-label="Style profile"><div className="modal-heading"><div><span className="eyebrow">{styleModal.kind === "template" ? "DEFAULT TEMPLATE · READ ONLY" : styleModal.kind === "reference" ? "REFERENCE PROFILE · CLEAN.MD" : styleModal.bundled ? "INSTALLED STYLE GUIDE · READ ONLY" : "MANUAL SKILL · READ ONLY"}</span><h2>{styleModal.name}</h2></div><button className="icon-button" aria-label="Close style profile" onClick={()=>setStyleModal(null)}><X size={18}/></button></div>{styleModal.bundled && <p className="muted">This guide shapes the AI plan using ImaginePro’s supported effects.</p>}<textarea className="markdown-editor" aria-label="Style Markdown" value={markdown} readOnly={styleModal.kind!=="reference"} onChange={e=>setMarkdown(e.target.value)}/><div className="modal-actions"><button className="secondary" onClick={()=>{setSelectedStyle(styleModal.id);setStyleModal(null);setNotice("Style selected for your next AI plan");}}><Layers3 size={14}/>Use this style</button>{styleModal.kind==="reference" && <button className="primary" onClick={async()=>{try{await api(`/projects/${project!.id}/styles/${styleModal.id}`,{method:"PUT",body:JSON.stringify({markdown})});setNotice("clean.md saved");setStyleModal(null);}catch(e){fail(e);}}}><Check size={14}/>Save clean.md</button>}</div></section></div>}
  </main>;
}


