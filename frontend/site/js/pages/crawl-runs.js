import { api } from '../api.js';
import { ENUMS, can, crawlTone } from '../config.js';
import { drawer, errorBox, errorMessage, esc, field, filterBar, fmtNum, fmtPct, fmtTime, kv, table, toast } from '../ui.js';

const state = { siteId: '', status: '' };

function sitesTable(sites) {
  if (!sites || sites.length === 0) return '<p class="muted">本次巡检没有站点明细。</p>';
  return `<div class="table-wrap"><table class="data" style="min-width:0">
    <thead><tr><th>站点</th><th>分页</th><th>链接/去重</th><th>覆盖率</th><th>缺陷</th><th>P0</th></tr></thead>
    <tbody>${sites
      .map(
        (site) => `<tr><td>${esc(site.name)}<div class="mono muted">${esc(site.code)}</div></td>
          <td class="num">${esc(site.pages)}</td>
          <td class="num">${esc(site.links)} / ${esc(site.unique)}</td>
          <td class="num">${esc(fmtPct(site.coverage))}</td>
          <td class="num">${esc(site.defects)}</td>
          <td class="num">${esc(site.p0)}</td></tr>`,
      )
      .join('')}</tbody></table></div>`;
}

function openRun(view, ctx, run) {
  const { root } = drawer({
    title: `巡检 ${run.run_no}`,
    subtitle: `${run.site_name || '全部站点'} · ${ENUMS.trigger[run.trigger] || run.trigger}`,
    body: `${kv([
      ['状态', esc(ENUMS.crawlStatus[run.status] || run.status)],
      ['操作人', esc(run.operator_email)],
      ['分页清单页', `<span class="mono">${esc(run.pages)}</span>`],
      ['抓取链接', `<span class="mono">${esc(fmtNum(run.links))}</span>`],
      ['canonical 去重', `<span class="mono">${esc(fmtNum(run.unique_links))}（重复率 ${esc(fmtPct(run.dup_ratio))}）</span>`],
      ['目录 / sitemap', `<span class="mono">${esc(run.catalog_count)} / ${esc(run.sitemap_count)}</span>`],
      ['覆盖率 / 不可达率', `<span class="mono">${esc(fmtPct(run.coverage))} / ${esc(fmtPct(run.unreachable_rate))}</span>`],
      ['缺陷', `${esc(run.defect_count)} 条（P0 ${esc(run.p0_count)} / P1 ${esc(run.p1_count)} / P2 ${esc(run.p2_count)}）`],
      ['开始', fmtTime(run.started_at)],
      ['结束', fmtTime(run.finished_at)],
    ])}
    <div class="rule-label">站点明细</div>
    ${sitesTable((run.metrics || {}).sites || [])}
    <div class="rule-label">运行日志</div>
    <pre class="code">${esc(run.log_text || '（无日志）')}</pre>`,
    footer: '<button class="btn accent" data-defects>查看本次缺陷单</button>',
  });
  root.querySelector('[data-defects]')?.addEventListener('click', () => {
    location.hash = `#/defects?run_id=${run.id}`;
  });
}

function openRunForm(view, ctx, sites) {
  const triggerOptions = Object.entries(ENUMS.trigger)
    .filter(([key]) => key !== 'seed')
    .map(([value, label]) => ({ value, label }));
  const { root, close } = drawer({
    title: '发起巡检',
    subtitle: '分页抓取 → URL 规范化 → 三向对账，结果写入缺陷单',
    body: `<form id="run-form" style="display:grid;gap:12px">
      ${field({
        label: '巡检范围',
        name: 'site_id',
        options: [{ value: '', label: '全部启用站点' }, ...sites.map((site) => ({ value: site.id, label: `${site.name}（${site.code}）` }))],
      })}
      ${field({ label: '触发方式', name: 'trigger', value: 'manual', options: triggerOptions })}
      <div class="mono muted">算法 A：rel=next 优先，缺失时按 index_2.html 猜解；去 utm_*/sessionid/#fragment，统一 https 与尾斜杠，跟随 301。<br />
      算法 B：A（目录）/ B（sitemap）/ C（可达）三向对账，死链 P0、漏收 P1、链路与口径 P2。</div>
      <div class="form-error" id="run-error"></div>
      <button class="btn accent" type="submit">开始巡检</button>
    </form>`,
  });
  root.querySelector('#run-form').addEventListener('submit', async (event) => {
    event.preventDefault();
    const form = event.target;
    const button = form.querySelector('button[type=submit]');
    button.disabled = true;
    button.textContent = '巡检中…';
    try {
      const run = await api.post('/api/crawl-runs', {
        site_id: form.site_id.value ? Number(form.site_id.value) : null,
        trigger: form.trigger.value,
      });
      toast(`巡检 ${run.run_no} 完成：覆盖率 ${fmtPct(run.coverage)}，缺陷 ${run.defect_count} 条`);
      close();
      await crawlRunsPage.render(view, ctx);
    } catch (err) {
      root.querySelector('#run-error').textContent = errorMessage(err);
      button.disabled = false;
      button.textContent = '开始巡检';
    }
  });
}

export const crawlRunsPage = {
  async render(view, ctx) {
    let runs;
    let sites;
    try {
      [runs, sites] = await Promise.all([
        api.get('/api/crawl-runs', { site_id: state.siteId, status: state.status, limit: 50 }),
        api.get('/api/sites', { limit: 50 }),
      ]);
    } catch (err) {
      view.innerHTML = errorBox(errorMessage(err));
      view.querySelector('#retry-btn')?.addEventListener('click', () => crawlRunsPage.render(view, ctx));
      return;
    }
    view.innerHTML = `
      <section class="panel">
        <div class="panel-head">
          <h2>抓取运行</h2>
          <div style="display:flex;gap:8px;align-items:center">
            <span class="meta">${esc(runs.total)} 次巡检</span>
            ${can(ctx.user.role, 'crawl:create') ? '<button class="btn sm accent" id="new-run">发起巡检</button>' : ''}
          </div>
        </div>
        <div class="panel-body">
          ${filterBar({
            id: 'run-filters',
            fields: [
              { label: '站点', name: 'site_id', value: state.siteId, options: [{ value: '', label: '全部' }, ...sites.items.map((site) => ({ value: site.id, label: site.name }))] },
              { label: '状态', name: 'status', value: state.status, options: [{ value: '', label: '全部' }, ...Object.entries(ENUMS.crawlStatus).map(([value, label]) => ({ value, label }))] },
            ],
          })}
        </div>
        ${table({
          rows: runs.items,
          empty: { title: '还没有巡检记录', hint: '巡检专员或主管可以发起一次巡检。' },
          columns: [
            { key: 'run_no', label: '巡检号', className: 'mono' },
            { key: 'site_name', label: '范围' },
            { key: 'status', label: '状态', render: (row) => `<span class="badge ${crawlTone(row.status)}">${esc(ENUMS.crawlStatus[row.status] || row.status)}</span>` },
            { key: 'pages', label: '分页', className: 'num' },
            { key: 'links', label: '链接 / 去重', className: 'num', render: (row) => `${esc(row.links)} / ${esc(row.unique_links)}` },
            { key: 'dup_ratio', label: '重复率', className: 'num', render: (row) => esc(fmtPct(row.dup_ratio)) },
            { key: 'coverage', label: '覆盖率', className: 'num', render: (row) => esc(fmtPct(row.coverage)) },
            { key: 'defect_count', label: '缺陷 P0/P1/P2', className: 'num', render: (row) => `${esc(row.defect_count)}（${esc(row.p0_count)}/${esc(row.p1_count)}/${esc(row.p2_count)}）` },
            { key: 'started_at', label: '开始时间', render: (row) => fmtTime(row.started_at) },
          ],
        })}
      </section>`;

    const filters = view.querySelector('#run-filters');
    filters?.addEventListener('change', () => {
      state.siteId = filters.querySelector('[name=site_id]').value;
      state.status = filters.querySelector('[name=status]').value;
      crawlRunsPage.render(view, ctx);
    });
    view.querySelectorAll('table.data tbody tr').forEach((row) => {
      row.addEventListener('click', () => {
        const run = runs.items.find((item) => String(item.id) === row.dataset.id);
        if (run) openRun(view, ctx, run);
      });
    });
    view.querySelector('#new-run')?.addEventListener('click', () => openRunForm(view, ctx, sites.items));
  },
};

export default crawlRunsPage;
