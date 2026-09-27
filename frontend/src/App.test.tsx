import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from './App'

const passage = {notice_id:'notice_01',title:'AI Tools Workshop for Students',publication_date:'2026-09-01',category:'Workshop',source_filename:'Notice_01.txt',chunk_id:'notice_01:1',passage:'Participants must bring their laptop, college ID card and a notebook.',score:0.76,highlights:[[29,35]]}
const notice = {id:'notice_01',title:passage.title,publication_date:passage.publication_date,category:'Workshop',source_filename:'Notice_01.txt',content:passage.passage + '\n\nWorkshop registration closes on 15 September 2026.'}
const result = {query:'What should I bring to the workshop?',found:true,results:[{...passage,passages:[passage]}],conflicts:[]}
let searchResult: object
let failed: boolean

beforeEach(() => {
  searchResult = result; failed = false
  vi.stubGlobal('fetch',vi.fn(async (path: string) => {
    if (path === '/api/health') return new Response(JSON.stringify({notice_count:10}))
    if (path.startsWith('/api/notices/')) return new Response(JSON.stringify(notice))
    if (failed) return new Response('upstream proxy failure',{status:502})
    return new Response(JSON.stringify(searchResult))
  }))
})
afterEach(() => vi.unstubAllGlobals())

describe('Evidence search', () => {
  it('renders the collection, labels, and five example questions', async () => {
    render(<App/> )
    expect(await screen.findByText('10 notices in your collection')).toBeVisible()
    expect(screen.getByRole('textbox',{name:'What are you looking for?'})).toBeVisible()
    expect(screen.getAllByRole('button').length).toBe(6)
  })

  it('runs an example and opens the full source notice', async () => {
    const user = userEvent.setup(); render(<App/> )
    await user.click(screen.getByRole('button',{name:/What should I bring/}))
    expect(await screen.findByRole('heading',{name:passage.title})).toBeVisible()
    expect(screen.getByRole('blockquote')).toHaveTextContent(passage.passage)
    await user.click(screen.getByRole('button',{name:'View full notice'}))
    const dialog = screen.getByRole('dialog')
    expect(await within(dialog).findByText(/Workshop registration closes/)).toBeVisible()
    await user.click(within(dialog).getByRole('button',{name:'Close full notice'}))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.getByRole('button',{name:'View full notice'})).toHaveFocus()
  })

  it('submits with the keyboard and rejects an empty question', async () => {
    const user = userEvent.setup(); render(<App/> )
    const input = screen.getByRole('textbox')
    await user.click(input); await user.keyboard('{Enter}')
    expect(await screen.findByText('Please enter a question.')).toBeVisible()
    await user.type(input,'What should I bring to the workshop?{Enter}')
    expect(await screen.findByRole('heading',{name:passage.title})).toBeVisible()
  })

  it('shows the unsupported state without fabricating an answer', async () => {
    searchResult = {query:'weather',found:false,results:[],conflicts:[],message:'No matching information found.'}
    const user = userEvent.setup(); render(<App/> )
    await user.type(screen.getByRole('textbox'),'weather{Enter}')
    expect(await screen.findByRole('heading',{name:'No matching information found.'})).toBeVisible()
    expect(screen.queryByRole('button',{name:'View full notice'})).not.toBeInTheDocument()
  })

  it('keeps both passages visible in a revision warning', async () => {
    const newer = {...passage,notice_id:'notice_10',title:'Workshop deadline update',publication_date:'2026-09-12',passage:'Registration deadline extended to 20 September 2026.',highlights:[]}
    searchResult = {...result,conflicts:[{kind:'explicit_revision',message:'Both passages are shown for verification.',earlier:passage,newer}]}
    const user = userEvent.setup(); render(<App/> )
    await user.type(screen.getByRole('textbox'),'registration deadline{Enter}')
    expect(await screen.findByText('Possible revised information')).toBeVisible()
    expect(screen.getByText('NEWER NOTICE')).toBeVisible()
    expect(screen.getByText('EARLIER NOTICE')).toBeVisible()
    expect(screen.getByText(newer.passage)).toBeVisible()
  })

  it('handles non-JSON server failure and allows retry', async () => {
    failed = true
    const user = userEvent.setup(); render(<App/> )
    await user.type(screen.getByRole('textbox'),'workshop{Enter}')
    expect(await screen.findByText('Search service is temporarily unavailable. Please try again.')).toBeVisible()
    expect(screen.queryByText('upstream proxy failure')).not.toBeInTheDocument()
    failed = false
    await user.click(screen.getByRole('button',{name:'Retry search'}))
    expect(await screen.findByRole('heading',{name:passage.title})).toBeVisible()
    await waitFor(() => expect(screen.queryByRole('alert')).not.toBeInTheDocument())
  })
})
