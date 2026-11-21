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
page { background: #ffffff; color: #293653; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', sans-serif; font-size: 16px; }
button { font-family: inherit; cursor: pointer; }
button::after { border: 0; }
button:focus-visible { outline: 2px solid #347be5; outline-offset: 3px; }
textarea { font-family: inherit; }
/* #ifdef H5 */
uni-button { font-family: inherit; cursor: pointer; }
.app-shell uni-button::after { border: 0; }
uni-button:focus-visible { outline: 2px solid #347be5; outline-offset: 3px; }
/* #endif */
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation: none !important; transition: none !important; scroll-behavior: auto !important; }
}
</style>
