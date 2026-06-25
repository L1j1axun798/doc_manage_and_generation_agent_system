<script setup lang="ts">
const statusItems = [
  { label: '可见资料', value: '--' },
  { label: '我的项目', value: '--' },
  { label: '未读通知', value: '--' },
  { label: '待处理授权', value: '--' },
]
</script>

<template>
  <section class="dashboard-page">
    <header class="dashboard-page__header">
      <p class="dashboard-page__eyebrow">Wind Document System</p>
      <h1>风电资料系统</h1>
    </header>

    <div class="dashboard-page__metrics" aria-label="首页概览">
      <article
        v-for="item in statusItems"
        :key="item.label"
        class="dashboard-page__metric"
      >
        <span>{{ item.label }}</span>
        <strong>{{ item.value }}</strong>
      </article>
    </div>
  </section>
</template>
