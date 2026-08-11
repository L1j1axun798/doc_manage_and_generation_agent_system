<template>
  <footer class="site-footer" aria-label="网站备案与版权信息">
    <p class="site-footer__content">
      <span>© 2026 绿能信盾检测技术服务(保定)有限公司</span>
      <span class="site-footer__separator" aria-hidden="true">·</span>
      <span>www.greenenergyinsp.cn</span>
      <span class="site-footer__separator" aria-hidden="true">·</span>
      <a
        href="https://beian.miit.gov.cn/"
        rel="noopener noreferrer"
        target="_blank"
        title="前往工业和信息化部 ICP/IP地址/域名信息备案管理系统"
      >
        冀ICP备2026028278号-1
      </a>
    </p>
  </footer>
</template>

<style scoped>
.site-footer {
  display: flex;
  min-height: var(--site-footer-height);
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  padding: var(--space-2) var(--space-4);
  border-top: 1px solid var(--color-divider);
  color: var(--color-text-tertiary);
  background: var(--color-bg-surface);
  font-size: var(--font-size-xs);
  line-height: 20px;
}

.site-footer__content {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: center;
  gap: 0 var(--space-2);
  margin: 0;
  font-variant-numeric: tabular-nums;
  text-align: center;
}

.site-footer a {
  color: var(--color-text-secondary);
  text-underline-offset: 3px;
}

.site-footer a:hover,
.site-footer a:focus-visible {
  color: var(--color-brand);
  text-decoration: underline;
}

.site-footer a:focus-visible {
  border-radius: var(--radius-xs);
  outline: 2px solid var(--color-brand-focus);
  outline-offset: 2px;
}

.site-footer__separator {
  color: var(--color-border-strong);
}

@media (max-width: 600px) {
  .site-footer {
    padding-inline: var(--space-3);
  }

  .site-footer__separator {
    display: none;
  }

  .site-footer__content {
    column-gap: var(--space-3);
  }
}
</style>
