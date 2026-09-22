import { defineConfig } from 'vite';
import mdx from '@mdx-js/rollup';
import remarkFrontmatter from 'remark-frontmatter';
import remarkMdxFrontmatter from 'remark-mdx-frontmatter';

export default defineConfig({
  base: '/sandbox-console/',
  plugins: [
    mdx({
      jsxImportSource: 'preact',
      remarkPlugins: [remarkFrontmatter, remarkMdxFrontmatter],
    }),
  ],
});
