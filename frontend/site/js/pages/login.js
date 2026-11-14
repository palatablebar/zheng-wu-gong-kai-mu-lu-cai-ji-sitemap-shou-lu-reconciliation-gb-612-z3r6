import { api } from '../api.js';
import { session } from '../store.js';
import { BRAND } from '../config.js';
import { errorMessage, esc, toast } from '../ui.js';

/** 登录页：档案馆的「卷宗检索」——左边一叠索引卡，右边借阅登记卡。 */
export const loginPage = {
  async render(root, ctx) {
    root.className = 'login-host';
    const cards = [
      ['档号', BRAND.catalogMark, true],
      ['卷宗', BRAND.catalogLabels[0], false],
      ['保管期限', BRAND.catalogLabels[1], false],
      ['办理方式', BRAND.catalogLabels[2], false],
    ];
    root.innerHTML = `
      <div class="login">
        <section class="login-brief">
          <div class="eyebrow">${esc(BRAND.edition)}</div>
          <h1>${esc(BRAND.title)}<br /><em>${esc(BRAND.short)}</em></h1>
          <p class="tagline">${esc(BRAND.loginLead)}</p>
          <div class="card-catalog" data-testid="card-catalog">
            ${cards
              .map(
                ([no, label, head]) =>
                  `<div class="index-card ${head ? 'is-head' : ''}"><span class="no">${esc(no)}</span><span class="label">${esc(label)}</span></div>`,
              )
              .join('')}
          </div>
          <div class="brief-points">
            ${BRAND.loginPoints
              .map(([no, text]) => `<div class="brief-point"><i>${esc(no)}</i><span>${esc(text)}</span></div>`)
              .join('')}
          </div>
          <div class="eyebrow">${esc(BRAND.org)} · 内部工作台</div>
        </section>
        <section class="login-form-wrap">
          <form class="login-card" id="login-form" novalidate>
            <div>
              <div class="brand">借阅登记卡</div>
              <div class="sub">使用编辑部内部账号登录。三个演示账号权限不同，导航、按钮与数据可见范围随角色变化。</div>
            </div>
            <div class="field">
              <label for="email">邮箱</label>
              <input id="email" name="email" type="email" autocomplete="username" value="admin@${esc(BRAND.short)}.io" required />
            </div>
            <div class="field">
              <label for="password">密码</label>
              <input id="password" name="password" type="password" autocomplete="current-password" value="Demo@2026" required />
            </div>
            <div class="form-error" id="login-error" role="alert"></div>
            <button class="btn accent" id="login-submit" type="submit">调阅台账</button>
            <div class="login-hint">
              演示账号（密码 <code>Demo@2026</code>）：<br />
              <code>admin@${esc(BRAND.short)}.io</code> 编辑部主管 ·
              <code>analyst@${esc(BRAND.short)}.io</code> 巡检专员 ·
              <code>viewer@${esc(BRAND.short)}.io</code> 公开办审阅
            </div>
          </form>
        </section>
      </div>`;

    const form = root.querySelector('#login-form');
    const errorNode = root.querySelector('#login-error');
    const submit = root.querySelector('#login-submit');
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      errorNode.textContent = '';
      submit.disabled = true;
      submit.textContent = '正在核对…';
      try {
        const result = await api.post('/api/auth/login', {
          email: form.email.value.trim(),
          password: form.password.value,
        });
        session.set(result.access_token, result.user);
        toast(`欢迎回来，${result.user.display_name}`);
        location.hash = '#/overview';
        await ctx.reload();
      } catch (err) {
        errorNode.textContent = err.code === 'AUTH_INVALID' ? '账号或密码不正确' : errorMessage(err);
      } finally {
        submit.disabled = false;
        submit.textContent = '调阅台账';
      }
    });
  },
};

export default loginPage;
