import { api } from '../api.js';
import { ENUMS, can } from '../config.js';
import { drawer, errorBox, errorMessage, esc, field, filterBar, fmtNum, fmtTime, kv, table, toast } from '../ui.js';

const state = { q: '', region: '', enabled: '' };

function columnsBlock(columns) {
  if (!columns || columns.length === 0) return '<p class="muted">该站点还没有登记栏目入口。</p>';
  return `<div class="table-wrap"><table class="data" style="min-width:0">
    <thead><tr><th>栏目</th><th>条目</th><th>分页</th></tr></thead>
    <tbody>${columns
      .map(
        (column) =>
          `<tr><td>${esc(column.column_name)}<span class="mono muted"> / ${esc(column.column_code)}</span></td>
           <td class="num">${esc(fmtNum(column.entries))}</td>
           <td class="num">${esc(column.pages)}</td></tr>`,
      )
      .join('')}</tbody></table></div>`;
}

function catalogBlock(items) {
  if (!items || items.length === 0) return '<p class="muted">还没有登记目录条目。</p>';
  return `<div class="table-wrap"><table class="data" style="min-width:0">
    <thead><tr><th>栏目</th><th>条目</th><th>canonical</th></tr></thead>
    <tbody>${items
      .map(
        (item) => `<tr><td>${esc(item.column_name)}</td>
          <td>${esc(item.title)}<span class="mono muted"> 第 ${esc(item.page_no)} 页 · ${esc(ENUMS.discovery[item.discovered_from] || item.discovered_from)}</span></td>
          <td class="url mono">${esc(item.canonical_url)}</td></tr>`,
      )
      .join('')}</tbody></table></div>`;
}

async function openSite(view, ctx, site) {
  const editable = can(ctx.user.role, 'site:write');
  let detail;
  let catalog;
  try {
    [detail, catalog] = await Promise.all([
      api.get(`/api/sites/${site.id}`),
      api.get('/api/catalog', { site_id: site.id, limit: 12 }),
    ]);
  } catch (err) {
    toast(errorMessage(err), 'err');
    return;
  }
  const { root, close } = drawer({
    title: site.name,
    subtitle: `${site.code} · ${site.dept}`,
    body: `${kv([
      ['首页', `<span class="mono">${esc(site.home_url)}</span>`],
      ['sitemap', site.sitemap_url ? `<span class="mono">${esc(site.sitemap_url)}</span>` : '—'],
      ['区域', esc(site.region)],
      ['分页口径', `每页 ${esc(site.page_size)} 条 · 最大深度 ${esc(site.max_depth)}`],
      ['目录 / sitemap', `${esc(fmtNum(site.catalog_count))} / ${esc(fmtNum(site.sitemap_count))}`],
      ['最近巡检', fmtTime(site.last_crawled_at)],
      ['状态', site.enabled ? '<span class="badge ok">启用</span>' : '<span class="badge">停用</span>'],
      ['备注', esc(site.note || '—')],
    ])}
    <div class="rule-label">栏目入口（${esc(detail.columns.length)} 栏）</div>
    ${columnsBlock(detail.columns)}
    <div class="rule-label">目录条目（前 12 条，共 ${esc(fmtNum(catalog.total))} 条）</div>
    ${catalogBlock(catalog.items)}
    <div class="rule-label">URL 规范化口径核对</div>
    <div style="display:grid;gap:8px">
      <div class="field"><label for="norm-url">原始 URL</label>
        <input id="norm-url" value="${esc(site.home_url)}/xxgk/zcwj/index.html?utm_source=wechat&amp;sessionid=s-01#top" /></div>
      <button class="btn sm ghost" id="norm-run" type="button">按算法 A 口径归一</button>
      <pre class="code" id="norm-out">等待核对…</pre>
    </div>`,
    footer: editable
      ? `<button class="btn ghost" data-toggle>${site.enabled ? '停用该站点' : '重新启用'}</button>`
      : '<span class="mono muted">公开办审阅角色只读</span>',
  });
  root.querySelector('#norm-run')?.addEventListener('click', async () => {
    const url = root.querySelector('#norm-url').value.trim();
    try {
      const result = await api.get('/api/catalog/normalize', { url });
      root.querySelector('#norm-out').textContent = `输入：${result.input}\ncanonical：${result.canonical}\n是否改写：${result.changed ? '是' : '否'}`;
    } catch (err) {
      root.querySelector('#norm-out').textContent = errorMessage(err);
    }
  });
  root.querySelector('[data-toggle]')?.addEventListener('click', async () => {
    try {
      await api.patch(`/api/sites/${site.id}`, { enabled: !site.enabled });
      toast('站点状态已更新');
      close();
      await sitesPage.render(view, ctx);
    } catch (err) {
      toast(errorMessage(err), 'err');
    }
  });
}

function openCreate(view, ctx) {
  const { root, close } = drawer({
    title: '登记政务站',
    subtitle: '登记一次，后续巡检都按这份口径跑',
    body: `<form id="site-form" style="display:grid;gap:12px">
      ${field({ label: '站点编码（小写字母/数字/连字符）', name: 'code', placeholder: 'zwdt-hezhou' })}
      ${field({ label: '站点名称', name: 'name', placeholder: '河州市政务公开 · 专题专栏' })}
      ${field({ label: '首页地址（https://）', name: 'home_url', placeholder: 'https://zwdt.hezhou.gov.cn' })}
      ${field({ label: '责任部门', name: 'dept', placeholder: '市政府办公室 · 政务公开科' })}
      ${field({ label: '区域', name: 'region', value: '市本级', options: [{ value: '市本级', label: '市本级' }, { value: '区县', label: '区县' }] })}
      ${field({ label: '备注', name: 'note' })}
      <div class="form-error" id="site-error"></div>
      <button class="btn accent" type="submit">保存登记</button>
    </form>`,
  });
  root.querySelector('#site-form').addEventListener('submit', async (event) => {
    event.preventDefault();
    const form = event.target;
    try {
      await api.post('/api/sites', {
        code: form.code.value.trim(),
        name: form.name.value.trim(),
        home_url: form.home_url.value.trim(),
        dept: form.dept.value.trim() || null,
        region: form.region.value,
        note: form.note.value.trim() || null,
      });
      toast('站点已登记');
      close();
      await sitesPage.render(view, ctx);
    } catch (err) {
      root.querySelector('#site-error').textContent = errorMessage(err);
    }
  });
}

export const sitesPage = {
  async render(view, ctx) {
    let data;
    try {
      data = await api.get('/api/sites', { q: state.q, region: state.region, enabled: state.enabled, limit: 50 });
    } catch (err) {
      view.innerHTML = errorBox(errorMessage(err));
      view.querySelector('#retry-btn')?.addEventListener('click', () => sitesPage.render(view, ctx));
      return;
    }
    const regions = [...new Set(data.items.map((item) => item.region))].sort();
    view.innerHTML = `
      <section class="panel">
        <div class="panel-head">
          <h2>站点与栏目登记</h2>
          <div style="display:flex;gap:8px;align-items:center">
            <span class="meta">${esc(data.total)} 个站点</span>
            ${can(ctx.user.role, 'site:write') ? '<button class="btn sm accent" id="new-site">登记政务站</button>' : ''}
          </div>
        </div>
        <div class="panel-body">
          ${filterBar({
            id: 'site-filters',
            fields: [
              { label: '搜索', name: 'q', value: state.q, placeholder: '名称 / 编码 / 首页' },
              { label: '区域', name: 'region', value: state.region, options: [{ value: '', label: '全部' }, ...regions.map((region) => ({ value: region, label: region }))] },
              { label: '状态', name: 'enabled', value: state.enabled, options: [{ value: '', label: '全部' }, { value: 'true', label: '启用' }, { value: 'false', label: '停用' }] },
            ],
          })}
        </div>
        ${table({
          rows: data.items,
          empty: { title: '还没有登记站点', hint: '编辑部主管可以登记第一个政务站。' },
          columns: [
            { key: 'code', label: '站点编码', className: 'mono' },
            { key: 'name', label: '站点名称', render: (row) => `<b>${esc(row.name)}</b><div class="mono muted">${esc(row.home_url)}</div>` },
            { key: 'dept', label: '责任部门' },
            { key: 'region', label: '区域' },
            { key: 'catalog_count', label: '目录', className: 'num', render: (row) => esc(fmtNum(row.catalog_count)) },
            { key: 'sitemap_count', label: 'sitemap', className: 'num', render: (row) => esc(fmtNum(row.sitemap_count)) },
            { key: 'last_crawled_at', label: '最近巡检', render: (row) => fmtTime(row.last_crawled_at) },
            { key: 'enabled', label: '状态', render: (row) => (row.enabled ? '<span class="badge ok">启用</span>' : '<span class="badge">停用</span>') },
          ],
        })}
      </section>`;

    const filters = view.querySelector('#site-filters');
    const apply = () => {
      state.q = filters.querySelector('[name=q]').value.trim();
      state.region = filters.querySelector('[name=region]').value;
      state.enabled = filters.querySelector('[name=enabled]').value;
      sitesPage.render(view, ctx);
    };
    filters?.addEventListener('change', apply);
    filters?.querySelector('[name=q]')?.addEventListener('keydown', (event) => {
      if (event.key === 'Enter') apply();
    });
    view.querySelectorAll('table.data tbody tr').forEach((row) => {
      row.addEventListener('click', () => {
        const item = data.items.find((entry) => String(entry.id) === row.dataset.id);
        if (item) openSite(view, ctx, item);
      });
    });
    view.querySelector('#new-site')?.addEventListener('click', () => openCreate(view, ctx));
  },
};

export default sitesPage;
