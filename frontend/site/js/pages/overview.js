import { api } from '../api.js';
import { BRAND, ENUMS } from '../config.js';
import {
  barList,
  chipRow,
  emptyState,
  errorBox,
  errorMessage,
  esc,
  fmtNum,
  fmtPct,
  fmtTime,
  gauge,
  siteCards,
  trendChart,
} from '../ui.js';

/** 总览：覆盖率仪表 + P0/P1/P2 分诊 + 站点索引卡 + 缺陷分类分布 + 最近巡检。 */
export const overviewPage = {
  async render(view, ctx) {
    view.innerHTML = '<div class="empty"><div class="mark">正在调取台账…</div></div>';
    try {
      const data = await api.get('/api/overview');
      const latest = data.latest_run;
      view.innerHTML = `
        <section class="panel">
          <div class="panel-head">
            <h2>收录覆盖率台账</h2>
            <span class="meta">three-way reconcile · ${esc(BRAND.edition)}</span>
          </div>
          <div class="panel-body">
            <div class="ledger-hero">
              ${gauge({ value: data.coverage, label: '收录覆盖率', caption: '|A∩B∩C| / |A|' })}
              <div>
                ${chipRow(
                  [
                    { key: 'p0', label: 'P0 死链', count: data.p0_total },
                    { key: 'p1', label: 'P1 漏收', count: data.p1_total },
                    { key: 'p2', label: 'P2 待优化', count: data.p2_total },
                    { key: 'pending', label: '待整改', count: data.pending_total },
                  ],
                  (item) => (item.key === 'p0' ? 'is-p0' : item.key === 'p1' ? 'is-p1' : item.key === 'p2' ? 'is-p2' : ''),
                )}
                <div class="rule-label">本次口径</div>
                <div class="sc-row"><span>政务站（启用 / 登记）</span><b>${esc(data.sites_enabled)} / ${esc(data.sites_total)}</b></div>
                <div class="sc-row"><span>公开目录条目 A</span><b>${esc(fmtNum(data.catalog_total))}</b></div>
                <div class="sc-row"><span>sitemap loc B</span><b>${esc(fmtNum(data.sitemap_total))}</b></div>
                <div class="sc-row"><span>不可达率（A\\C）</span><b>${esc(fmtPct(data.unreachable_rate))}</b></div>
                <div class="sc-row"><span>后台任务</span><b>${data.worker_alive ? 'worker 在岗' : '心跳超时'}</b></div>
              </div>
            </div>
          </div>
        </section>

        <section class="panel">
          <div class="panel-head">
            <h2>站点覆盖索引</h2>
            <span class="meta">coverage by site</span>
          </div>
          <div class="panel-body">${siteCards(data.coverage_by_site)}</div>
        </section>

        <div class="grid-2">
          <section class="panel">
            <div class="panel-head"><h2>缺陷分类分布</h2><span class="meta">category</span></div>
            <div class="panel-body">${
              data.category.some((item) => item.count > 0)
                ? barList(data.category, 'danger')
                : emptyState({ title: '还没有缺陷单', hint: '去「抓取运行」发起一次巡检。' })
            }</div>
          </section>
          <section class="panel">
            <div class="panel-head"><h2>整改流转</h2><span class="meta">defect status</span></div>
            <div class="panel-body">${
              data.status.some((item) => item.count > 0)
                ? barList(data.status, 'ok')
                : emptyState({ title: '还没有整改记录', hint: '缺陷单生成后由巡检专员处理。' })
            }</div>
          </section>
        </div>

        <div class="grid-2">
          <section class="panel">
            <div class="panel-head"><h2>近 7 天巡检</h2><span class="meta">runs / day</span></div>
            <div class="panel-body">${trendChart(data.trend)}</div>
          </section>
          <section class="panel">
            <div class="panel-head"><h2>最近一次巡检</h2><span class="meta">latest run</span></div>
            <div class="panel-body">
              ${
                latest
                  ? `<div class="kv">
                      <dt>巡检号</dt><dd class="mono">${esc(latest.run_no)}</dd>
                      <dt>范围</dt><dd>${esc(latest.site_name || '全部站点')}</dd>
                      <dt>状态</dt><dd>${esc(ENUMS.crawlStatus[latest.status] || latest.status)}</dd>
                      <dt>开始</dt><dd>${fmtTime(latest.started_at)}</dd>
                      <dt>分页页数</dt><dd class="mono">${esc(latest.pages)}</dd>
                      <dt>链接 / 去重</dt><dd class="mono">${esc(latest.links)} / ${esc(latest.unique_links)}（重复 ${esc(fmtPct(latest.dup_ratio))}）</dd>
                      <dt>覆盖率</dt><dd class="mono">${esc(fmtPct(latest.coverage))}</dd>
                      <dt>缺陷</dt><dd>${esc(latest.defect_count)} 条（P0 ${esc(latest.p0_count)} / P1 ${esc(latest.p1_count)} / P2 ${esc(latest.p2_count)}）</dd>
                    </div>
                    <p class="muted mono" style="margin:10px 0 0">${esc(BRAND.subtitle)}</p>`
                  : emptyState({ title: '还没有巡检记录', hint: '先在「站点与栏目」确认登记，再去「抓取运行」发起巡检。' })
              }
            </div>
          </section>
        </div>`;
    } catch (err) {
      view.innerHTML = errorBox(errorMessage(err));
      view.querySelector('#retry-btn')?.addEventListener('click', () => overviewPage.render(view, ctx));
    }
  },
};

export default overviewPage;
