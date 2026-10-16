# Ch14 踩坑:交付硬化(CI + Playwright e2e + 非root/HTTPS)

> 这一章补交付底座:CI 工作流、Playwright 端到端、非 root/健康检查/HTTPS。坑集中在「e2e 起服务的方式」「antd 组件与 DOM 的错位」「空态渲染」「测试工具边界」「nginx 网络解析」——全是「上下文/环境」类,不是业务逻辑错,但都能让一条好好的链路跑不起来。

## 坑 1:e2e 起服务别复用已有服务,端口要与 docker 映射错开

> **2026-10-16 端口现状补充**:下面记的是**当时的现场** —— 那时 `docker compose` 把前端映射到
> 宿主 5173、后端映射到 8000。现在这几个端口已经重新分配过一轮:`8000` 是 docker 里的 **Chroma**、
> `5173` 是本仓库的 dev 前端、后端在 `8002`。当前值以 `scripts/devguard.mjs` 顶部的端口表为准。
>
> **事件描述保持原样** —— 改掉就等于篡改记录。而这个坑的成因(`reuseExistingServer` 复用了
> 一个"端口上碰巧有人响应"的旧容器)和具体端口号无关,仍然成立。

**现象**:本地 `npx playwright test` 反复失败——前端请求后端报「网络异常,请确认后端已启动」,但后端明明起在 8000。查页面快照发现前端渲染的是 33 小时前的旧代码(菜单里少了「趋势」)。

**根因**:两层叠加。
1. `webServer.reuseExistingServer: true` 会让 Playwright 在端口已有服务响应时**直接复用**它,而不是起自己的。当时 `docker compose up` 的前端容器正映射宿主 5173、后端映射 8000,Playwright 就复用了这两个 33 小时前的旧容器(旧代码、没走 E2E_MOCK、CORS 白名单里没有 e2e 端口)。
2. 复用旧后端 → CORS `allow_origins` 没有 e2e 的前端 origin → 浏览器拦掉跨域 → axios 拿不到 response → 统一报「网络异常」。

**修法**:
- e2e 的前后端用**专用端口**(后端 8001 / 前端 5174),`reuseExistingServer: false`,彻底不和 docker 映射的 8000/5173 抢。
- 后端 CORS `allow_origins` 同步加上 `http://localhost:5174`。
- 前端 vite 起服务时用 `VITE_API_BASE` 显式指向 8001。

**原理**:e2e 的价值在「用当前代码、可复现地跑」,任何「复用已有服务」都是引入不确定性的捷径——你以为在测新代码,其实在测一个没人记得的旧进程。端口和「是否复用」都要显式声明,别把「碰巧有个服务在跑」当成「我要的那个服务」。

## 坑 2:antd Select 的 placeholder 是 span,不是 input 的 placeholder 属性

**现象**:`page.getByPlaceholder('选评测集').click()` 一直等到超时,但页面上明明看得到「选评测集」。

**根因**:`getByPlaceholder` 匹配的是 DOM 里 input 的 `placeholder` **属性**,只有原生 input 才有。antd Select 是「div 拼出来的模拟组件」,它的 placeholder 是渲染成 `<span class="ant-select-selection-placeholder">选评测集</span>`,不是 input 属性。

**修法**:点 Select 内部的搜索框——它有个 `role=combobox` 的 input,`page.getByRole('combobox').click()` 打开下拉,再 `page.locator('.ant-select-item-option', { hasText: ... }).click()` 选选项。

**原理**:组件库的「假 input」和「真 input」语义不一致,按原生语义(placeholder 属性、value 属性)写的定位器会落空。优先用**语义角色**(role)和**可见文本**定位,别赌组件内部结构长成原生标签。

## 坑 3:空态提前 return,把「新建」按钮也一起藏了

**现象**:e2e 第一步就找不到「新建评测集」按钮,页面只有 Empty「还没有评测集」。

**根因**:DatasetsView 里写的是 `if (!data?.items.length) return <Empty description="还没有评测集" />`——这个**提前 return** 发生在「新建按钮」渲染之前,于是空库时整个视图只有空态、没有新建入口。首次使用(空库)的人根本没法建第一个评测集。

**修法**:按钮**始终渲染**,空态只替换表格部分:按钮放顶层,`{!data?.items.length ? <Empty/> : <Table/>}` 用三元替换表格而不是 return 掉整个视图。

**原理**:「无数据」和「无操作」是两回事——空态表达「还没有内容」,但「新建」这个动作本身永远可用。用提前 return 处理空态,等于把「展示层状态」错当成了「功能是否可用」;空态应当只替换**数据区**,不替换**操作区**。这类 bug 单元测试往往漏掉(测的是「空态显示什么」),要靠 e2e 走一遍首次使用路径才能抓到。

## 坑 4:vitest 会把 Playwright 用例也当成单测跑

**现象**:跑 `npm test`(vitest)报 `Playwright Test did not expect test() to be called here`,失败套件是 `e2e/main-flow.spec.ts`。

**根因**:vitest 默认 include 是 `**/*.{test,spec}.?[jt]s?(x)`,而 e2e 文件也叫 `*.spec.ts`,被 vitest 一并拾取。同一个文件里 `@playwright/test` 的 `test()` 在 vitest 环境里双注册,直接抛错。

**修法**:vite.config.ts 的 `test.include` 收紧成 `['src/**/*.{test,spec}.{ts,tsx}']`,让 vitest 只扫 src/,不碰 e2e/。

**原理**:两套测试框架各自有默认的文件匹配规则,当文件命名撞规则(`*.spec.ts`)时就会互相误拾。工具边界要**显式收窄**(include/exclude),别依赖默认值;这也和「环境/版本要显式」是一条线——默认值只有在没冲突时才是你的朋友。

## 坑 5:nginx 静态 upstream 在启动期解析,单跑容器起不来

**现象**:用 `docker run` 单独起前端容器验证 HTTPS,容器立刻退出,日志 `nginx: [emerg] host not found in upstream "backend"`。

**根因**:nginx.conf 里 `proxy_pass http://backend:8000/` 的 `backend` 是 **compose 服务名**,只在 compose 网络里有 DNS 条目。nginx 对**静态 upstream**(没有 resolver、不是变量拼接)会在**启动期**就解析域名,解析不到直接拒绝启动。单 `docker run` 的容器不在 compose 网络里,`backend` 解析不到 → 起不来。

**修法**:这不是要改配置——前端反代 backend 本就是 compose 编排的一部分,`docker compose up` 时 `backend` 能解析。本地想单独验证前端时,用 `docker run --add-host backend:127.0.0.1` 临时给个解析,或干脆跑整套 compose。验证 HTTPS 本身(证书自签、443 监听)用 `--add-host` 就够。

**原理**:容器编排里「服务名」和「网络」是绑定的,反代 upstream 用服务名是「假设我在 compose 网络里」。脱离编排单独跑某个容器,等于把它放进了错误的网络上下文——不是容器坏了,是它依赖的 DNS 环境变了。

## 小结

这一章的坑一句话:**测试和部署的「上下文」比代码本身更决定成败**——e2e 起服务要隔离端口、别复用旧进程;组件库 DOM 和原生语义不一致;空态不能吞掉操作入口;两个测试框架要划清边界;容器反代的 DNS 只在 compose 网络里成立。全是「环境/上下文」类问题,但都能让一条好好的链路跑不起来。
