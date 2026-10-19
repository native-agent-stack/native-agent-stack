export const meta = {
  name: 'layer-verdict-lane',
  description: 'Review a stripped layer-packet wave in sequential chains: an Opus proposer, two refuter lenses, and at most one revision/recheck per packet. Final requires complete lens returns, no refutation or remaining major/blocking finding, and explicit evidence-backed closure of prior findings by their originating lenses. A required unsuccessful revision returns unknown, preserving both rounds, errors and stop cause. The script writes nothing and never promotes a candidate; pilot one-packet admission, native identity, global capacity and terminal/usage closure remain caller gates.',
  whenToUse: 'After tools/sota-convergence/lane_packets.py wrote the packets: args = {repo: "<source view>", packets: [{catalog, layer_id, path, sha256}] (nonempty, all valid, unique catalog/layer identities; docs mode is rejected), prompt: "<lane-prompt.md text with {PACKET_PATH} {REPO_ROOT} {LANE} placeholders>", model?: {name: "opus", effort: "max"} (optional; a different value is logged and returned as caller_model, never applied, because every agent() call binds that literal), launch?: {repo, repo_tree_sha256, ...} (optional; returned unchanged as launch so the collector can bind the result to the export it was launched on)}. A pilot must separately admit exactly one packet before dispatch; this reusable wave API does not implement that gate.',
  phases: [
    { title: 'Propose', detail: 'blind-lane-reviewer per packet, Opus max, Read/Glob/Grep only, no skills or project instructions', model: 'opus' },
    { title: 'Refute', detail: 'evidence lens + challenger lens per proposal, blind-lane-reviewer, Opus max', model: 'opus' },
    { title: 'Revise', detail: 'one revision when any lens refutes or reports a major finding, Opus max', model: 'opus' },
    { title: 'Re-check', detail: 'evidence lens + challenger lens re-check the revision, blind-lane-reviewer, Opus max', model: 'opus' },
  ],
}
const a = args && typeof args === 'object' ? args : {}
const issues = []
const nonblank = (v) => typeof v === 'string' && v.trim().length > 0
const REPO = nonblank(a.repo) ? a.repo : '.'
const PROMPT = nonblank(a.prompt) ? a.prompt : 'You are the {LANE} lane. Read the packet at {PACKET_PATH} under {REPO_ROOT} and return the schema object.'
const validPacket = (p) => p && typeof p === 'object' && !Array.isArray(p) && ['foundation', 'us-equities'].includes(p.catalog) && nonblank(p.layer_id) && nonblank(p.path) && typeof p.sha256 === 'string' && /^[0-9a-f]{64}$/.test(p.sha256)
// Validate the complete wave without filtering. Pilot cardinality, packet bytes
// and source-view closure still need the external caller's admission checks.
const packets = Array.isArray(a.packets) ? a.packets : []
if (!packets.length || !packets.every(validPacket)) issues.push('packets must be a nonempty array of valid {catalog, layer_id, path, sha256} entries')
else if (new Set(packets.map((p) => `${p.catalog}/${p.layer_id}`)).size !== packets.length) issues.push('packet catalog/layer identities must be unique')
if (a.docs !== undefined) issues.push('docs mode is not admitted; supply packets')
if (!nonblank(a.repo)) issues.push('repo must name the admitted source view')
// Every admitted run names its prompt. The collector binds the echoed prompt to
// the registered lane-prompt.md (catalog review of #145, M1).
if (Array.isArray(a.packets) && a.packets.length && !nonblank(a.prompt)) issues.push('prompt must be the lane-prompt.md text when packets are given')
// Every agent() call below binds the literal model 'opus' / effort 'max' (the contract suite requires inline alias
// literals), so the recorded model is that same literal and args.model cannot re-route the lane.
const MODEL = { name: 'opus', effort: 'max' }
// A caller-supplied model is not applied (it cannot be); it is logged and returned as caller_model so the record stays truthful.
const CALLER_MODEL = a.model !== undefined && !(a.model && typeof a.model === 'object' && a.model.name === MODEL.name && a.model.effort === MODEL.effort) ? a.model : null
// A caller-supplied launch identity is echoed unchanged (catalog Codex review of #145): the collector requires it
// to name the export and evidence-tree digest it records, so a result from another launch cannot be relabelled.
const LAUNCH = a.launch && typeof a.launch === 'object' && !Array.isArray(a.launch) ? a.launch : null
// The echoed identity must name the repository the agents actually read (Codex review of #42).
if (a.launch !== undefined && (!LAUNCH || LAUNCH.repo !== REPO)) issues.push('launch must be an object whose repo equals repo')
if (CALLER_MODEL) log('args.model ' + JSON.stringify(CALLER_MODEL) + ' is not applied: every agent() call binds ' + JSON.stringify(MODEL))
if (issues.length) { for (const i of issues) log('argument issue: ' + i); return { status: 'incomplete', stop_cause: 'argument_rejected', argument_issues: issues } }
const PACKET = [
  'Worker packet contract: bounded objective, only the listed sources, no writes except what an acceptance command named in your task itself produces, return only the schema.',
  'Cite every claim with file path and section/line or the exact command. Copy numbers exactly. Never print credential or env values. Never claim token savings.',
  'Distinguish documented-as-done from observed-now. Preserve failures, empty results and unknowns as such; do not restate them as passes.',
  'Context lanes, limited to the tools your role has (load a deferred one with ToolSearch "select:<tool name>" before calling it; skip lanes your role lacks): focused rg/Read or Serena for known symbols/references, SocratiCode for conceptual code, jCodeMunch for indexed retrieval, scoped qmd search for Markdown, ai-memory query for prior decisions, Context Mode ctx_execute for large outputs; one lane per artifact, and open the original source before judging retrieved text.',
].join(' ')
// The shared PACKET above is byte-identical across saved workflows (contract suite). This lane adds a blind
// rule after it. Every agent here is blind-lane-reviewer: Read/Glob/Grep only, no preloaded skill (a skill can be
// a candidate, as typesafe-ai is in instructions-skills) and no project instructions (omitClaudeMd; agent-lab's
// AGENTS.md names incumbent selections). Memory stores, code indexes, git history and other checkouts can carry
// the verdict the lane must reach on the retained evidence alone.
const BLIND = 'Blind lane: this rule overrides the context lanes above. Use only Read, Glob and Grep on the packet and on files under the repository root. Do not query memory stores, code indexes, git history or the web, and do not open another checkout or work directory.'
const ALT = { type: 'object', properties: { key: { type: ['string', 'null'] }, name: { type: 'string' }, repository: { type: 'string', pattern: '^https://[^ ;,]+$' }, disposition: { type: 'string', enum: ['selected', 'observed_failure', 'measured_tradeoff', 'overlap', 'out_of_scope', 'unqualified', 'conditional'] }, why_not_default: { type: 'string' }, evidence_class: { type: 'string', enum: ['native_proven', 'local_integration', 'synthetic', 'source_review', 'measured_comparison'] }, evidence_refs: { type: 'array', items: { type: 'string' } } }, required: ['key', 'name', 'repository', 'disposition', 'why_not_default', 'evidence_class', 'evidence_refs'] }
const LANE_RETURN = { type: 'object', properties: {
  schema_version: { type: 'integer', enum: [1] }, lane: { type: 'string', enum: ['claude'] }, catalog: { type: 'string', enum: ['foundation', 'us-equities'] }, layer_id: { type: 'string' }, packet_sha256: { type: 'string' },
  model: { type: 'object', properties: { name: { type: 'string' }, effort: { type: 'string' } }, required: ['name', 'effort'] },
  winner_keys: { type: 'array', items: { type: 'string' }, minItems: 1, maxItems: 3 },
  why_selected: { type: 'string' }, winner_evidence_class: { type: 'string', enum: ['native_proven', 'local_integration', 'synthetic', 'source_review', 'measured_comparison'] }, winner_evidence_refs: { type: 'array', items: { type: 'string' } },
  alternatives: { type: 'array', items: ALT, minItems: 1 },
  challenger_preferred: { type: ['object', 'null'], properties: { key: { type: ['string', 'null'] }, name: { type: 'string' }, repository: { type: 'string', pattern: '^https://[^ ;,]+$' }, why: { type: 'string' }, required_comparison: { type: 'string' } }, required: ['key', 'name', 'repository', 'why', 'required_comparison'] },
  overturn_when: { type: 'string' }, overturn_protocol: { type: 'object', properties: { fixture_paths: { type: 'array', items: { type: 'string' } }, metric: { type: 'string' }, arms: { type: 'array', items: { type: 'string' } } }, required: ['fixture_paths', 'metric', 'arms'] },
  open_gaps: { type: 'array', items: { type: 'string' } }, sources_read: { type: 'array', items: { type: 'string' } }, limits: { type: 'array', items: { type: 'string' } } },
  required: ['schema_version', 'lane', 'catalog', 'layer_id', 'packet_sha256', 'model', 'winner_keys', 'why_selected', 'winner_evidence_class', 'winner_evidence_refs', 'alternatives', 'challenger_preferred', 'overturn_when', 'overturn_protocol', 'open_gaps', 'sources_read', 'limits'] }
const RESOLUTION = { type: 'object', properties: { finding_id: { type: 'string' }, disposition: { type: 'string', enum: ['resolved', 'unresolved'] }, evidence: { type: 'string' } }, required: ['finding_id', 'disposition', 'evidence'] }
const VOTE = { type: 'object', properties: { refuted: { type: 'boolean' }, reason: { type: 'string' }, findings: { type: 'array', items: { type: 'object', properties: { claim: { type: 'string' }, evidence: { type: 'string' }, severity: { type: 'string', enum: ['blocking', 'major', 'minor'] } }, required: ['claim', 'evidence', 'severity'] } }, paths_checked: { type: 'array', items: { type: 'string' } }, resolutions: { type: 'array', items: RESOLUTION } }, required: ['refuted', 'reason', 'findings', 'paths_checked', 'resolutions'] }
const fill = (p) => PROMPT.split('{PACKET_PATH}').join(p.path).split('{REPO_ROOT}').join(REPO).split('{LANE}').join('claude')
const fixed = (p) => `\nFixed values you must copy exactly: schema_version 1, lane "claude", catalog "${p.catalog}", layer_id "${p.layer_id}", packet_sha256 "${p.sha256}", model {"name": "${MODEL.name}", "effort": "${MODEL.effort}"}. Read files only under ${REPO}; you cannot run commands, so verify a path exists by opening it. winner_keys, alternatives[].key and challenger_preferred.key are the packet's candidate keys (c1, c2, ...).`
const lensPrompt = (p, proposal, lens) => PACKET + '\n' + BLIND + '\n' + (lens === 'evidence'
  ? `Evidence lens. Try to refute this layer-verdict proposal for packet ${p.path} (repository root ${REPO}): ${JSON.stringify(proposal)}. Open every path in winner_evidence_refs, alternatives[].evidence_refs and sources_read; a path that does not exist or does not support the claim made about it is a blocking finding. Check that every packet candidate with adopted == true that is not a winner appears in alternatives (missing one is blocking), that every winner key is adopted (else blocking), that why_selected reports an observed result rather than a project claim, that overturn_when names a fixtures/, blueprints/ or tests/ path or a python3/node command that exists or is runnable, and that no number or result is stated without a cited path. refuted = true if any blocking finding; reason is one sentence naming the deciding finding or why none blocks. Do not edit anything.`
  : `Challenger lens. Try to refute this layer-verdict proposal for packet ${p.path} (repository root ${REPO}): ${JSON.stringify(proposal)}. Read the packet's requirement and the evidence_refs of the strongest non-winner candidate(s), adopted or not. Argue that one of them satisfies the requirement at least as well as the winner set on the retained evidence. refuted = true only when the cited evidence shows that (name the paths), or when a stated why_not_default is contradicted by its own evidence; a stronger candidate that is not adopted must have been recorded in challenger_preferred (its absence is a major finding, not a refutation of the winner); reason is one sentence naming the deciding evidence. Do not edit anything.`)
// Packet chains run sequentially; only their two refuter lenses run concurrently.
const LENSES = ['evidence', 'challenger']
const stageIdentity = (label) => {
  if (label.startsWith('parallel:')) {
    const round = label.split(':')[1]
    return { label, round, lens: null, role: round + ':parallel' }
  }
  const round = label.startsWith('propose:revise:') || label.startsWith('refute:recheck:') ? 'revision' : 'proposal'
  const lens = label.match(/^refute:(?:recheck:)?(evidence|challenger):/)?.[1] || null
  return { label, round, lens, role: round + (lens ? ':' + lens : '') }
}
const started = (stages, label) => stages.push({ ...stageIdentity(label), status: 'running' })
const failed = (stages, label, error) => {
  const record = stages.find((s) => s.label === label)
  const failure = { ...stageIdentity(label), status: 'error', error: { name: error && typeof error.name === 'string' ? error.name : 'Error', message: error && typeof error.message === 'string' ? error.message : String(error) } }
  if (record) Object.assign(record, failure)
  else stages.push(failure)
  return null
}
const validSubject = (v) => v && typeof v === 'object' && !Array.isArray(v)
const validVote = (v) => validSubject(v) && typeof v.refuted === 'boolean' && nonblank(v.reason)
  && Array.isArray(v.findings) && v.findings.every((f) => validSubject(f) && ['blocking', 'major', 'minor'].includes(f.severity) && nonblank(f.claim) && nonblank(f.evidence))
  && Array.isArray(v.paths_checked) && v.paths_checked.every(nonblank)
  && Array.isArray(v.resolutions) && v.resolutions.every((r) => validSubject(r) && nonblank(r.finding_id) && ['resolved', 'unresolved'].includes(r.disposition) && nonblank(r.evidence))
const outcome = (stages, label, value, valid) => {
  if (stages.some((s) => s.label === label && s.status === 'error')) return null
  const status = value == null ? 'null' : valid(value) ? 'returned' : 'invalid'
  const record = stages.find((s) => s.label === label)
  const result = { ...stageIdentity(label), status, ...(status === 'invalid' ? { returned: value } : {}) }
  if (record) Object.assign(record, result)
  else stages.push(result)
  return status === 'returned' ? value : null
}
// Both lens votes are required on every checked object. A vote that is missing, null, thrown or
// lacks a boolean `refuted` is kept as refuted: null, so a lost refuter reads as unknown, never as unrefuted.
const refute = async (p, subject, round, prior, stages) => {
  const labels = LENSES.map((lens) => (round === 'revision' ? 'refute:recheck:' : 'refute:') + `${lens}:${p.catalog}/${p.layer_id}`)
  const observed = []
  const groupLabel = `parallel:${round}:${p.catalog}/${p.layer_id}`
  const got = await Promise.resolve().then(() => parallel(LENSES.map((lens, i) => async () => {
    started(stages, labels[i])
    const raw = await Promise.resolve().then(() => agent(lensPrompt(p, subject, lens) + '\nRecheck obligations for this lens: ' + JSON.stringify(prior.filter((f) => f.lens === lens)) + '. Return one resolutions entry for each finding_id, with disposition resolved or unresolved and cited evidence from the revision. Do not mark a finding resolved merely because the revision omits it. With no obligations, return resolutions: [].', { label: labels[i], phase: round === 'revision' ? 'Re-check' : 'Refute', agentType: 'blind-lane-reviewer', model: 'opus', effort: 'max', schema: VOTE })).catch((error) => failed(stages, labels[i], error))
    const v = outcome(stages, labels[i], raw, validVote)
    observed[i] = v ? { ...v, lens, round } : { lens, round, refuted: null, reason: raw == null ? 'no vote returned; see stage_results' : 'invalid vote returned; see stage_results', findings: Array.isArray(raw && raw.findings) ? raw.findings : [], paths_checked: [] }
    return observed[i]
  }))).catch((error) => failed(stages, groupLabel, error))
  if ((!Array.isArray(got) || got.length !== LENSES.length || got.some((v) => v == null) || LENSES.some((_, i) => !observed[i])) && !stages.some((s) => s.label === groupLabel)) failed(stages, groupLabel, new Error('parallel returned an incomplete array or before every lens outcome was observed'))
  return LENSES.map((lens, i) => observed[i] || { lens, round, refuted: null, reason: 'no completed vote; see stage_results', findings: [], paths_checked: [] })
}
// Round status from the two votes: any refutation decides; otherwise a missing vote leaves it unknown.
const roundStatus = (votes) => votes.some((v) => v.refuted === true) ? 'refuted' : votes.length === LENSES.length && votes.every((v) => v.refuted === false) ? 'unrefuted' : 'unknown'
const completeVotes = (votes) => votes.length === LENSES.length && votes.every((v) => typeof v.refuted === 'boolean')
const completeRound = (votes, stages, round) => completeVotes(votes) && !stages.some((s) => s.round === round && s.status !== 'returned')
// Finding identities survive the revision. A refutation without a structured major
// still needs an explicit disposition of its reason by the originating lens.
const requiredFindings = (votes) => votes.flatMap((v) => {
  const findings = (v.findings || []).map((f, i) => f && typeof f === 'object' ? { ...f, finding_id: `${v.round}:${v.lens}:${i}`, lens: v.lens } : null).filter((f) => f && f.severity !== 'minor')
  return findings.length || !v.refuted ? findings : [{ finding_id: `${v.round}:${v.lens}:refutation`, lens: v.lens, claim: v.reason, evidence: v.reason, severity: 'blocking' }]
})
const findingsClosed = (prior, votes) => votes.every((v) => {
  const own = prior.filter((f) => f.lens === v.lens)
  const resolutions = v.resolutions
  return Array.isArray(resolutions) && resolutions.length === own.length && own.every((f) => {
    const got = resolutions.filter((r) => r && r.finding_id === f.finding_id)
    return got.length === 1 && got[0].disposition === 'resolved' && nonblank(got[0].evidence)
  })
})
const summary = (votes) => votes.map((v) => {
  const blocking = (v.findings || []).filter((f) => f && f.severity !== 'minor').map((f) => f.claim).filter(nonblank)
  return { lens: v.lens, round: v.round, refuted: v.refuted, reason: nonblank(v.reason) ? v.reason : blocking.length ? blocking.join('; ') : v.refuted === null ? 'no vote returned' : 'no reason given' }
})
// Each layer echoes the packet path its agents read (catalog Codex review of #145): the collector requires it to be
// the work dir's packet with that sha256, so edited args cannot pass a different packet under the same hash.
const layer = (p, proposal, votes, revised, revisionVotes, final, finalSource, status, stages, stopCause = null) => {
  const expected = ['proposal', ...LENSES.map((l) => 'proposal:' + l)]
  if (completeRound(votes, stages, 'proposal') && requiredFindings(votes).length) expected.push('revision', ...LENSES.map((l) => 'revision:' + l))
  return {
  catalog: p.catalog, layer_id: p.layer_id, packet_sha256: p.sha256, packet_path: p.path, proposal, votes, revised, revision_votes: revisionVotes, final, final_source: finalSource,
  required_findings: requiredFindings(votes), stage_results: stages, stop_cause: stopCause,
  expected_roles: expected, returned_roles: stages.filter((s) => s.status === 'returned').map((s) => s.role), not_started_roles: expected.filter((role) => !stages.some((s) => s.role === role)),
  refutation: { status, final_source: finalSource, proposal_status: votes.length ? roundStatus(votes) : null, revision_status: revisionVotes.length ? roundStatus(revisionVotes) : null, votes: summary([...votes, ...revisionVotes]) },
  }
}
const subjectStop = (stages, role) => role + '_' + (stages.find((s) => s.role === role)?.status === 'error' ? 'failed' : stages.find((s) => s.role === role)?.status === 'invalid' ? 'invalid' : 'missing')
const chain = async (p) => {
  const stages = []
  const proposalLabel = `propose:${p.catalog}/${p.layer_id}`
  started(stages, proposalLabel)
  const rawProposal = await Promise.resolve().then(() => agent(PACKET + '\n' + BLIND + '\n' + fill(p) + fixed(p), { label: proposalLabel, phase: 'Propose', agentType: 'blind-lane-reviewer', model: 'opus', effort: 'max', schema: LANE_RETURN })).catch((error) => failed(stages, proposalLabel, error))
  const proposal = outcome(stages, proposalLabel, rawProposal, validSubject)
  if (!proposal) return layer(p, null, [], null, [], null, null, 'unknown', stages, subjectStop(stages, 'proposal'))
  const votes = await refute(p, proposal, 'proposal', [], stages)
  const first = roundStatus(votes)
  const majors = requiredFindings(votes)
  if (!completeRound(votes, stages, 'proposal')) return layer(p, proposal, votes, null, [], null, null, 'unknown', stages, 'proposal_votes_incomplete')
  // No refutation and no major finding: the proposal is final only when both votes returned.
  if (first !== 'refuted' && !majors.length) return layer(p, proposal, votes, null, [], proposal, 'proposal', first, stages)
  const revisionLabel = `propose:revise:${p.catalog}/${p.layer_id}`
  started(stages, revisionLabel)
  const rawRevision = await Promise.resolve().then(() => agent(PACKET + '\n' + BLIND + '\n' + fill(p) + fixed(p) + `\nThis is the revision round. Your earlier proposal was: ${JSON.stringify(proposal)}. Independent refuters found: ${JSON.stringify(votes)}. Resolve every blocking and major finding by re-reading the cited evidence; keep what the evidence supports, drop or correct what it does not, and add what was missing. Return the complete revised object.`, { label: revisionLabel, phase: 'Revise', agentType: 'blind-lane-reviewer', model: 'opus', effort: 'max', schema: LANE_RETURN })).catch((error) => failed(stages, revisionLabel, error))
  const revised = outcome(stages, revisionLabel, rawRevision, validSubject)
  if (!revised) return layer(p, proposal, votes, null, [], null, null, 'unknown', stages, subjectStop(stages, 'revision'))
  const revisionVotes = await refute(p, revised, 'revision', majors, stages)
  const second = revised ? roundStatus(revisionVotes) : null
  if (completeRound(revisionVotes, stages, 'revision') && second === 'unrefuted' && !requiredFindings(revisionVotes).length && findingsClosed(majors, revisionVotes)) return layer(p, proposal, votes, revised, revisionVotes, revised, 'revision', 'unrefuted', stages)
  // A required revision that failed, stayed refuted/unknown or left a finding open
  // cannot restore the original proposal. Keep both rounds and refuse judgment.
  const stopCause = !completeRound(revisionVotes, stages, 'revision') ? 'revision_votes_incomplete' : second === 'refuted' ? 'revision_refuted' : requiredFindings(revisionVotes).length ? 'revision_findings_unresolved' : 'prior_findings_unresolved'
  return layer(p, proposal, votes, revised, revisionVotes, null, null, 'unknown', stages, stopCause)
}
// Preserve the args-builder/collector wave contract without an outer parallel
// group that could lose earlier results or run multiple chains concurrently.
const results = []
let waveInterrupted = false
for (const p of packets) {
  const result = await chain(p)
  results.push(result)
  // A failed/early group return does not prove its started children stopped.
  // Preserve that partial chain and never add another packet's producers.
  if (result.stage_results.some((s) => s.role.endsWith(':parallel') && s.status === 'error')) {
    waveInterrupted = true
    break
  }
}
const out = results.filter(Boolean)
const lost = packets.filter((p) => !out.find((r) => r.catalog === p.catalog && r.layer_id === p.layer_id)).map((p) => `${p.catalog}/${p.layer_id}`)
const status = lost.length || out.some((r) => !r.final) ? 'incomplete' : 'complete'
const stopCause = lost.length ? waveInterrupted ? 'wave_orchestration_incomplete' : 'layer_result_missing' : out.find((r) => r.stop_cause)?.stop_cause || null
const count = (st) => out.filter((r) => r.refutation && r.refutation.status === st).length
const roundRefutations = { proposal: out.filter((r) => r.refutation.proposal_status === 'refuted').length, revision: out.filter((r) => r.refutation.revision_status === 'refuted').length }
log(`layers: ${out.length} returned, ${out.filter((r) => r.revised).length} revised, ${out.filter((r) => r.final).length} sealed (${out.filter((r) => r.final_source === 'revision').length} from a revision), ${count('unknown')} unknown (${out.filter((r) => !r.proposal).length} without a proposal), ${roundRefutations.proposal} proposal rounds and ${roundRefutations.revision} revision rounds refuted, ${lost.length} lost`)
return { lane: 'claude', launch: LAUNCH, prompt: PROMPT, status, stop_cause: stopCause, refutation_counts: { unrefuted: count('unrefuted'), refuted: count('refuted'), unknown: count('unknown') }, round_refutation_counts: roundRefutations, model: MODEL, caller_model: CALLER_MODEL, model_note: 'model is the literal alias/effort bound by every agent() call in this lane, not an observed identity; bind resolved child models/efforts and native attempts/usage to this run separately', layers: out, lost, not_started_packets: waveInterrupted ? lost : [] }
