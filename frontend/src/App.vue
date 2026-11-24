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
@import './styles/workspace.css';
/* Noto Serif SC heading subset: consistent weight without remote loading; license in static/fonts/OFL.txt. */
@font-face { font-family: 'ClearComplaint Display'; src: url('./static/fonts/clearcomplaint-display.woff2') format('woff2'); font-style: normal; font-weight: 600; font-display: swap; }
page { background: #fdfdf7; color: #1b1b18; font-family: Arial, -apple-system, BlinkMacSystemFont, 'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', sans-serif; font-size: 16px; }
button { font-family: inherit; cursor: pointer; }
button::after { border: 0; }
button:focus-visible { outline: 2px solid #2463eb; outline-offset: 3px; }
textarea { font-family: inherit; }
/* #ifdef H5 */
uni-button { font-family: inherit; cursor: pointer; }
.app-shell uni-button::after { border: 0; }
uni-button:focus-visible { outline: 2px solid #2463eb; outline-offset: 3px; }
html, body { margin: 0; min-height: 100%; background: #fdfdf7; }
body { overflow-x: clip; }
uni-button { -webkit-tap-highlight-color: transparent; }
input:focus-visible, textarea:focus-visible { outline: 2px solid #2463eb; outline-offset: 2px; }
/* #endif */
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation: none !important; transition: none !important; scroll-behavior: auto !important; }
}
</style>
