import { api } from '../api.js';
import { ENUMS, can } from '../config.js';
import { drawer, errorBox, errorMessage, esc, filterBar, fmtNum, fmtTime, table, toast } from '../ui.js';

const state = { siteId: '', q: '', isGap: '' };

function sourceTone(status) {
  return { ok: 'ok', stale_gap: 'warn', failed: 'danger' }[status] || 'info';
}

function roundTone(status) {
  return { success: 'ok', partial: 'warn', failed: 'danger' }[status] || 'info';
}

function statLine(round) {
  const s = round.stats || {};
  return `新增 ${esc(fmtNum(s.added || 0))} · 更新 ${esc(fmtNum(s.updated || 0))} · 保持 ${esc(fmtNum(s.kept || 0))} · 缺口沿用 ${esc(fmtNum(s.reused_gap || 0))} · 下线 ${esc(fmtNum(s.removed || 0))}`;
}

function openSourceDrawer(view, ctx, siteId, source) {
  let versions = { items: [] };
  api
    .get(`/api/sitemaps/sources/${source.id}/versions`)
    .then((data) => {
      versions = data;
      render();
    })
    .catch((err) => toast(errorMessage(err), 'err'));

  const { root } = drawer({
    title: source.source_file,
    subtitle: `${ENUMS.sourceStatus[source.status] || source.status} · 子清单版本留痕`,
    body: `<div id="src-detail">加载中…</div>`,
  });

  function render() {
    root.querySelector('#src-detail').innerHTML = `
      <dl class="kv">
        <dt>来源 URL</dt><dd class="mono">${esc(source.source_url || '—')}</dd>
        <dt>状态</dt><dd><span class="badge ${sourceTone(source.status)}">${esc(ENUMS.sourceStatus[source.status] || source.status)}</span></dd>
        <dt>最近成功</dt><dd>${fmtTime(source.last_success_at)}</dd>
        <dt>最近尝试</dt><dd>${fmtTime(source.last_attempt_at)}</dd>
        <dt>内容指纹</dt><dd class="mono muted" style="word-break:break-all">${esc(source.last_success_hash || '—')}</dd>
        <dt>错误</dt><dd>${esc(source.last_error || '—')}</dd>
      </dl>
      <div class="rule-label">到达版本（${esc(versions.items.length)} 条，不可变）</div>
      ${table({
        rows: versions.items,
        empty: { title: '还没有版本记录', hint: '执行一次清单同步后这里会留下每次到达的快照。' },
        columns: [
          { key: 'status', label: '结果', render: (row) => `<span class="badge ${row.status === 'ok' ? 'ok' : 'danger'}">${row.status === 'ok' ? '成功' : '失败'}</span>` },
          { key: 'entry_count', label: '条目', className: 'num' },
          { key: 'error', label: '错误', render: (row) => esc(row.error || '—') },
          { key: 'created_at', label: '到达时间', render: (row) => fmtTime(row.created_at) },
        ],
      })}`;
  }
}

function openSyncForm(view, ctx, sites) {
  const options = sites.items.map((site) => ({ value: site.id, label: `${site.name}（${site.code}）` }));
  const { root, close } = drawer({
    title: '同步 sitemap 子清单',
    subtitle: '按 lastmod 裁决同一地址版本；失败子清单沿用上一版并标缺口，不会误删地址',
    body: `<form id="sync-form" style="display:grid;gap:12px">
      <div class="field"><label for="sync-site">站点</label>
        <select id="sync-site">${options.map((opt) => `<option value="${esc(opt.value)}">${esc(opt.label)}</option>`).join('')}</select></div>
      <div class="field"><label for="sync-fail">模拟超时的子清单（可空，逗号分隔文件名）</label>
        <input id="sync-fail" placeholder="sitemap-zcwj.xml" /></div>
      <div class="mono muted">演示环境从离线 fixture 重新拉取该站 sitemap index 下的全部子清单；
        被点名的子清单按 504 超时处理，其地址沿用上一版并标记缺口。</div>
      <div class="form-error" id="sync-error"></div>
      <button class="btn accent" type="submit">执行同步</button>
    </form>`,
  });
  root.querySelector('#sync-form').addEventListener('submit', async (event) => {
    event.preventDefault();
    const fail = root.querySelector('#sync-fail').value
      .split(',')
      .map((item) => item.trim())
      .filter(Boolean);
    const button = event.target.querySelector('button[type=submit]');
    button.disabled = true;
    button.textContent = '同步中…';
    try {
      const result = await api.post('/api/sitemaps/sync-fixture', {
        site_id: Number(root.querySelector('#sync-site').value),
        fail_sources: fail,
      });
      const round = result.items[0];
      toast(`同步完成：${round.round_no}，生效 ${round.entry_total} 条，缺口 ${round.gap_count} 条`);
      close();
      state.siteId = String(round.site_id);
      await sitemapsPage.render(view, ctx);
    } catch (err) {
      root.querySelector('#sync-error').textContent = errorMessage(err);
      button.disabled = false;
      button.textContent = '执行同步';
    }
  });
}

export const sitemapsPage = {
  async render(view, ctx) {
    let sites;
    let rounds;
    let sources;
    let entries;
    try {
      [sites, rounds, sources, entries] = await Promise.all([
        api.get('/api/sites', { limit: 50 }),
        api.get('/api/sitemaps/rounds', state.siteId ? { site_id: state.siteId, limit: 20 } : { limit: 20 }),
        state.siteId ? api.get('/api/sitemaps/sources', { site_id: state.siteId }) : Promise.resolve({ items: [] }),
        api.get(
          '/api/sitemaps',
          {
            site_id: state.siteId || undefined,
            q: state.q || undefined,
            is_gap: state.isGap === '' ? undefined : state.isGap,
            limit: 50,
          },
        ),
      ]);
    } catch (err) {
      view.innerHTML = errorBox(errorMessage(err));
      view.querySelector('#retry-btn')?.addEventListener('click', () => sitemapsPage.render(view, ctx));
      return;
    }
    if (!state.siteId && sites.items.length) state.siteId = String(sites.items[0].id);
    const syncable = can(ctx.user.role, 'sitemap:sync');
    view.innerHTML = `
      <section class="panel">
        <div class="panel-head">
          <h2>sitemap 子清单同步</h2>
          <div style="display:flex;gap:8px;align-items:center">
            <span class="meta">${esc(rounds.total)} 个同步轮次</span>
            ${syncable ? '<button class="btn sm accent" id="new-sync">同步子清单</button>' : ''}
          </div>
        </div>
        <div class="panel-body">
          ${filterBar({
            id: 'sitemap-filters',
            fields: [
              { label: '站点', name: 'site_id', value: state.siteId, options: [{ value: '', label: '全部站点' }, ...sites.items.map((site) => ({ value: site.id, label: `${site.name}（${site.code}）` }))] },
              { label: '搜索 loc', name: 'q', value: state.q, placeholder: 'URL 片段' },
              { label: '缺口', name: 'is_gap', value: state.isGap, options: [{ value: '', label: '全部' }, { value: 'true', label: '仅缺口沿用' }, { value: 'false', label: '仅正常' }] },
            ],
          })}
        </div>
        <div class="panel-body">
          <div class="rule-label">子清单来源（${esc(sources.items.length)}）</div>
          ${table({
            rows: sources.items,
            empty: { title: '该站点还没有子清单', hint: '执行一次同步后会自动登记 sitemap index 中的子清单。' },
            columns: [
              { key: 'source_file', label: '子清单', className: 'mono', render: (row) => esc(row.source_file) },
              { key: 'status', label: '状态', render: (row) => `<span class="badge ${sourceTone(row.status)}">${esc(ENUMS.sourceStatus[row.status] || row.status)}</span>` },
              { key: 'last_error', label: '最近错误', render: (row) => esc(row.last_error || '—') },
              { key: 'last_success_at', label: '最近成功', render: (row) => fmtTime(row.last_success_at) },
            ],
          })}
        </div>
        <div class="panel-body">
          <div class="rule-label">同步轮次（按 lastmod 裁决留痕）</div>
          ${table({
            rows: rounds.items,
            empty: { title: '还没有同步轮次', hint: '点击「同步子清单」开始第一轮版本化同步。' },
            columns: [
              { key: 'round_no', label: '轮次号', className: 'mono' },
              { key: 'status', label: '状态', render: (row) => `<span class="badge ${roundTone(row.status)}">${esc(ENUMS.roundStatus[row.status] || row.status)}</span>` },
              { key: 'entry_total', label: '生效地址', className: 'num' },
              { key: 'gap_count', label: '缺口', className: 'num', render: (row) => esc(fmtNum(row.gap_count)) },
              { key: 'stats', label: '裁决动作', render: (row) => statLine(row) },
              { key: 'created_at', label: '同步时间', render: (row) => fmtTime(row.created_at) },
            ],
          })}
        </div>
        <div class="panel-body">
          <div class="rule-label">生效地址（前 50 条，共 ${esc(fmtNum(entries.total))} 条；同一地址按 lastmod 裁决）</div>
          ${table({
            rows: entries.items,
            empty: { title: '没有生效地址', hint: '同步成功后这里展示裁决后的 sitemap loc。' },
            columns: [
              { key: 'source_file', label: '来源子清单', className: 'mono', render: (row) => esc(row.source_file) },
              { key: 'canonical_url', label: 'canonical URL', render: (row) => `<span class="mono">${esc(row.canonical_url)}</span>${row.is_gap ? ' <span class="badge warn">缺口沿用</span>' : ''}` },
              { key: 'lastmod', label: 'lastmod', className: 'mono' },
              { key: 'updated_at', label: '裁决更新时间', render: (row) => fmtTime(row.updated_at) },
            ],
          })}
        </div>
      </section>`;

    const filters = view.querySelector('#sitemap-filters');
    filters?.addEventListener('change', () => {
      state.siteId = filters.querySelector('[name=site_id]').value;
      state.q = filters.querySelector('[name=q]').value.trim();
      state.isGap = filters.querySelector('[name=is_gap]').value;
      sitemapsPage.render(view, ctx);
    });
    filters?.querySelector('[name=q]')?.addEventListener('keydown', (event) => {
      if (event.key === 'Enter') {
        state.q = filters.querySelector('[name=q]').value.trim();
        sitemapsPage.render(view, ctx);
      }
    });
    view.querySelector('#new-sync')?.addEventListener('click', () => openSyncForm(view, ctx, sites));
    view.querySelectorAll('table.data tbody tr').forEach((row) => {
      row.addEventListener('click', () => {
        const item = sources.items.find((entry) => String(entry.id) === row.dataset.id);
        if (item && state.siteId) openSourceDrawer(view, ctx, Number(state.siteId), item);
      });
    });
  },
};

export default sitemapsPage;
