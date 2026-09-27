import { useEffect, useRef, useState } from 'react'
import { ArrowRight, ArrowUpRight, BookOpen, CalendarDays, Check, ChevronRight, FileSearch, FileText, GraduationCap, Info, Layers3, LoaderCircle, Search, ShieldCheck, Sparkles, X } from 'lucide-react'

type Passage = { notice_id: string; title: string; publication_date: string; category: string; source_filename: string; chunk_id: string; passage: string; score: number; highlights: number[][] }
type Result = Passage & { passages: Passage[] }
type Conflict = { kind: string; message: string; earlier: Passage; newer: Passage }
type SearchResponse = { query: string; found: boolean; results: Result[]; conflicts: Conflict[]; message?: string }
type Notice = { id: string; title: string; publication_date: string; content: string; category: string; source_filename: string }
const examples = ['What should I bring to the workshop?', 'What documents are required?', 'When is registration due?', 'Where is the event?', 'Who can participate?']
const date = (value: string) => new Date(value + 'T00:00:00').toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const unavailable = 'Search service is temporarily unavailable. Please try again.'
  let response: Response
  try { response = await fetch(path, init) }
  catch { throw new Error(unavailable) }
  let data
  try { data = await response.json() }
  catch { throw new Error(unavailable) }
  if (!response.ok) throw new Error(typeof data.message === 'string' ? data.message : typeof data.detail === 'string' ? data.detail : 'Search service is temporarily unavailable. Please try again.')
  return data
}

function Highlight({ evidence }: { evidence: Passage }) {
  const characters = Array.from(evidence.passage)
  const nodes = []; let cursor = 0
  for (const [start, end] of evidence.highlights) {
    nodes.push(characters.slice(cursor, start).join(''), <mark key={start}>{characters.slice(start, end).join('')}</mark>)
    cursor = end
  }
  nodes.push(characters.slice(cursor).join(''))
  return <>{nodes}</>
}

function EvidenceCard({ result, compact = false, onOpen }: { result: Result; compact?: boolean; onOpen: (id: string) => void }) {
  return <article className={'result-card' + (compact ? ' compact' : '')}>
    <div className="result-top"><span className="category"><FileText size={13}/>{result.category}</span><span className="relevance" title="A retrieval similarity score, not a probability of correctness."><span/>Relevance {Math.round(result.score * 100)}%</span></div>
    <h3>{result.title}</h3>
    <div className="date"><CalendarDays size={14}/><time dateTime={result.publication_date}>{date(result.publication_date)}</time></div>
    <div className="passages">{result.passages.map(p => <blockquote key={p.chunk_id}><Highlight evidence={p}/></blockquote>)}</div>
    <div className="result-footer"><span className="source"><FileText size={13}/>{result.notice_id} <span className="source-file">/ {result.source_filename}</span></span><button className="text-button" onClick={() => onOpen(result.notice_id)}>View full notice <ArrowUpRight size={15}/></button></div>
  </article>
}

export default function App() {
  const [query, setQuery] = useState('')
  const [data, setData] = useState<SearchResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [count, setCount] = useState<number | null>(null)
  const [notice, setNotice] = useState<Notice | null>(null)
  const [viewerLoading, setViewerLoading] = useState(false)
  const [viewerError, setViewerError] = useState('')
  const [elapsed, setElapsed] = useState(0)
  const dialog = useRef<HTMLDialogElement>(null)
  const input = useRef<HTMLInputElement>(null)
  const abort = useRef<AbortController | null>(null)
  const noticeAbort = useRef<AbortController | null>(null)
  const trigger = useRef<HTMLElement | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    request<{notice_count: number}>('/api/health', {signal: controller.signal}).then(d => setCount(d.notice_count)).catch(() => {})
    return () => { controller.abort(); abort.current?.abort(); noticeAbort.current?.abort() }
  }, [])

  async function search(value = query) {
    const trimmed = value.trim()
    if (!trimmed) { setError('Please enter a question.'); input.current?.focus(); return }
    abort.current?.abort()
    const controller = new AbortController(); abort.current = controller
    setQuery(value); setLoading(true); setError(''); setData(null)
    const start = performance.now()
    try {
      const result = await request<SearchResponse>('/api/search', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({query: trimmed}), signal: controller.signal})
      if (!controller.signal.aborted) { setData(result); setElapsed(performance.now() - start) }
    } catch (e) { if (!controller.signal.aborted) setError(e instanceof Error ? e.message : 'Search service is temporarily unavailable. Please try again.') }
    finally { if (!controller.signal.aborted) setLoading(false) }
  }

  async function openNotice(id: string) {
    trigger.current = document.activeElement as HTMLElement
    noticeAbort.current?.abort()
    const controller = new AbortController(); noticeAbort.current = controller
    setNotice(null); setViewerError(''); setViewerLoading(true); dialog.current?.showModal()
    try { setNotice(await request<Notice>('/api/notices/' + encodeURIComponent(id), {signal: controller.signal})) }
    catch (e) { if (!controller.signal.aborted) setViewerError(e instanceof Error ? e.message : 'Unable to open this notice.') }
    finally { if (!controller.signal.aborted) setViewerLoading(false) }
  }
  function closeNotice() { noticeAbort.current?.abort(); dialog.current?.close(); trigger.current?.focus() }

  return <>
    <a className="skip-link" href="#search-input">Skip to search</a>
    <header className="site-header"><div className="header-inner">
      <a className="brand" href="/" aria-label="Find That Notice home"><span className="brand-icon"><FileSearch size={23}/></span><span>find that notice<span className="brand-dot">.</span></span></a>
      <div className="header-right"><span className="campus-label"><GraduationCap size={17}/>Your campus, a little clearer</span><span className="demo-label">DEMO COLLECTION</span></div>
    </div></header>

    <main>
      <section className="hero" aria-labelledby="hero-title">
        <div className="hero-copy"><div className="eyebrow"><span className="live-dot"/> LESS SCROLLING. MORE FINDING.</div>
          <h1 id="hero-title">You remember the detail.<br/>We’ll find <span>the notice.</span></h1>
          <p className="hero-description">Ask a question. Find the notice. Verify the evidence.</p>
          <p className="hero-note">Deadlines, documents, that one thing you need to bring.<br className="desktop-break"/> Find the exact passage in your campus notices.</p>
          <div className="hero-proof"><span><Check size={14}/>Straight from the source</span><span><Check size={14}/>No guessed answers</span></div>
        </div>
        <div className="hero-art" aria-hidden="true"><div className="art-grid"/><div className="back-sheet sheet-one"/><div className="back-sheet sheet-two"/><div className="sample-sheet"><div className="sheet-head"><span className="tiny-icon"><FileText size={17}/></span><span>CAMPUS NOTICE<span>01 SEP 2026</span></span><span className="sheet-dots">•••</span></div><div className="sheet-rule"/><h3>AI Tools Workshop</h3><div className="fake-line long"/><div className="fake-line medium"/><p>Participants must bring their<br/><span>laptop, college ID card</span><br/><span>and a notebook.</span></p><div className="fake-line medium"/><div className="fake-line short"/><div className="sheet-source"><ShieldCheck size={13}/> A passage. Not a prediction.</div></div><div className="found-bubble"><span><Search size={18}/></span>Found that detail.<Check size={16}/></div></div>
      </section>

      <section className="search-panel" aria-label="Search notices">
        <div className="search-label-row"><label htmlFor="search-input">What are you looking for?</label><span><Layers3 size={14}/>{count === null ? 'Campus notice collection' : `${count} notices in your collection`}</span></div>
        <form onSubmit={event => { event.preventDefault(); void search() }} className="search-form"><Search size={23} aria-hidden="true"/><input ref={input} id="search-input" name="query" maxLength={500} value={query} onChange={e => setQuery(e.target.value)} placeholder="e.g. What should I bring to the workshop?" autoComplete="off" aria-describedby="search-hint"/><button className="search-button" type="submit" disabled={loading}>{loading ? <LoaderCircle size={18} className="spin"/> : <Search size={18}/>}<span>{loading ? 'Searching…' : 'Find the notice'}</span><ArrowRight size={17}/></button></form>
        <div className="examples" id="search-hint"><span>Try asking</span>{examples.map(example => <button key={example} onClick={() => void search(example)} disabled={loading}>{example}<ArrowUpRight size={12}/></button>)}</div>
        <div className="search-footnote"><ShieldCheck size={13}/> Searches only this notice collection. Every result links back to its source.</div>
      </section>

      <section className="results-section" aria-live="polite" aria-busy={loading}>
        {error && <div className="state-box error" role="alert"><Info size={24}/><h2>Let’s try that again</h2><p>{error}</p><button className="text-button" onClick={() => void search()}>Retry search <ArrowRight size={15}/></button></div>}
        {loading && <div className="state-box"><LoaderCircle className="spin" size={26}/><h2>Finding the supporting passages…</h2><p>Looking through your campus notice collection.</p></div>}
        {data && !data.found && <div className="state-box"><span className="state-icon"><FileSearch size={27}/></span><h2>{data.message === 'No notices are currently available.' ? data.message : 'No matching information found.'}</h2><p>We couldn’t find supporting information for this question in the uploaded notices.</p><span>Try asking about registration, documents, deadlines or workshops.</span></div>}
        {data?.found && <>
          <div className="section-heading"><div><div className="eyebrow small">HERE’S THE EVIDENCE</div><h2>Notices that match your question<span className="count-badge">{data.results.length}</span></h2></div><span className="result-timing">Found in {(elapsed / 1000).toFixed(2)}s</span></div>
          {data.conflicts.map(conflict => <section className="conflict" key={conflict.newer.notice_id + conflict.earlier.notice_id}><div className="conflict-title"><Info size={21}/><div><h3>{conflict.kind === 'possible_conflict' ? 'Potentially conflicting information' : 'Possible revised information'}</h3><p>{conflict.message}</p></div></div><div className="conflict-grid">{(['newer', 'earlier'] as const).map(key => <div key={key}><div className="version-label">{key === 'newer' ? 'NEWER NOTICE' : 'EARLIER NOTICE'}</div><EvidenceCard compact onOpen={openNotice} result={{...conflict[key], passages: [conflict[key]]}}/></div>)}</div></section>)}
          <div className="results-list">{data.results.map(result => <EvidenceCard result={result} key={result.notice_id} onOpen={openNotice}/>)}</div>
          <p className="results-note"><Info size={13}/>Relevance measures the search match, not certainty. Check the full notice for context.</p>
        </>}
        {!data && !loading && !error && <div className="ready-state"><span className="ready-icon"><BookOpen size={23}/></span><div><h2>The answer is already in a notice.</h2><p>Ask in your own words. We’ll help you get back to it.</p></div><span className="ready-arrow"><ArrowRight size={23}/></span></div>}
      </section>

      <section className="how-it-works" aria-labelledby="how-title"><div className="how-intro"><div className="eyebrow small">A SHORTCUT TO THE SOURCE</div><h2 id="how-title">A little search.<br/>A lot more clarity.</h2><p>Three simple steps.<br/>No conversation required.</p></div><div className="steps"><div className="step"><span className="step-icon"><Search size={22}/></span><span className="step-number">01</span><h3>Ask naturally</h3><p>Use the words you remember.<br/>Semantic search finds the meaning.</p></div><ChevronRight className="step-chevron" size={18}/><div className="step"><span className="step-icon"><FileText size={22}/></span><span className="step-number">02</span><h3>Find the passage</h3><p>Read the exact words from the notice,<br/>with its title and publication date.</p></div><ChevronRight className="step-chevron" size={18}/><div className="step"><span className="step-icon"><ShieldCheck size={22}/></span><span className="step-number">03</span><h3>Verify the evidence</h3><p>Open the complete notice.<br/>See earlier versions when revised.</p></div></div></section>
      <div className="collection-note"><Sparkles size={15}/><p>A small collection. A useful starting point. <span>This demo uses 10 synthetic Indian campus notices.</span></p></div>
    </main>

    <footer><span className="footer-brand"><FileSearch size={17}/>find that notice.</span><span>Built around evidence. Made for students.</span><span className="footer-tag"><span className="live-dot"/>Ask. Find. Verify.</span></footer>

    <dialog ref={dialog} className="notice-dialog" aria-labelledby="notice-title" onCancel={e => { e.preventDefault(); closeNotice() }} onClick={e => { if (e.target === dialog.current) closeNotice() }}><div className="dialog-inner"><div className="dialog-top"><span><FileText size={16}/>FULL SOURCE NOTICE</span><button className="icon-button" aria-label="Close full notice" onClick={closeNotice}><X size={21}/></button></div><h2 id="notice-title">{notice?.title || (viewerLoading ? 'Opening notice…' : 'Notice unavailable')}</h2>{viewerLoading && <LoaderCircle className="spin"/>}{viewerError && <p role="alert">{viewerError}</p>}{notice && <><div className="dialog-meta"><span className="category">{notice.category}</span><span className="date"><CalendarDays size={14}/>{date(notice.publication_date)}</span></div><div className="notice-content">{notice.content.split(/\n\s*\n/).map((p,i) => <p key={i}>{p}</p>)}</div><div className="dialog-source"><ShieldCheck size={16}/><span>{notice.id} · {notice.source_filename}<small>Original text from the uploaded collection. Synthetic demo notice.</small></span></div></>}</div></dialog>
  </>
}
