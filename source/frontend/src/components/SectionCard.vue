<template>
  <section class="section-card">
    <header class="section-card__header">
      <div class="section-card__title">
        <slot name="icon"></slot>
        <h2><slot name="title"></slot></h2>
      </div>
    </header>
    <div class="section-card__body">
      <slot></slot>
    </div>
  </section>
</template>

<script setup>
// Lightweight wrapper card with consistent dark style
</script>

<style scoped>
.section-card{
  border-radius: 16px;
  background: var(--card-bg, #0f172a);
  padding: 20px;
  margin-bottom: 24px;
  border: 1px solid var(--border-color, rgba(255,255,255,0.1));
  box-shadow: 0 4px 14px rgba(0,0,0,0.25);
}
.section-card__header{
  margin-bottom: 12px;
}
.section-card__title{ display:flex; align-items:center; gap:8px; }
.section-card__title h2{ font-size: 18px; margin:0; font-weight:700; color: var(--text-color, #e5e7eb); }
.section-card__body{ color: var(--text-color, #e5e7eb); }
</style>


