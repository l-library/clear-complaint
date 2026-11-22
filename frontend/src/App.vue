<script setup lang="ts">
import { onLaunch, onShow, onHide } from "@dcloudio/uni-app";
onLaunch(() => {
  console.log("App Launch");
});
onShow(() => {
  console.log("App Show");
});
onHide(() => {
  console.log("App Hide");
});
</script>
<style>
@import url("./styles/tokens.css");
@import url("./styles/base.css");

uni-button,
button {
  transition:
    transform var(--dur-micro) var(--ease-out),
    background-color var(--dur-micro) var(--ease-out),
    border-color var(--dur-micro) var(--ease-out),
    color var(--dur-micro) var(--ease-out);
}

uni-button:active,
button:active {
  transform: translateY(1px);
}

uni-button[disabled],
button[disabled] {
  opacity: 0.55;
  cursor: not-allowed;
}
</style>
