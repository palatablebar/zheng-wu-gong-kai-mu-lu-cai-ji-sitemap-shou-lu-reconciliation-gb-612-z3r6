import { api } from '../api.js';
import { CATEGORY_TONE, ENUMS, badgeTone, can, statusTone } from '../config.js';
import { chipRow, drawer, errorBox, errorMessage, esc, field, filterBar, fmtTime, kv, table, toast } from '../ui.js';

const state = { runId: '', siteId: '', category: '', severity: '', status: '', q: '' };

function evidenceBlock(item) {
  const evidence = item.evidence || {};
  const lines = [];
  if (evidence.redirect_chain && evidence.redirect_chain.length) {
    lines.push(`301 链路（${evidence.hops ?? evidence.redirect_chain.length} 跳）`);
    evidence.redirect_chain.forEach((hop) => lines.push(`  ${hop.status || 301}  ${hop.from}\n       → ${hop.to}`));
    if (evidence.final_url) lines.push(`最终 URL：${evidence.final_url}`);
  }
  if (evidence.page_canonical) lines.push(`页面 rel=canonical：${evidence.page_canonical}\n应为：${evidence.expected_canonical}`);
  if (evidence.sitemap_loc) lines.push(`sitemap loc：${evidence.sitemap_loc}\nlastmod：${evidence.lastmod || '—'}\n来源文件：${evidence.source_file || 'sitemap.xml'}`);
  if (evidence.entry_url) lines.push(`目录入口：${evidence.entry_url}\n栏目：${evidence.column || '—'}（第 ${evidence.page_no || 1} 页）`);
  if (evidence.http_status !== undefined && evidence.http_status !== null) lines.push(`探测状态：HTTP ${evidence.http_status}`);
  if (evidence.entry_urls) lines.push(`重复入口（${evidence.entry_urls.length} 条）：\n  ${evidence.entry_urls.join('\n  ')}`);
  if (evidence.action) lines.push(`\n整改建议：${evidence.action}`);
  return `<pre class="code">${esc(lines.join('\n') || JSON.stringify(evidence, null, 2))}</pre>`;
}

function openDefect(view, ctx, item) {
  const canReview = can(ctx.user.role, 'defect:review');
  const { root, close } = drawer({
    title: item.title,
    subtitle: `${item.site_code} · ${item.category_label}`,
    body: `${kv([
      ['严重度', `<span class="badge ${badgeTone(item.severity)}">${esc(ENUMS.severity[item.severity] || item.severity)}</span>`],
      ['分类', `<span class="badge ${CATEGORY_TONE[item.category] || 'info'}">${esc(item.category_label)}</span>`],
      ['站点', esc(item.site_name || item.site_code)],
      ['栏目', esc(item.column_name || '—')],
      ['URL', `<span class="mono">${esc(item.canonical_url)}</span>`],
      ['所属巡检', `<span class="mono">${esc(item.run_no || item.run_id)}</span>`],
      ['处理状态', `<span class="badge ${statusTone(item.status)}">${esc(ENUMS.defectStatus[item.status] || item.status)}</span>`],
      ['复核人', esc(item.reviewer || '—')],
      ['复核备注', esc(item.review_note || '—')],
      ['检出时间', fmtTime(item.created_at)],
    ])}
    <div class="rule-label">判定说明</div>
    <p style="margin:0;font-size:0.86rem;color:var(--ink-soft)">${esc(item.summary)}</p>
    <div class="rule-label">证据链</div>
    ${evidenceBlock(item)}`,
    footer: canReview
      ? `<form id="review-form" style="display:grid;gap:10px">
          ${field({ label: '处理结论', name: 'status', value: item.status, options: Object.entries(ENUMS.defectStatus).map(([value, label]) => ({ value, label })) })}
          ${field({ label: '整改备注', name: 'note', value: item.review_note || '', placeholder: '写一句整改依据，例如「已补进 sitemap 2026-11 批次」' })}
          <button class="btn accent" type="submit">提交整改</button>
        </form>`
      : '<span class="mono muted">公开办审阅角色可以查看，但不能处理缺陷单</span>',
  });
  root.querySelector('#review-form')?.addEventListener('submit', async (event) => {
    event.preventDefault();
    const form = event.target;
    try {
      await api.patch(`/api/defects/${item.id}/review`, {
        status: form.status.value,
        note: form.note.value.trim() || null,
      });
      toast('整改结论已保存');
      close();
      await defectsPage.render(view, ctx);
    } catch (err) {
      toast(errorMessage(err), 'err');
    }
  });
}

export const defectsPage = {
  async render(view, ctx) {
    state.runId = ctx.query.run_id || state.runId;
    let data;
    let facets;
    let sites;
    try {
      [data, facets, sites] = await Promise.all([
        api.get('/api/defects', {
          run_id: state.runId,
          site_id: state.siteId,
          category: state.category,
          severity: state.severity,
          status: state.status,
          q: state.q,
          limit: 50,
        }),
        api.get('/api/defects/facets', { run_id: state.runId }),
        api.get('/api/sites', { limit: 50 }),
      ]);
    } catch (err) {
      view.innerHTML = errorBox(errorMessage(err));
      view.querySelector('#retry-btn')?.addEventListener('click', () => defectsPage.render(view, ctx));
      return;
    }
    view.innerHTML = `
      <section class="panel">
        <div class="panel-head">
          <h2>对账缺陷单 ${state.runId ? `<span class="mono muted">· 巡检 #${esc(state.runId)}</span>` : ''}</h2>
          <div style="display:flex;gap:8px;align-items:center">
            <span class="meta">${esc(data.total)} 条</span>
            ${can(ctx.user.role, 'export:read') ? '<button class="btn sm ghost" id="export-defects">导出缺陷 CSV</button>' : ''}
          </div>
        </div>
        <div class="panel-body">
          ${chipRow(facets.severity, (item) => (item.key === 'p0' ? 'is-p0' : item.key === 'p1' ? 'is-p1' : 'is-p2'))}
          ${filterBar({
            id: 'defect-filters',
            fields: [
              { label: '搜索', name: 'q', value: state.q, placeholder: 'URL / 站点编码 / 说明' },
              { label: '分类', name: 'category', value: state.category, options: [{ value: '', label: '全部' }, ...Object.entries(ENUMS.category).map(([value, label]) => ({ value, label }))] },
              { label: '严重度', name: 'severity', value: state.severity, options: [{ value: '', label: '全部' }, ...Object.entries(ENUMS.severity).map(([value, label]) => ({ value, label }))] },
              { label: '处理状态', name: 'status', value: state.status, options: [{ value: '', label: '全部' }, ...Object.entries(ENUMS.defectStatus).map(([value, label]) => ({ value, label }))] },
              { label: '站点', name: 'site_id', value: state.siteId, options: [{ value: '', label: '全部' }, ...sites.items.map((site) => ({ value: site.id, label: site.code }))] },
            ],
          })}
        </div>
        ${table({
          rows: data.items,
          empty: { title: '这个筛选下没有缺陷', hint: '换一个分类或巡检再看；也可能是本批次已经整改干净。' },
          columns: [
            { key: 'severity', label: '严重度', render: (row) => `<span class="badge ${badgeTone(row.severity)}">${esc(ENUMS.severity[row.severity] || row.severity)}</span>` },
            { key: 'category', label: '分类', render: (row) => `<span class="badge ${CATEGORY_TONE[row.category] || 'info'}">${esc(row.category_label)}</span>` },
            { key: 'site_code', label: '站点', className: 'mono' },
            { key: 'column_name', label: '栏目', render: (row) => esc(row.column_name || '—') },
            { key: 'canonical_url', label: 'canonical URL', className: 'url', render: (row) => esc(row.canonical_url) },
            { key: 'status', label: '处理', render: (row) => `<span class="badge ${statusTone(row.status)}">${esc(ENUMS.defectStatus[row.status] || row.status)}</span>` },
            { key: 'created_at', label: '检出时间', render: (row) => fmtTime(row.created_at) },
          ],
        })}
      </section>`;

    const filters = view.querySelector('#defect-filters');
    const apply = () => {
      state.q = filters.querySelector('[name=q]').value.trim();
      state.category = filters.querySelector('[name=category]').value;
      state.severity = filters.querySelector('[name=severity]').value;
      state.status = filters.querySelector('[name=status]').value;
      state.siteId = filters.querySelector('[name=site_id]').value;
      defectsPage.render(view, ctx);
    };
    filters?.addEventListener('change', apply);
    filters?.querySelector('[name=q]')?.addEventListener('keydown', (event) => {
      if (event.key === 'Enter') apply();
    });
    view.querySelectorAll('table.data tbody tr').forEach((row) => {
      row.addEventListener('click', () => {
        const item = data.items.find((entry) => String(entry.id) === row.dataset.id);
        if (item) openDefect(view, ctx, item);
      });
    });
    view.querySelector('#export-defects')?.addEventListener('click', async () => {
      try {
        await api.download(`/api/exports/defects.csv${state.runId ? `?run_id=${state.runId}` : ''}`, 'defects.csv');
        toast('已开始下载缺陷清单');
      } catch (err) {
        toast(errorMessage(err), 'err');
      }
    });
  },
};

export default defectsPage;
