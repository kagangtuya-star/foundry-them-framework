# FVTT Join Theme Framework

该仓库提供一个可插拔的 Foundry VTT 世界登陆页主题框架，以及配套的桌面安装器 `installer_app`。目标是让前端工程师或 AI 代理无需触及核心引擎即可开发、预览、分发多套登录主题。本 README 说明框架能力、目录布局与主题开发流程，并给出面向 AI 的实现提示。

## 功能概览

- **动态主题加载**：`public/scripts/foundry.mjs` 在渲染 JoinGameForm 前，根据世界配置的 `joinTheme` 拉取对应脚本并实例化自定义 `ApplicationV2` 子类。
- **常量同步**：`common/constants.mjs` 中的 `WORLD_JOIN_THEMES` 用于服务器校验，和前端 `JOIN_THEME_SCRIPTS` 保持一致，确保世界设置可见。
- **内置 Simple 主题**：提供一个带背景图/视频、表单渐变与 CTA 区域的基础主题，可直接在世界中启用，也可作为新主题的蓝本。
- **主题安装器**：PyQt GUI 支持一键安装框架、导入导出 ZIP、打包主题目录，以及为主题附加 `.webm` 背景视频。
- **AI 友好**：`docs/gemini-theme-dev.md` + 本 README 描述模板上下文、提交逻辑与 CSS 注入规则，便于 LLM 自动生成完整主题。

## 目录结构

```
installer_app/               # GUI 安装器与打包工具
  resources/                 # Simple 主题模板/样式副本
  core.py                    # 打补丁、导入导出、背景视频
  gui.py                     # PyQt6 UI
```
## Join Theme 工作流

1. 世界配置 `joinTheme`（非 `default/minimal`）后，`JoinGameForm.#joinView()` 读取 `JOIN_THEME_SCRIPTS[themeKey]`。
2. 通过 `fetch` 拉取脚本并 `Function("return " + source)` 生成类，若有效则替换默认 `JoinGameForm`。
3. 自定义类继承 `foundry.applications.api.ApplicationV2`，通常混入 `HandlebarsApplicationMixin` 以驱动多模板分区。
4. 构造函数负责注入 CSS、设置 `<body>` class、调用 `game.users.apps.push(this)` 便于回收。
5. `_prepareContext()` 组装模板数据；`PARTS` 描述各 Handlebars 模板与表单处理器；提交逻辑仍复用官方 `JOIN` 接口。
6. `_syncPartState()` 需手动复制 `userid`、`password` 等输入值，保证局部渲染后状态不丢失。

## 主题资源规范

- **脚本**：放在 `public/joinmenu-so-nice/<theme-id>/joinmenu.js`，结尾需 `return <className>;`。使用 ES2022 语法，勿依赖构建流程。
- **模板**：置于 `templates/joinmenu-so-nice/<theme-id>/`，每个 `PARTS` 必须渲染单一根元素（一个 `<form>` 或 `<section>`），避免插入 `<link>`/`<script>`。
- **样式**：集中在 `public/joinmenu-so-nice/<id>/custom.css`，由脚本注入 `<link>`。可以使用 `@import` 引入字体，也可在 `installer_app` 资源中存放。
- **静态资源**：把图片、视频等置于同主题目录下，使用相对路径引用；若需要跨主题共享，可放置在 `public/joinmenu-so-nice/shared/` 并自行加载。
- **命名**：主题 ID 必须满足 `/^[A-Za-z_][A-Za-z0-9_]*$/`，以便自动更新 `WORLD_JOIN_THEMES` 与 `JOIN_THEME_SCRIPTS`。
## `joinmenu.js` 模板

```javascript
class mytheme extends foundry.applications.api.HandlebarsApplicationMixin(foundry.applications.api.ApplicationV2) {
  static #styleId = "mytheme-style";

  constructor(options) {
    mytheme.#injectCSS();
    document.body.classList.add("join-theme-mytheme");
    super(options);
    game.users.apps.push(this);
  }

  static #injectCSS() {
    if ( document.getElementById(this.#styleId) ) return;
    const link = document.createElement("link");
    link.id = this.#styleId;
    link.rel = "stylesheet";
    link.href = "joinmenu-so-nice/mytheme/custom.css";
    document.head.appendChild(link);
  }

  static PARTS = {
    hero: { id: "hero", template: "templates/joinmenu-so-nice/mytheme/hero.hbs" },
    form: { id: "form", template: "templates/joinmenu-so-nice/mytheme/form.hbs", forms: {"#join-game-form": { handler: mytheme.#onSubmitLoginForm }}},
    setup:{ id: "setup", template:"templates/joinmenu-so-nice/mytheme/setup.hbs", forms: {"#join-game-setup": { handler: mytheme.#onSubmitSetupForm }}}
  };

  async _prepareContext() {
    const strip = foundry?.utils?.stripHTML ?? (s => s);
    return {
      world: game.world,
      users: game.users,
      passwordString: game.data.passwordString,
      mytheme: {
        tagline: strip(game.world?.description ?? "").slice(0, 120) || game.world?.title,
        heroImage: game.world?.background ?? "",
        heroVideo: await mytheme.#resolveHeroVideo()
      }
    };
  }

  // #onSubmitLoginForm/#onSubmitSetupForm/#post 建议直接复制官方 JoinGameForm，实现一致行为
}

return mytheme;
```

### 必备处理器
- `#onSubmitLoginForm`：校验 `userid`，POST `{action: "join"}`，处理 `HttpError`。
- `#onSubmitSetupForm`：确认在线用户，POST `{action: "shutdown"}`。
- `_syncPartState`：在 `partId === "form"` 时把旧 DOM 值复制到新 DOM。
- `close()`：移除 `<body>` 上的主题类，释放引用。
## 模板上下文速查

| 字段 | 内容来源 |
| --- | --- |
| `world.title` / `world.background` / `world.description` | 世界配置，描述常含 HTML，需 `stripHTML` |
| `users` | `game.users` 集合，可遍历 `id/name/active/isGM` |
| `passwordString` | 若启用访问密码将在模板中提示 |
| `isAdmin` | `game.data.isAdmin`，可决定是否显示返回设置按钮 |
| `usersCurrent` / `usersMax` | 当前在线玩家数 / 用户总数 |
| `simpleTheme.tagline` | Simple 主题的短标语，可根据世界描述生成 |
| `simpleTheme.heroImage` | `game.world.background` 或手动指定的图片 |
| `simpleTheme.heroVideo` | `.webm` 视频 URL（世界背景或本地 `background.webm`） |
| 自定义字段 | `_prepareContext` 任意添加，如 CTA、背景色、可选面板等 |

> 提示：Handlebars 模板不可包含 `<script>`，如需动态行为请在 `joinmenu.js` 中用 `activateListeners` 绑定事件。
## 样式与背景策略

- **加载优先级**：Simple 主题示范了 `preload + ready/loading class`。CSS 里可以通过 `.join-theme-<id>-loading #join-game { opacity: 0; }` 避免默认主题闪现。
- **背景图/视频**：`simpleTheme.heroVideo` 优先取 `world.background` 中的 `.webm`，否则检测 `joinmenu-so-nice/<id>/background.webm`。你也可以扩展缓存策略或添加兜底图片。
- **响应式布局**：Join 页面内容处于固定容器，可通过 `body.join-theme-<id>` 控制全局背景，再为 `.application`（表单）调整透明度、投影与动画。
- **字体管理**：允许在 CSS 中使用 `@import`，但要考虑加载时序；如需极致性能，可选择把关键 @font-face 转为本地文件。
- **无障碍**：保证按钮对比度、输入标签可读，同时确保 `tabindex` 正常；必要时在模板中添加 `aria-label`。
## 安装器 `installer_app`

1. 运行 `python installer_app/main.py`（或在 Windows 上双击 `run.cmd`）。
2. 选择 FVTT 根目录，点击“安装框架”即会：
   - 拷贝 Simple 主题至 `public/` 与 `templates/`；
   - 自动为 `foundry.mjs`、`constants.mjs` 打补丁，注册 `Join Theme Loader`；
   - 写入 `.join-theme-framework.json` 标记。
3. 其他操作：
   - **导入主题**：选择主题 ZIP，包含 `theme.json`、`templates/`、`public/` 即可。
   - **导出主题**：基于已安装主题生成 ZIP，可供分发。
   - **打包主题目录**：从任意本地目录打包符合规范的 ZIP。
   - **附加背景视频**：选中主题后点击“附加背景视频”，挑选 `.webm` 文件，安装器会复制到 `public/joinmenu-so-nice/<id>/background.webm`，Simple 主题会自动使用。
   - **移除背景视频**：若需回滚，点击“移除背景视频”即可删除 `background.webm`，恢复到世界或主题默认的背景逻辑。
   - **恢复备份**：将 `foundry.mjs`、`constants.mjs` 回滚至 `.backup`。

> `installer_app/resources/` 中存放 Simple 主题的模板与样式，若你更新 Simple，请同步这里，保证一键安装能分发最新版本。
## 开发与集成流程

1. **创建主题资源**：在 `templates/joinmenu-so-nice/<id>/` 中添加每个 PART 的 `.hbs`，在 `public/joinmenu-so-nice/<id>/` 中创建 `joinmenu.js` 与 `custom.css`。建议先复制 Simple 主题再替换样式。
2. **注册主题**：若未使用安装器，可手动修改：
   - `common/constants.mjs`: 向 `WORLD_JOIN_THEMES` 添加 `<id>: "显示名称"`；
   - `public/scripts/foundry.mjs`: 同时更新 `WORLD_JOIN_THEMES` 和 `JOIN_THEME_SCRIPTS`，指向 `joinmenu-so-nice/<id>/joinmenu.js`；
   - 确认 `#joinView()` 片段包含“Join theme loader”逻辑（安装器会自动注入）。
3. **测试**：
   - 启动 FVTT，进入世界选择页，修改世界配置选择新主题；
   - 检查登录表单、管理员返回功能、错误提示；
   - 调试模板渲染错误（常见：PART 输出多个根元素）。
4. **打包发布**：使用安装器“导出主题”或 `core.pack_external_theme` 生成包含 `theme.json` 的 ZIP，方便他人导入。
5. **迭代 Simple 主题**：更新 `public/` 下的文件后别忘记同步 `installer_app/resources/` 目录，使安装器发放的是最新版本。
## 主题开发提示

- **输入**：向模型提供 `docs/gemini-theme-dev.md`、本 README 以及 Simple 主题源码，要求其按指定目录输出 `joinmenu.js`、多个 `.hbs` 与 `custom.css`。
- **输出格式**：建议让模型分块返回（脚本/模板/CSS），避免一次生成的内容超出长度限制。
- **数据库引用**：传递必要的上下文字段（世界标题、描述、背景 URL）即可，复杂逻辑留给 `_prepareContext`。
- **验证问题**：提示模型检查 PART 是否只有单根元素、CSS 路径是否正确、`return <className>;` 是否存在。
- **多主题协作**：当需要生成多套主题时，可要求模型使用统一的 class 命名规则，例如 `join-theme-<id>`，方便后续 CSS 管理器替换。
