/** 无框架 UI 组件：表格 / 过滤条 / 抽屉 / 徽标 / 仪表 / 索引卡 / 空态 / toast。
 *  sites、crawl-runs、defects 三个业务页共用 table + filterBar + drawer。 */

export function esc(value) {
  return String(value ?? '').replace(/[&<>"']/g, (ch) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]));
}

export function fmtTime(iso) {
  if (!iso) return '—';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return esc(iso);
  return new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
}

export function fmtPct(value, digits = 2) {
  const num = Number(value);
  if (!Number.isFinite(num)) return '—';
  return `${(num * 100).toFixed(digits)}%`;
}

export function fmtNum(value) {
  const num = Number(value);
  if (!Number.isFinite(num)) return esc(value ?? '—');
  return new Intl.NumberFormat('zh-CN').format(num);
}

export function badge(tone, text) {
  return `<span class="badge ${esc(tone)}">${esc(text)}</span>`;
}

export function statStrip(items) {
  return `<div class="stat-strip">${items
    .map(
      (item) => `<div class="stat">
        <span class="k">${esc(item.label)}</span>
        <span class="v">${esc(item.value)}</span>
        <span class="hint">${esc(item.hint || '')}</span>
      </div>`,
    )
    .join('')}</div>`;
}

/** 共享过滤条：三个业务页都走这里，保证筛选交互与间距一致。 */
export function filterBar({ id, fields, extra = '' }) {
  return `<div class="filter-bar" id="${esc(id)}" data-testid="${esc(id)}">
    ${fields.map((spec) => field(spec)).join('')}
    <div class="spacer"></div>
    ${extra}
  </div>`;
}

export function emptyState({ title, hint, actionText, actionId }) {
  return `<div class="empty" data-testid="empty-state">
    <div class="mark">${esc(title)}</div>
    <p>${esc(hint || '')}</p>
    ${actionText ? `<button class="btn ghost" id="${esc(actionId || 'empty-action')}">${esc(actionText)}</button>` : ''}
  </div>`;
}

export function errorBox(message, retryId = 'retry-btn') {
  return `<div class="error-box"><span>${esc(message)}</span><button class="btn sm ghost" id="${esc(retryId)}">重试</button></div>`;
}

export function table({ columns, rows, rowId, empty }) {
  if (!rows || rows.length === 0) return emptyState(empty || { title: '暂无记录', hint: '调整筛选条件，或先发起一次巡检。' });
  const head = columns.map((col) => `<th>${esc(col.label)}</th>`).join('');
  const body = rows
    .map(
      (row) => `<tr data-id="${esc(row.id)}" ${rowId ? `id="${esc(rowId(row))}"` : ''}>
        ${columns.map((col) => `<td class="${esc(col.className || '')}">${col.render ? col.render(row) : esc(row[col.key])}</td>`).join('')}
      </tr>`,
    )
    .join('');
  return `<div class="table-wrap"><table class="data"><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`;
}

export function drawer({ title, subtitle, body, footer }) {
  const backdrop = document.createElement('div');
  backdrop.className = 'drawer-backdrop';
  backdrop.innerHTML = `<aside class="drawer" role="dialog" aria-modal="true">
    <div class="drawer-head">
      <div>
        <h2>${esc(title)}</h2>
        <div class="mono muted">${esc(subtitle || '')}</div>
      </div>
      <button class="btn sm ghost" data-close>关闭</button>
    </div>
    <div class="drawer-body">${body}</div>
    ${footer ? `<div class="drawer-foot">${footer}</div>` : ''}
  </aside>`;
  const close = () => {
    backdrop.remove();
    document.removeEventListener('keydown', onKey);
  };
  const onKey = (event) => {
    if (event.key === 'Escape') close();
  };
  backdrop.addEventListener('click', (event) => {
    if (event.target === backdrop || event.target.closest('[data-close]')) close();
  });
  document.addEventListener('keydown', onKey);
  document.body.appendChild(backdrop);
  return { root: backdrop, close };
}

export function kv(items) {
  return `<dl class="kv">${items
    .map(([key, value]) => `<dt>${esc(key)}</dt><dd>${value === undefined || value === null || value === '' ? '—' : value}</dd>`)
    .join('')}</dl>`;
}

export function barList(items, tone = '') {
  const max = Math.max(1, ...items.map((item) => item.count));
  return `<div class="bars">${items
    .map(
      (item) => `<div class="bar-row">
        <span>${esc(item.label)}</span>
        <div class="bar-track"><div class="bar-fill ${esc(tone)}" style="width:${Math.round((item.count / max) * 100)}%"></div></div>
        <span class="mono">${esc(item.count)}</span>
      </div>`,
    )
    .join('')}</div>`;
}

export function trendChart(points) {
  const max = Math.max(1, ...points.map((point) => point.runs));
  return `<div class="trend">${points
    .map(
      (point) => `<div class="col" title="${esc(point.date)} · ${esc(point.runs)} 次">
        <div class="stem" style="height:${Math.max(2, Math.round((point.runs / max) * 70))}px"></div>
        <span class="lbl">${esc(point.date.slice(5))}</span>
      </div>`,
    )
    .join('')}</div>`;
}

/** 覆盖率仪表：SVG 圆环 + 数字。数值来自后端 /api/overview。 */
export function gauge({ value, label = '覆盖率', caption = '' }) {
  const pct = Math.max(0, Math.min(1, Number(value) || 0));
  const radius = 56;
  const circumference = 2 * Math.PI * radius;
  const dash = (pct * circumference).toFixed(2);
  return `<div class="gauge" data-testid="coverage-gauge">
    <svg viewBox="0 0 132 132" role="img" aria-label="${esc(label)} ${esc(fmtPct(pct))}">
      <circle class="g-track" cx="66" cy="66" r="${radius}"></circle>
      <circle class="g-fill" cx="66" cy="66" r="${radius}"
        stroke-dasharray="${dash} ${circumference.toFixed(2)}"></circle>
      <text class="g-value" x="66" y="68" text-anchor="middle">${esc(fmtPct(pct))}</text>
      <text class="g-cap" x="66" y="86" text-anchor="middle">${esc(caption || 'A∩B∩C / A')}</text>
    </svg>
    <span class="gauge-label">${esc(label)}</span>
  </div>`;
}

export function coverageBar(value) {
  const pct = Math.max(0, Math.min(1, Number(value) || 0));
  const tone = pct < 0.9 ? 'is-danger' : pct < 0.95 ? 'is-warn' : '';
  return `<div class="cov-bar ${tone}"><span style="width:${(pct * 100).toFixed(1)}%"></span></div>`;
}

/** 站点索引卡：总览与报表共用。 */
export function siteCards(sites) {
  if (!sites || sites.length === 0) return emptyState({ title: '还没有站点', hint: '先在「站点与栏目」登记政务站。' });
  return `<div class="site-cards">${sites
    .map(
      (site) => `<article class="site-card" data-testid="site-card-${esc(site.code)}">
      <span class="sc-mark">${esc(site.code)}</span>
      <h3>${esc(site.name)}</h3>
      <div class="sc-row"><span>覆盖率</span><b>${esc(fmtPct(site.coverage))}</b></div>
      ${coverageBar(site.coverage)}
      <div class="sc-row"><span>目录 / sitemap</span><b>${esc(fmtNum(site.catalog_total))} / ${esc(fmtNum(site.sitemap_total))}</b></div>
      <div class="sc-row"><span>缺陷 P0/P1/P2</span><b>${esc(site.p0)} / ${esc(site.p1)} / ${esc(site.p2)}</b></div>
    </article>`,
    )
    .join('')}</div>`;
}

export function chipRow(items, toneOf = () => '') {
  return `<div class="chip-row">${items
    .map((item) => `<span class="chip ${esc(toneOf(item))}">${esc(item.label)}<b>${esc(item.count)}</b></span>`)
    .join('')}</div>`;
}

export function field({ label, name, type = 'text', value = '', placeholder = '', options = null, attrs = '' }) {
  const control = options
    ? `<select name="${esc(name)}" id="${esc(name)}" ${attrs}>${options
        .map((opt) => `<option value="${esc(opt.value)}" ${String(opt.value) === String(value) ? 'selected' : ''}>${esc(opt.label)}</option>`)
        .join('')}</select>`
    : `<input name="${esc(name)}" id="${esc(name)}" type="${esc(type)}" value="${esc(value)}" placeholder="${esc(placeholder)}" ${attrs} />`;
  return `<div class="field"><label for="${esc(name)}">${esc(label)}</label>${control}</div>`;
}

export function toast(message, tone = '') {
  const stack = document.getElementById('toast-stack');
  const node = document.createElement('div');
  node.className = `toast ${tone}`;
  node.textContent = message;
  stack.appendChild(node);
  setTimeout(() => node.remove(), 3800);
}

export function errorMessage(err) {
  if (!err) return '未知错误';
  if (err.code === 'FORBIDDEN') return '当前角色没有这个操作的权限';
  if (err.code === 'CONFLICT') return '该自然键已存在，请换一个';
  return err.message || '请求失败';
}
