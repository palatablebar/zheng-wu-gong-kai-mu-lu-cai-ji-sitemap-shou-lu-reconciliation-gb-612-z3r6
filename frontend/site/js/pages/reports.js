import { api } from '../api.js';
import { ENUMS, can } from '../config.js';
import {
  emptyState,
  errorBox,
  errorMessage,
  esc,
  fmtNum,
  fmtPct,
  fmtTime,
  siteCards,
  table,
  toast,
} from '../ui.js';

const state = { tab: 'coverage' };

function coverageTable(sites) {
  return `<div class="table-wrap"><table class="data" style="min-width:0">
    <thead><tr>
      <th>站点</th><th>目录 A</th><th>sitemap B</th><th>可达 C</th><th>A∩B∩C</th>
      <th>覆盖率</th><th>不可达率</th><th>死链</th><th>缺陷</th><th>P0/P1/P2</th>
    </tr></thead>
    <tbody>${sites
      .map(
        (site) => `<tr data-id="${esc(site.code)}">
          <td>${esc(site.name)}<div class="mono muted">${esc(site.code)}</div></td>
          <td class="num">${esc(fmtNum(site.catalog_total))}</td>
          <td class="num">${esc(fmtNum(site.sitemap_total))}</td>
          <td class="num">${esc(fmtNum(site.reachable))}</td>
          <td class="num">${esc(fmtNum(site.hit))}</td>
          <td class="num">${esc(fmtPct(site.coverage))}</td>
          <td class="num">${esc(fmtPct(site.unreachable_rate))}</td>
          <td class="num">${esc(site.dead)}</td>
          <td class="num">${esc(site.defects)}</td>
          <td class="num">${esc(site.p0)}/${esc(site.p1)}/${esc(site.p2)}</td>
        </tr>`,
      )
      .join('')}</tbody></table></div>`;
}

async function renderCoverage(view, ctx) {
  const runs = await api.get('/api/crawl-runs', { limit: 1 });
  const latest = runs.items[0];
  if (!latest) {
    return emptyState({ title: '还没有巡检数据', hint: '先发起一次巡检，报表会按巡检号归档。' });
  }
  const run = await api.get(`/api/crawl-runs/${latest.id}`);
  const sites = (run.metrics || {}).sites || [];
  const totals = (run.metrics || {}).totals || {};
  return `
    <section class="panel">
      <div class="panel-head">
        <h2>覆盖率报表 · ${esc(run.run_no)}</h2>
        <span class="meta">${esc(ENUMS.crawlStatus[run.status] || run.status)} · ${fmtTime(run.finished_at)}</span>
      </div>
      <div class="panel-body">
        <div class="rule-label">三向口径</div>
        <div class="kv">
          <dt>目录条目 A</dt><dd class="mono">${esc(fmtNum(run.catalog_count))}</dd>
          <dt>sitemap B</dt><dd class="mono">${esc(fmtNum(run.sitemap_count))}</dd>
          <dt>命中 A∩B∩C</dt><dd class="mono">${esc(fmtNum(totals.hit))}</dd>
          <dt>覆盖率</dt><dd class="mono">${esc(fmtPct(run.coverage))} = ${esc(fmtNum(totals.hit))} / ${esc(fmtNum(run.catalog_count))}</dd>
          <dt>重复率</dt><dd class="mono">${esc(fmtPct(run.dup_ratio))}（抓取 ${esc(fmtNum(run.links))} 条 → 去重 ${esc(fmtNum(run.unique_links))} 条）</dd>
          <dt>缺陷构成</dt><dd>P0 ${esc(run.p0_count)} / P1 ${esc(run.p1_count)} / P2 ${esc(run.p2_count)}，合计 ${esc(run.defect_count)} 条</dd>
        </div>
        <div class="rule-label" style="margin-top:14px">站点明细</div>
        ${coverageTable(sites)}
      </div>
    </section>
    <section class="panel">
      <div class="panel-head"><h2>站点索引卡</h2><span class="meta">index cards</span></div>
      <div class="panel-body">${siteCards(sites)}</div>
    </section>`;
}

async function renderAudit() {
  const data = await api.get('/api/audit', { limit: 100 });
  return `<section class="panel">
    <div class="panel-head"><h2>审计日志</h2><span class="meta">${esc(data.total)} 条 · 最近 100 条</span></div>
    ${table({
      rows: data.items,
      empty: { title: '还没有审计记录', hint: '登录、登记、巡检、整改、导出都会留痕。' },
      columns: [
        { key: 'created_at', label: '时间', render: (row) => fmtTime(row.created_at) },
        { key: 'actor_email', label: '操作人', className: 'mono' },
        { key: 'actor_role', label: '角色' },
        { key: 'action_label', label: '动作' },
        { key: 'entity', label: '对象' },
        { key: 'layer', label: '层', render: (row) => `<span class="badge">${esc(row.layer)}</span>` },
        { key: 'detail', label: '详情', render: (row) => `<span class="mono muted">${esc(JSON.stringify(row.detail || {}))}</span>` },
      ],
    })}
  </section>`;
}

export const reportsPage = {
  async render(view, ctx) {
    const isAdmin = can(ctx.user.role, 'audit:read');
    if (!isAdmin && state.tab === 'audit') state.tab = 'coverage';
    view.innerHTML = '<div class="empty"><div class="mark">正在归档报表…</div></div>';
    let body;
    try {
      body = state.tab === 'audit' ? await renderAudit() : await renderCoverage(view, ctx);
    } catch (err) {
      view.innerHTML = errorBox(errorMessage(err));
      view.querySelector('#retry-btn')?.addEventListener('click', () => reportsPage.render(view, ctx));
      return;
    }
    view.innerHTML = `
      <section class="panel">
        <div class="panel-head">
          <h2>报表与导出</h2>
          <div style="display:flex;gap:8px;align-items:center">
            ${can(ctx.user.role, 'export:read') ? '<button class="btn sm ghost" id="exp-defects">缺陷 CSV</button><button class="btn sm ghost" id="exp-sites">站点 CSV</button><button class="btn sm ghost" id="exp-coverage">覆盖率 CSV</button>' : '<span class="meta">当前角色不可导出</span>'}
          </div>
        </div>
        <div class="panel-body">
          <div class="tabs" id="report-tabs">
            <button data-tab="coverage" class="${state.tab === 'coverage' ? 'active' : ''}">覆盖率报表</button>
            ${isAdmin ? `<button data-tab="audit" class="${state.tab === 'audit' ? 'active' : ''}">审计日志</button>` : ''}
          </div>
          <p class="mono muted" style="margin:0 0 10px">导出内容来自算法 B 的落库结果，行数与页面一致；缺陷 CSV 一行一条缺陷单。</p>
        </div>
      </section>
      ${body}`;

    view.querySelectorAll('#report-tabs button').forEach((button) => {
      button.addEventListener('click', () => {
        state.tab = button.dataset.tab;
        reportsPage.render(view, ctx);
      });
    });
    const downloads = [
      ['#exp-defects', '/api/exports/defects.csv', 'defects.csv', '缺陷清单'],
      ['#exp-sites', '/api/exports/sites.csv', 'sites.csv', '站点覆盖表'],
      ['#exp-coverage', '/api/exports/coverage.csv', 'coverage.csv', '覆盖率报表'],
    ];
    downloads.forEach(([selector, path, filename, label]) => {
      view.querySelector(selector)?.addEventListener('click', async () => {
        try {
          await api.download(path, filename);
          toast(`已开始下载${label}`);
        } catch (err) {
          toast(errorMessage(err), 'err');
        }
      });
    });
  },
};

export default reportsPage;
