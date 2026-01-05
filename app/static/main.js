document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.dropzone').forEach(dz => {
    const input = dz.querySelector('input[type=file]');
    if (!input) return;
    const triggerPreview = () => {
      const evt = new Event('change');
      input.dispatchEvent(evt);
    };
    const activate = (e, on) => {
      e.preventDefault(); e.stopPropagation();
      dz.classList.toggle('border-primary', on);
      dz.classList.toggle('bg-light', on);
    };
    dz.addEventListener('click', () => input.click());
    ['dragenter','dragover'].forEach(evt => dz.addEventListener(evt, e => activate(e, true)));
    ['dragleave','drop'].forEach(evt => dz.addEventListener(evt, e => activate(e, false)));
    dz.addEventListener('drop', e => {
      const files = e.dataTransfer.files;
      input.files = files;
      triggerPreview();
    });
  });
});

document.addEventListener('DOMContentLoaded', () => {
  const desc = document.getElementById('description');
  const title = document.getElementById('title');
  const box = document.getElementById('kb-suggest');
  const render = (items) => {
    if (!box) return;
    box.innerHTML = items.map(i => `<li class="list-group-item"><a href="${i.url}" target="_blank">${i.title}</a></li>`).join('') || `<li class="list-group-item text-muted">Sem sugestões.</li>`;
  };
  let timer;
  const onChange = () => {
    const q = [title?.value||'', desc?.value||''].join(' ').trim();
    if (!q || !box) { if (box) box.innerHTML=''; return; }
    clearTimeout(timer);
    timer = setTimeout(() => {
      fetch(`/kb/search?q=${encodeURIComponent(q)}`).then(r=>r.json()).then(render).catch(()=>{});
    }, 300);
  };
  title && title.addEventListener('input', onChange);
  desc && desc.addEventListener('input', onChange);
});

// Generic previews for file inputs with data-preview
document.addEventListener('DOMContentLoaded', () => {
  const setupPreviews = (input) => {
    const sel = input.getAttribute('data-preview');
    if (!sel) return;
    const container = document.querySelector(sel);
    if (!container) return;
    const render = () => {
      const files = Array.from(input.files || []);
      container.innerHTML = '';
      if (!files.length) return;
      files.forEach(file => {
        const col = document.createElement('div');
        col.className = 'col-6 col-md-3';
        const wrap = document.createElement('div');
        wrap.className = 'preview-item p-2';
        if (file.type.startsWith('image/')) {
          const img = document.createElement('img');
          img.className = 'img-fluid rounded';
          img.alt = file.name;
          const url = URL.createObjectURL(file);
          img.src = url;
          img.onload = () => URL.revokeObjectURL(url);
          wrap.appendChild(img);
        } else {
          const box = document.createElement('div');
          box.className = 'd-flex align-items-center justify-content-center bg-light rounded';
          box.style.height = '80px';
          box.textContent = file.name.split('.').pop()?.toUpperCase() || 'FILE';
          wrap.appendChild(box);
        }
        const name = document.createElement('div');
        name.className = 'name text-truncate mt-1';
        name.title = file.name;
        name.textContent = file.name;
        wrap.appendChild(name);
        col.appendChild(wrap);
        container.appendChild(col);
      });
    };
    input.addEventListener('change', render);
  };
  document.querySelectorAll('input[type=file][data-preview]').forEach(setupPreviews);
});

// Show Bootstrap toasts
document.addEventListener('DOMContentLoaded', () => {
  const container = document.getElementById('toastContainer') || document;
  const toasts = container.querySelectorAll('.toast');
  toasts.forEach(t => {
    const toast = new bootstrap.Toast(t);
    toast.show();
  });
});

// Reactions (emoji) on comments
document.addEventListener('DOMContentLoaded', () => {
  const thread = document.querySelector('.chat-thread');
  if (!thread) return;
  const ticketId = thread.getAttribute('data-ticket-id');
  const csrf = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';

  const renderCounts = (counts, el) => {
    const entries = Object.entries(counts || {}).filter(([, n]) => n > 0);
    el.innerHTML = entries.map(([e, n]) => `<span class="badge bg-light text-dark me-1">${e} ${n}</span>`).join('');
  };

  // Initialize counts
  thread.querySelectorAll('[data-comment-id]').forEach(row => {
    const id = row.getAttribute('data-comment-id');
    fetch(`/tickets/${ticketId}/comments/${id}/reactions`).then(r=>r.json()).then(data => {
      if (!data.ok) return;
      const box = row.querySelector('.reaction-counts');
      if (box) renderCounts(data.counts, box);
    }).catch(()=>{});
  });

  thread.addEventListener('click', (ev) => {
    const btn = ev.target.closest('.react-btn');
    if (!btn) return;
    const row = ev.target.closest('[data-comment-id]');
    if (!row) return;
    const commentId = row.getAttribute('data-comment-id');
    const emoji = btn.getAttribute('data-emoji');
    const form = new URLSearchParams();
    form.set('emoji', emoji);
    form.set('csrf_token', csrf);
    fetch(`/tickets/${ticketId}/comments/${commentId}/react`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: form.toString(),
    }).then(r=>r.json()).then(data => {
      if (!data.ok) return;
      const box = row.querySelector('.reaction-counts');
      if (box) renderCounts(data.counts, box);
    }).catch(()=>{});
  });
});

// Open PDFs in embedded viewer (PDF.js hosted)
document.addEventListener('DOMContentLoaded', () => {
  const modalEl = document.getElementById('pdfModal');
  if (!modalEl) return;
  const iframe = modalEl.querySelector('#pdfViewer');
  const modal = new bootstrap.Modal(modalEl);
  document.body.addEventListener('click', (e) => {
    const link = e.target.closest('a.view-attachment[data-type="pdf"]');
    if (!link) return;
    e.preventDefault();
    const url = link.getAttribute('href');
    const viewer = `https://mozilla.github.io/pdf.js/web/viewer.html?file=${encodeURIComponent(url)}`;
    iframe.src = viewer;
    modal.show();
  });
});

// Theme toggle (light/dark)
document.addEventListener('DOMContentLoaded', () => {
  const btn = document.getElementById('themeToggle');
  const root = document.documentElement;
  const apply = (mode) => {
    if (mode === 'dark') root.setAttribute('data-theme', 'dark');
    else root.removeAttribute('data-theme');
  };
  const saved = localStorage.getItem('theme');
  if (saved) apply(saved);
  btn && btn.addEventListener('click', () => {
    const now = root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
    apply(now);
    localStorage.setItem('theme', now);
  });
});

// Lightbox for images/videos
document.addEventListener('DOMContentLoaded', () => {
  const modalEl = document.getElementById('lightboxModal');
  if (!modalEl) return;
  const img = modalEl.querySelector('.lightbox-image');
  const vid = modalEl.querySelector('.lightbox-video');
  const modal = new bootstrap.Modal(modalEl);
  const close = () => {
    img.src = '';
    vid.pause();
    vid.removeAttribute('src');
  };
  modalEl.addEventListener('hidden.bs.modal', close);
  document.body.addEventListener('click', (e) => {
    const link = e.target.closest('a.lb-open');
    if (!link) return;
    e.preventDefault();
    const type = link.getAttribute('data-type');
    const url = link.getAttribute('href');
    if (type === 'image') {
      vid.classList.add('d-none');
      img.classList.remove('d-none');
      img.src = url;
    } else if (type === 'video') {
      img.classList.add('d-none');
      vid.classList.remove('d-none');
      vid.setAttribute('src', url);
      vid.setAttribute('controls', 'controls');
    }
    modal.show();
  });
});

// Simple emoji picker (expand panel)
document.addEventListener('DOMContentLoaded', () => {
  const thread = document.querySelector('.chat-thread');
  if (!thread) return;
  const more = ['🎉','😅','😢','🔥','✅','❌','⚠️','💡','🧰','🕒','🧑\u200d💻','📌','📎','📷','📝'];
  thread.querySelectorAll('.reactions').forEach(box => {
    const group = box.querySelector('.btn-group');
    if (!group) return;
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'btn btn-outline-secondary react-btn react-more';
    btn.textContent = '…';
    const panel = document.createElement('div');
    panel.className = 'mt-2 d-none';
    more.forEach(e => {
      const b = document.createElement('button');
      b.type = 'button';
      b.className = 'btn btn-light btn-sm me-1 react-btn';
      b.setAttribute('data-emoji', e);
      b.textContent = e;
      panel.appendChild(b);
    });
    btn.addEventListener('click', () => panel.classList.toggle('d-none'));
    group.appendChild(btn);
    box.appendChild(panel);
  });
});

// Global loading overlay for long operations (form POSTs, explicit triggers)
document.addEventListener('DOMContentLoaded', () => {
  const ensureOverlay = () => {
    let el = document.getElementById('loadingOverlay');
    if (!el) {
      el = document.createElement('div');
      el.id = 'loadingOverlay';
      el.className = 'd-none';
      el.style.position = 'fixed';
      el.style.inset = '0';
      el.style.background = 'rgba(0,0,0,.45)';
      el.style.display = 'flex';
      el.style.alignItems = 'center';
      el.style.justifyContent = 'center';
      el.style.zIndex = '2000';
      el.innerHTML = '<div class="text-center text-white">\
        <div class="spinner-border text-light mb-3" role="status" style="width:3rem;height:3rem">\
          <span class="visually-hidden">Carregando...</span>\
        </div>\
        <div>Processando, aguarde...</div>\
      </div>';
      document.body.appendChild(el);
    }
    return el;
  };

  const overlay = ensureOverlay();
  const show = () => overlay.classList.remove('d-none');
  const hide = () => overlay.classList.add('d-none');

  // Optional global access if needed
  window.showLoadingOverlay = show;
  window.hideLoadingOverlay = hide;

  // Show overlay on submit of POST forms (or forms marked with data-loading)
  document.querySelectorAll('form').forEach(form => {
    form.addEventListener('submit', () => {
      const method = (form.getAttribute('method') || 'GET').toUpperCase();
      const wants = form.hasAttribute('data-loading') || method === 'POST';
      if (!wants) return;
      if (typeof form.checkValidity === 'function' && !form.checkValidity()) return;
      show();
    });
  });

  // Explicit trigger on any element with data-loading attribute
  document.body.addEventListener('click', (e) => {
    const el = e.target.closest('[data-loading]');
    if (!el) return;
    show();
  });
});

// Notifications polling and UI
document.addEventListener('DOMContentLoaded', () => {
  let lastId = 0;
  const bellBadge = document.getElementById('notifBellCount');
  const container = document.getElementById('toastContainer') || document.body;
  const listBox = document.getElementById('notifList');
  const audioUrl = '/static/sons/bip.mp3';
  let notifCache = [];

  const beep = () => {
    try {
      if (!window.__notifAudio) {
        window.__notifAudio = new Audio(audioUrl);
      }
      window.__notifAudio.currentTime = 0;
      window.__notifAudio.play().catch(() => {
        // fallback to oscillator if autoplay blocked
        const ctx = new (window.AudioContext || window.webkitAudioContext)();
        const o = ctx.createOscillator();
        const g = ctx.createGain();
        o.type = 'sine';
        o.frequency.value = 880;
        o.connect(g);
        g.connect(ctx.destination);
        g.gain.setValueAtTime(0.0001, ctx.currentTime);
        g.gain.exponentialRampToValueAtTime(0.2, ctx.currentTime + 0.01);
        g.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.25);
        o.start();
        o.stop(ctx.currentTime + 0.3);
      });
    } catch (e) { /* ignore */ }
  };

  const showToast = (title, body) => {
    const wrap = document.createElement('div');
    wrap.className = 'toast align-items-center text-bg-primary border-0 mb-2';
    wrap.setAttribute('role', 'alert');
    wrap.setAttribute('aria-live', 'assertive');
    wrap.setAttribute('aria-atomic', 'true');
    wrap.setAttribute('data-bs-delay', '6000');
    wrap.innerHTML = '<div class="d-flex">\
      <div class="toast-body"><strong>' + (title || 'Notificação') + '</strong>' + (body ? ' — ' + body : '') + '</div>\
      <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>\
    </div>';
    container.appendChild(wrap);
    const t = new bootstrap.Toast(wrap);
    t.show();
    wrap.addEventListener('hidden.bs.toast', () => wrap.remove());
  };

  const applyUnread = (unread) => {
    if (!bellBadge) return;
    const n = Number(unread || 0);
    bellBadge.textContent = n > 99 ? '99+' : String(n);
    bellBadge.classList.toggle('d-none', n === 0);
  };

  const poll = () => {
    const url = '/notify/poll' + (lastId ? ('?after_id=' + encodeURIComponent(lastId)) : '');
    fetch(url).then(r => r.json()).then(data => {
      if (!data || !data.ok) return;
      applyUnread(data.unread);
      const items = data.items || [];
      if (items.length) {
        items.forEach(n => {
          lastId = Math.max(lastId, n.id || lastId);
          showToast(n.title, n.body);
          notifCache.unshift(n);
        });
        notifCache = notifCache.slice(0, 20);
        // refresh dropdown list
        if (listBox) renderNotifList();
        beep();
      }
    }).catch(() => {});
  };

  // Render dropdown list helper
  const renderNotifList = () => {
    listBox.innerHTML = '';
    if (!notifCache.length) {
      const empty = document.createElement('div');
      empty.className = 'list-group-item text-muted';
      empty.textContent = 'Sem notificações.';
      listBox.appendChild(empty);
      return;
    }
    notifCache.forEach(n => {
      const row = document.createElement('div');
      row.className = 'list-group-item d-flex justify-content-between align-items-start gap-2';
      row.dataset.id = n.id;
      const a = document.createElement('a');
      a.className = 'flex-grow-1 text-decoration-none';
      a.href = n.link || '#';
      a.textContent = (n.title || 'Notificação') + (n.body ? ' — ' + n.body : '');
      const btn = document.createElement('button');
      btn.className = 'btn btn-sm btn-outline-secondary notif-read-one';
      btn.textContent = 'Lida';
      row.appendChild(a);
      row.appendChild(btn);
      listBox.appendChild(row);
    });
  };

  // SSE for notifications (fallback to polling)
  let usedSSE = false;
  if (window.EventSource) {
    try {
      const es = new EventSource('/notify/stream');
      usedSSE = true;
      es.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data || '{}');
          applyUnread(data.unread);
          const items = data.items || [];
          if (items.length) {
            items.forEach(n => {
              lastId = Math.max(lastId, n.id || lastId);
              showToast(n.title, n.body);
              notifCache.unshift(n);
            });
            notifCache = notifCache.slice(0, 20);
            if (listBox) renderNotifList();
            beep();
          }
        } catch {}
      };
      es.onerror = () => { /* keep connection; browser will retry */ };
    } catch {}
  }

  if (!usedSSE) {
    // Initial poll and interval
    poll();
    setInterval(poll, 20000);
  }

  // Mark as seen when opening the dropdown
  const dd = document.getElementById('notifDropdown');
  if (dd) {
    dd.addEventListener('shown.bs.dropdown', () => {
      const meta = document.querySelector('meta[name="csrf-token"]');
      const token = meta ? meta.getAttribute('content') : '';
      // Marca como "visto" (não zera o badge aqui)
      const body = new URLSearchParams();
      body.set('csrf_token', token);
      fetch('/notify/seen', {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded', 'X-CSRFToken': token },
        body: body.toString()
      }).catch(() => {});
    });
  }

  // Per-item mark as read (event delegation)
  if (listBox) {
    listBox.addEventListener('click', (ev) => {
      const row = ev.target.closest('.list-group-item');
      if (!row) return;
      const id = row.dataset.id;
      const meta = document.querySelector('meta[name="csrf-token"]');
      const token = meta ? meta.getAttribute('content') : '';

      // Clique no botão "Lida"
      const btn = ev.target.closest('.notif-read-one');
      if (btn) {
        if (!id) return;
        const body = new URLSearchParams();
        body.set('csrf_token', token);
        fetch(`/notify/read/${encodeURIComponent(id)}`, {
          method: 'POST',
          credentials: 'same-origin',
          headers: { 'Content-Type': 'application/x-www-form-urlencoded', 'X-CSRFToken': token },
          body: body.toString()
        }).then(r => r.json()).then(data => {
          if (data && data.ok) {
            row.classList.add('text-muted');
            // Decrementa badge localmente
            const current = Number((bellBadge && bellBadge.textContent || '0').replace(/\D/g,'')) || 0;
            const next = Math.max(current - 1, 0);
            applyUnread(next);
          }
        }).catch(() => {});
        return;
      }

      // Clique no link da notificação
      const link = ev.target.closest('a');
      if (link) {
        const href = link.getAttribute('href') || '#';
        if (!id || href === '#') return; // nada a fazer
        ev.preventDefault();
        const body = new URLSearchParams();
        body.set('csrf_token', token);
        fetch(`/notify/read/${encodeURIComponent(id)}`, {
          method: 'POST',
          credentials: 'same-origin',
          headers: { 'Content-Type': 'application/x-www-form-urlencoded', 'X-CSRFToken': token },
          body: body.toString()
        }).then(r => r.json()).then(data => {
          if (data && data.ok) {
            row.classList.add('text-muted');
            const current = Number((bellBadge && bellBadge.textContent || '0').replace(/\D/g,'')) || 0;
            const next = Math.max(current - 1, 0);
            applyUnread(next);
          }
        }).catch(() => {}).finally(() => {
          // Navega após tentativa de marcação
          window.location.href = href;
        });
      }
    });
  }

  // Mark all as read
  const markAll = document.getElementById('notifMarkAll');
  if (markAll) {
    markAll.addEventListener('click', () => {
      const meta = document.querySelector('meta[name="csrf-token"]');
      const token = meta ? meta.getAttribute('content') : '';
      const body = new URLSearchParams();
      body.set('csrf_token', token);
      fetch('/notify/read_all', {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded', 'X-CSRFToken': token },
        body: body.toString()
      })
        .then(r => r.json()).then(() => {
          applyUnread(0);
          if (listBox) {
            const items = listBox.querySelectorAll('.list-group-item');
            items.forEach(el => el.classList.add('text-muted'));
          }
        }).catch(() => {});
    });
  }
});

// Real-time updates for ticket detail thread
document.addEventListener('DOMContentLoaded', () => {
  const thread = document.querySelector('.chat-thread');
  if (!thread) return;
  const ticketId = Number(thread.getAttribute('data-ticket-id'));
  if (!ticketId) return;
  let lastId = 0;
  const getLast = () => {
    const els = thread.querySelectorAll('[data-comment-id]');
    if (!els.length) return 0;
    const id = Number(els[els.length - 1].getAttribute('data-comment-id'));
    return isNaN(id) ? 0 : id;
  };
  lastId = getLast();
  const appendItems = (items) => {
    if (!items || !items.length) return;
    items.forEach(it => {
      const row = document.createElement('div');
      row.className = 'chat-row other';
      row.setAttribute('data-comment-id', it.id);
      row.innerHTML = `
        <div class="bubble">
          <div class="meta"><span class="name">${it.user_name}</span><span class="time">${it.created_at}</span></div>
          <div class="text">${(it.content || '').replace(/\n/g,'<br>')}</div>
        </div>`;
      thread.appendChild(row);
      lastId = Math.max(lastId, it.id || lastId);
    });
  };
  let usedSSE2 = false;
  if (window.EventSource) {
    try {
      const es2 = new EventSource(`/tickets/${ticketId}/comments/stream?after=${encodeURIComponent(lastId)}`);
      usedSSE2 = true;
      es2.onmessage = (e) => {
        try { const data = JSON.parse(e.data||'{}'); appendItems(data.items||[]); } catch {}
      };
    } catch {}
  }
  if (!usedSSE2) {
    const poll = () => {
      fetch(`/tickets/${ticketId}/comments/poll?after=${encodeURIComponent(lastId)}`)
        .then(r => r.json()).then(data => appendItems((data&&data.items)||[])).catch(()=>{});
    };
    setInterval(poll, 5000);
  }
});

// Real-time updates for chat page (chat/index)
document.addEventListener('DOMContentLoaded', () => {
  const chatBox = document.getElementById('chatThread');
  if (!chatBox) return;
  const ticketId = Number(chatBox.getAttribute('data-ticket-id'));
  if (!ticketId) return;
  let lastId = 0;
  const getLast = () => {
    const els = chatBox.querySelectorAll('[data-comment-id]');
    if (!els.length) return 0;
    const id = Number(els[els.length - 1].getAttribute('data-comment-id'));
    return isNaN(id) ? 0 : id;
  };
  lastId = getLast();
  const appendChat = (items) => {
    if (!items || !items.length) return;
    items.forEach(it => {
      const row = document.createElement('div');
      row.className = 'list-group-item';
      row.setAttribute('data-comment-id', it.id);
      row.innerHTML = `<div class="small text-muted d-flex justify-content-between"><span>${it.user_name}</span><span>${it.created_at}</span></div>
        <div style="white-space: pre-wrap;">${it.content}</div>`;
      chatBox.appendChild(row);
      lastId = Math.max(lastId, it.id || lastId);
    });
  };
  let usedSSE3 = false;
  if (window.EventSource) {
    try {
      const es3 = new EventSource(`/chat/stream?ticket_id=${encodeURIComponent(ticketId)}&after=${encodeURIComponent(lastId)}`);
      usedSSE3 = true;
      es3.onmessage = (e) => { try { const data = JSON.parse(e.data||'{}'); appendChat(data.items||[]); } catch {} };
    } catch {}
  }
  if (!usedSSE3) {
    const poll = () => {
      fetch(`/chat/poll?ticket_id=${encodeURIComponent(ticketId)}&after=${encodeURIComponent(lastId)}`)
        .then(r => r.json()).then(data => appendChat((data&&data.items)||[])).catch(()=>{});
    };
    setInterval(poll, 4000);
  }
});
