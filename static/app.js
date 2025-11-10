;(function(){
  const q = (s, el=document) => el.querySelector(s)
  const qa = (s, el=document) => Array.from(el.querySelectorAll(s))

  // Elements
  const cardsEl = q('#cards')
  const emptyEl = q('#empty')
  const metaCountsEl = q('#metaCounts')

  const sidebarList = q('#categoryList')
  const mobileList  = q('#categoryListMobile')
  const catToggle   = q('#catToggle')
  const catDrawer   = q('#catDrawer')
  const drawerClose = q('#drawerClose')

  const searchSidebar = q('#searchInput')
  const searchTop     = q('#searchTop')

  // State
  let allCards = []
  let categories = []
  let activeCategory = null
  let searchTerm = ''

  // UX helpers
  function openDrawer(){ catDrawer.classList.add('open'); catDrawer.setAttribute('aria-hidden','false') }
  function closeDrawer(){ catDrawer.classList.remove('open'); catDrawer.setAttribute('aria-hidden','true') }

  catToggle.addEventListener('click', openDrawer)
  drawerClose.addEventListener('click', closeDrawer)
  catDrawer.addEventListener('click', (e) => {
    if(e.target === catDrawer){ closeDrawer() }
  })

  ;[searchSidebar, searchTop].forEach(inp => {
    if(!inp) return
    inp.addEventListener('input', (e) => {
      searchTerm = String(e.target.value || '').trim().toLowerCase()
      render()
    })
  })

  function categoryButton(cat){
    const btn = document.createElement('button')
    btn.className = 'category' + (activeCategory === cat ? ' active' : '')
    btn.type = 'button'
    btn.innerHTML = `
      <div>${cat || 'Uncategorized'}</div>
    `
    btn.addEventListener('click', () => {
      activeCategory = (activeCategory === cat) ? null : cat
      render()
      // Close the drawer if on mobile
      closeDrawer()
    })
    return btn
  }

  function buildCategoriesUI(){
    sidebarList.innerHTML = ''
    mobileList.innerHTML = ''
    categories.forEach(cat => {
      sidebarList.appendChild(categoryButton(cat))
      mobileList.appendChild(categoryButton(cat))
    })
  }

  function filterCards(){
    let out = allCards
    if(activeCategory){
      out = out.filter(c => String(c.category || '').trim() === activeCategory)
    }
    if(searchTerm){
      const s = searchTerm
      out = out.filter(c => {
        const hay = `${c.question||''} ${c.answer||''} ${c.category||''}`.toLowerCase()
        return hay.includes(s)
      })
    }
    return out
  }

  function render(){
    const filtered = filterCards()
    cardsEl.innerHTML = ''
    if(filtered.length === 0){
      emptyEl.classList.remove('hidden')
    }else{
      emptyEl.classList.add('hidden')
      const frag = document.createDocumentFragment()
      filtered.forEach(c => {
        const el = document.createElement('article')
        el.className = 'card'
        el.innerHTML = `
          <div class="q">${escapeHTML(c.question || '')}</div>
          <div class="meta">
            <span>${escapeHTML(c.category || 'Uncategorized')}</span>
            ${c.tags ? `<span>${escapeHTML([].concat(c.tags).join(', '))}</span>` : ''}
          </div>
          <div class="a">${formatAnswer(c.answer)}</div>
        `
        frag.appendChild(el)
      })
      cardsEl.appendChild(frag)
    }
    updateCounts()
    // Update active state on buttons
    qa('.category').forEach(btn => {
      const label = btn.textContent.trim()
      btn.classList.toggle('active', label === (activeCategory || 'Uncategorized'))
    })
  }

  function updateCounts(){
    const total = allCards.length
    const shown = filterCards().length
    metaCountsEl.textContent = `${shown} / ${total} cards`
  }

  function escapeHTML(s){
    return String(s).replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]))
  }

  function formatAnswer(a){
    if(a == null) return ''
    const s = String(a)
    // Basic formatting: support fenced code blocks and line breaks
    if(s.includes('```')){
      // naive split for display
      return s.split('```').map((chunk, i) => i % 2 ? `<pre><code>${escapeHTML(chunk)}</code></pre>` : `<p>${escapeHTML(chunk)}</p>`).join('')
    }
    return s.split('\n').map(line => `<p>${escapeHTML(line)}</p>`).join('')
  }

  async function fetchJSON(url){
    const r = await fetch(url, { headers: { 'Accept': 'application/json' }})
    if(!r.ok) throw new Error(`HTTP ${r.status}`)
    return await r.json()
  }

  async function boot(){
    try{
      // Try API first; fall back to static if available
      const [cards, cats] = await Promise.allSettled([
        fetchJSON('/api/cards'),
        fetchJSON('/api/categories')
      ])

      if(cards.status === 'fulfilled'){
        allCards = normalizeCards(cards.value)
      }else{
        // fallback: try static JSON
        try{
          allCards = normalizeCards(await fetchJSON('/static/cards.json'))
        }catch(_){ allCards = [] }
      }

      if(cats.status === 'fulfilled'){
        categories = cats.value
      }else{
        // derive from cards
        const set = new Set(allCards.map(c => String(c.category || '').trim()))
        categories = Array.from(set).sort()
      }

      buildCategoriesUI()
      render()
    }catch(err){
      console.error(err)
      cardsEl.innerHTML = `<div class="empty">Failed to load cards.</div>`
    }
  }

  function normalizeCards(arr){
    return [].concat(arr || []).map(c => ({
      question: c.question ?? c.q ?? '',
      answer: c.answer ?? c.a ?? '',
      category: c.category ?? '',
      tags: c.tags ?? []
    }))
  }

  boot()
})()
