
<template><div><MyComponent @event="handler"/></div></template>
<script lang="ts">
export default { name: 'TestVue', props: ['id'], methods: { handler() {} } }
</script>