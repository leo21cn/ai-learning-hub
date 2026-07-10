---
kind: frontend_style
name: Tailwind CSS 原子化样式体系
category: frontend_style
scope:
    - '**'
source_files:
    - frontend/tailwind.config.js
    - frontend/src/index.css
    - frontend/postcss.config.js
    - frontend/package.json
    - frontend/src/pages/public/Home.tsx
---

前端采用 **Tailwind CSS v3 + PostCSS + Autoprefixer** 的原子化样式方案，配合 Vite 构建。核心约定如下：

1. **样式入口与全局变量**
   - `src/index.css` 通过 `@tailwind base/components/utilities` 注入 Tailwind 层，并定义 CSS 自定义属性 `--header-height: 56px` 作为全局布局 token。
   - 定义 `.brand-title` 类实现渐变色标题（蓝→紫），统一品牌视觉。

2. **设计令牌（Design Tokens）**
   - 在 `tailwind.config.js` 的 `theme.extend.colors.primary` 中集中声明主色板（50/500/600/700），组件一律使用 `text-primary-*`、`bg-primary-*`、`focus:ring-primary-500` 等语义化变体，禁止硬编码十六进制颜色。
   - `fontFamily.sans` 扩展为 `PingFang SC → Microsoft YaHei → system-ui`，确保中英文混排一致。

3. **构建管线**
   - `postcss.config.js` 仅挂载 `tailwindcss` 与 `autoprefixer`，无额外插件；Vite 通过 `vite.config.ts` 驱动，无需单独 CSS 打包步骤。
   - `package.json` 依赖 `tailwindcss@^3.4.16`、`autoprefixer@^10.4.20`、`postcss@^8.4.49`，版本锁定且与 Vite 生态兼容。

4. **组件内样式约定**
   - 所有 UI 通过 JSX `className` 直接书写 Tailwind 原子类，未引入任何 CSS-in-JS 或第三方 UI 库（如 AntD/MUI）。
   - 交互态统一用 `hover:`、`focus:`、`focus:ring-*` 修饰；阴影用 `shadow-sm`；圆角用 `rounded-lg` / `rounded-r-lg` 等原子值。
   - 布局以 Flexbox 原子类为主（`flex flex-col items-center pt-[20vh] px-4`），避免手写 `style` 属性。

5. **可访问性与测试标记**
   - 关键交互元素附带 `data-testid`（如 `home-search-input`、`home-search-btn`），便于 Playwright E2E 定位。

该风格体系轻量、无运行时开销，通过单一主题色与字体配置即可保持全站视觉一致。