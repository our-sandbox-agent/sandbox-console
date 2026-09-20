# Sandbox Console — 互動雛形

AI Agent 沙盒產品的第一版可操作介面。這是本機模擬，沒有真正的 VM、Agent API、shell 執行或收費。

線上展示：https://our-sandbox-agent.github.io/sandbox-console/

## 啟動

Node.js 20.19+ 或 22.12+。

```sh
npm ci
npm run dev -- --port 4173
```

開啟 http://localhost:4173 。`npm run build` 產生靜態頁面於 `dist/`。

## 可體驗流程

- Claude / Codex / Harness 快速啟動、新增自訂名稱與規格的沙盒。
- 搜尋及依 Active / Idle / Suspend 篩選。
- Active → Idle 或 Suspend；Idle / Suspend → Active。
- 模擬 terminal：help、pwd、ls、status、clear、sandbox claude / codex / harness。其他輸入不執行。
- 個別沙盒的檔案及資料夾上傳、相對路徑保留、原始內容下載。每檔上限 10 MB。
- 三段示意費率與按狀態累計的 session 費用，4 vCPU 為 2 vCPU 示意費率的兩倍。
- 自動降級：無活動 N 分鐘 Active → Idle，再 M 分鐘 → Suspend，門檻可在 Usage 頁調整，詳情頁顯示倒數。
- Snapshot / Fork：對沙盒建立快照，從快照分支出新沙盒（含檔案）。
- 從 git repo URL 建立沙盒（模擬 clone）。
- 終端新增 sandbox ls / connect <id> / suspend / snapshot、git status。
- Usage 頁與 E2B、Daytona、Modal、Fly Sprites、Vercel 的同小時工作成本比較。
- 手機與桌面布局。

## 研究與建議

競品比較、痛點與優化建議見 [docs/research.md](docs/research.md)。

## 資料與限制

沙盒與紀錄儲存在 localStorage，檔案儲存在 IndexedDB。同一 origin／瀏覽器重整後保留；清除網站資料會移除。沒有跨裝置同步。避免上傳敏感檔案。計時只累計頁面開啟期間；多分頁同步、離線計費與後端權威時鐘尚未實作。初始三個沙盒與既有時數是展示資料，費率不是商業報價。資料夾請用 Upload folder 按鈕選取；拖放區支援一般檔案。不同路徑同名檔案可共存，相同完整路徑再次上傳會覆寫。

此版本不驗證 gVisor / Firecracker 的隔離安全性或 suspend 能力。介面中的 Resume 只切換模擬狀態。

## 後續實作邊界

1. 控制平面 API：登入、工作區、沙盒生命週期、租戶隔離、操作授權。
2. Runner 介面：create / exec / suspend / resume / destroy，將 gVisor 與 Firecracker 差異封裝於 adapter。須先驗證主機虛擬化支援與安全模型。
3. Agent 整合：CLI、串流終端、憑證注入、工作退出與重連。
4. 檔案傳輸：物件儲存、目錄 manifest、續傳、權限與路徑驗證。
5. 計量：伺服器端 lifecycle events、單一時鐘、失敗恢復及可核對帳務。

產品原型刻意先驗證「啟動 → 工作 → 暫停 → 接續」流程，尚未承諾底層基礎設施的可行性或效能。
