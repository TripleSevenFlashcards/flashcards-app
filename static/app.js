;(function(){
  const q  = (s, el=document) => el.querySelector(s)
  const qa = (s, el=document) => Array.from(el.querySelectorAll(s))

  // Elements
  const cardsEl       = q('#cards')
  const emptyEl       = q('#empty')
  const metaCountsEl  = q('#metaCounts')

  const sidebarList   = q('#categoryList')
  const mobileList    = q('#categoryListMobile')

  const searchSidebar = q('#searchInput')
  const searchTop     = q('#searchTop')
  const searchDrawer  = q('#searchDrawer')

  // Drawer controls (hamburger)
  const navDrawer     = q('#navDrawer')
  const menuToggle    = q('#menuToggle')
  const drawerClose   = q('#drawerClose')

  // State
  let allCards = []
  let categories = []
  let activeCategory = null
  let searchTerm = ''

  // Drawer handlers
  function openDrawer(){
    navDrawer.setAttribute('aria-hidden','false')
    menuToggle.setAttribute('aria-expanded','true')
  }
  function closeDrawer(){
    navDrawer.setAttribute('aria-hidden','true')
    menuToggle.setAttribute('aria-expanded','false')
  }
  menuToggle.addEventListener('click', openDrawer)
  drawerClose.addEventListener('click', closeDrawer)
  navDrawer.addEventListener('click', (e) => { if(e.target === navDrawer) closeDrawer() })
  // ESC to close
  document.addEventListener('keydown', (e) => { if(e.key === 'Escape') closeDrawer() })

  ;[searchSidebar, searchTop, searchDrawer].forEach(inp => {
    if(!inp) return
    inp.addEventListener('input', (e) => {
      searchTerm = String(e.target.value || '').trim().toLowerCase()
      // Sync search boxes so user sees consistent state
      ;[searchSidebar, searchTop, searchDrawer].forEach(x => { if(x && x !== e.target) x.value = e.target.value })
      render()
    })
  })

  function categoryButton(cat){
    const label = cat || 'Uncategorized'
    const btn = document.createElement('button')
    btn.className = 'category'
    btn.type = 'button'
    btn.textContent = label
    btn.addEventListener('click', () => {
      activeCategory = (activeCategory === cat) ? null : cat
      render()
      closeDrawer()
    })
    return btn
  }

  function buildCategoriesUI(){
    sidebarList && (sidebarList.innerHTML = '')
    mobileList && (mobileList.innerHTML = '')
    categories.forEach(cat => {
      const a = categoryButton(cat)
      const b = categoryButton(cat)
      sidebarList && sidebarList.appendChild(a)
      mobileList && mobileList.appendChild(b)
    })
    reflectActiveButtons()
  }

  function reflectActiveButtons(){
    qa('.category').forEach(btn => {
      const label = btn.textContent.trim()
      const isActive = label === (activeCategory || 'Uncategorized')
      btn.classList.toggle('active', isActive)
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
    reflectActiveButtons()
  }

  function updateCounts(){
    const total = allCards.length
    const shown = filterCards().length
    if(metaCountsEl) metaCountsEl.textContent = `${shown} / ${total} cards`
  }

  function escapeHTML(s){
    return String(s).replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]))
  }

  function formatAnswer(a){
    if(a == null) return ''
    const s = String(a)
    if(s.includes('```')){
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
      // Prefer API; gracefully fall back to static JSON if present
      const [cards, cats] = await Promise.allSettled([
        fetchJSON('/api/cards'),
        fetchJSON('/api/categories')
      ])

      if(cards.status === 'fulfilled'){
        allCards = normalizeCards(cards.value)
      }else{
        try{
          allCards = normalizeCards(await fetchJSON('/static/cards.json'))
        }catch(_){ allCards = [] }
      }

      if(cats.status === 'fulfilled'){
        categories = dedupeSort(cats.value)
      }else{
        const set = new Set(allCards.map(c => (c.category || '').trim()))
        categories = dedupeSort(Array.from(set))
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

  function dedupeSort(arr){
    const a = Array.from(new Set([].concat(arr || []).map(s => String(s || '').trim())))
    a.sort((x, y) => x.localeCompare(y, undefined, { sensitivity: 'base' }))
    return a
  }

  boot()
})()
