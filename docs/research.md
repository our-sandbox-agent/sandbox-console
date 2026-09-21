# 競品研究與優化建議（2026-09）

> 目的：對照市面上的 AI Agent 沙盒產品，找出我們「不打價格戰、追求整合體驗」的差異點，並回饋到雛形。費率皆取自各家 2026-09 公開定價頁，可能變動。

## 1. 競品一覽

| 產品 | 隔離技術 | 計費 | 閒置／暫停時 | 生命週期 |
|---|---|---|---|---|
| E2B | Firecracker | $0.0504/vCPU-hr + $0.0162/GiB-hr，按秒 | Paused 不計運算費 | running → paused → resumed；Hobby 連續 1h、Pro 24h 上限 |
| Daytona | 容器（可選 Kata） | 同 E2B 費率 | stopped 只算磁碟；15 分鐘自動停 | running → stopped → archived（7 天）→ deleted |
| Modal Sandboxes | gVisor | ~$0.142/core-hr + 記憶體，按秒 | 沒有 pause，只能 snapshot 後 terminate | 記憶體快照 7 天過期 |
| Fly Sprites | Firecracker | $0.07/CPU-hr + $0.04375/GB-hr | 幾秒無活動即自動暫停，只算儲存 | running → warm → cold，checkpoint 約 1s |
| Cloudflare Sandboxes | Firecracker 容器 | 只算 active CPU | sleep = $0 | active → sleep → wake |
| Vercel Sandbox | Firecracker | active CPU $0.128/vCPU-hr + 全時記憶體 | 記憶體仍計費 | 24h/session |
| Blaxel | Firecracker | 按記憶體秒計 | standby ≈ 25ms 恢復、不算運算 | running → standby |
| Runloop | microVM | $0.108/CPU-hr | suspend 需 Pro $250/mo | suspend / resume / snapshot |
| Morph Cloud | Firecracker 衍生 | 用量計費 | 快照後停 | 記憶體快照 <250ms fork，可無限分支 |
| Anthropic Managed Agents | 容器 | token + $0.08/session-hr | idle 不計 | session running / idle / ended |

**CLI／DX 共通模式**：`e2b sandbox spawn`、`sprite create` + `sprite console`、`daytona create --repo URL` + `daytona ssh`、`rli devbox ssh`。幾乎都：一行建立、一行接上 shell、可從 git repo 直接建立、Claude Code／Codex 預裝。

**開源可參考**：e2b-dev/infra（Firecracker + Nomad，最接近我們要做的）、kubernetes-sigs/agent-sandbox、microsandbox（libkrun）、OpenSandbox、Kata、Cloud Hypervisor。

## 2. 使用者最常抱怨的點

1. **等 LLM 也照全價收**：E2B／Daytona／Modal 保留 vCPU 全時計費，Agent 大部分時間其實在等模型回覆。
2. **Session 時間上限**：E2B 1h/24h、Modal 24h、Vercel 24h，長任務要自己 pause。
3. **基本月費門檻**：E2B Pro $150、Modal Team $250、Runloop suspend 要 $250。
4. **快照過期／隱藏費**：Modal 記憶體快照 7 天、Vercel 30 天、Blaxel standby $0.20/GB-mo。
5. **平台綁定**：Cloudflare 要 Workers + Dockerfile + wrangler；Modal 要 App/Image 前置。
6. **祕密外洩**：沙盒隔離了 Agent，但沒隔離 API key；transcript 含祕密。
7. **網路出口政策**：大多預設全開，deny-by-default 很少。

## 3. 對我們產品的建議（依優先序）

1. **把三段狀態做成「自動」而不是手動**：無終端輸入／無 CPU／Agent 回報完成 → N 分鐘後 Idle → 再 M 分鐘 Suspend。這是我們相對 E2B 的核心賣點；如果要使用者手動按 Suspend，就跟別人沒差。→ 雛形已加入 policy 與倒數。
2. **定價公式對齊業界**：改成 vCPU-hr + GiB-hr 拆開，Idle 只收記憶體＋磁碟、Suspend 只收快照儲存。避免自創一個「$/hr」讓人難比較。
3. **`sandbox claude` 之外還要 `sandbox ls / connect / suspend / snapshot`**：一行啟動只是入口，重連才是日常。→ 雛形終端已加。
4. **從 git repo 建立**（`sandbox claude --repo URL`），Suspend 時可選擇 push 分支，做到跨主機可攜。→ 雛形建立表單已加 Repository 欄位。
5. **快照與 fork**：Morph／Sprites 都把「分支出一個平行沙盒」當賣點，對跑實驗特別有用。→ 雛形已加 Snapshot / Fork。
6. **不設 session 上限，但快照設保留期**（例如 30 天）並明確顯示。
7. **祕密不進沙盒**：用 vault／proxy 注入 API key，是 Managed Agents 也沒完全解決的痛點，可當差異化。
8. **網路出口預設拒絕、白名單放行**。

## 4. 底層技術結論

- **有裸機／KVM（Hetzner AX、OVH、AWS .metal、GCP nested virt）→ Firecracker**：snapshot/restore + UFFD 延遲載入，恢復約 1s；overlay rootfs + 每沙盒 ext4 volume。這是 E2B／Sprites／Vercel 的架構。
- **一般 VPS 沒 /dev/kvm → gVisor `runsc checkpoint/restore`**：Modal 的路線，隔離較弱、跨主機恢復較脆弱，但沒有硬體依賴。
- **Firecracker 恢復後的坑**：網路連線不保證存活（重建 TAP、視所有 TCP 為斷線）、時鐘凍結要 step、同一快照多次恢復會重複亂數／token（要輪換祕密）。
- **閒置偵測**：PTY 無位元組 + guest CPU 低 + SDK 明確 `pause()`，三者合併，而非只看 wall-clock。
- **終端串流**：xterm.js ↔ WebSocket ↔ guest 內 pty daemon 接 tmux，經 vsock 出來；重連 `tmux attach` 即可。
- **檔案**：overlay rootfs + volume + 可選 git push；virtio-fs 上游 Firecracker 不支援，9p 被拒。
- **控制平面**：先從 e2b-dev/infra 或 agent-sandbox 起步，不要從零寫。

## 5. 主要來源

- E2B billing / persistence docs、Daytona pricing、Modal pricing & snapshots、Fly Sprites、Cloudflare Sandbox GA blog、Vercel Sandbox pricing、Blaxel、Runloop、Morph Infinibranch、Together Code Sandbox
- Firecracker snapshot-support.md、UFFD docs；gVisor checkpoint/restore docs；Modal mem-snapshots blog
- fly.io/learn/ai-sandbox-pricing、bex.co 比較文、LogRocket 平台比較、HN Sprites 討論

## 6. 補充（2026-09-22）：Boat、Agent 37、Archal 與瀏覽器 IDE

- **Boat（boat.dev）**：持久 Linux VM、CLI 與 SDK 為主、串流桌面；專案靠 Environments 設定自動 git clone；按秒計、停止免費、預付方案；每分鐘自動磁碟快照，「快照存不下來就拒絕停止」；預設 TTL 從建立起算。
- **Agent 37 Cloud**：API-first 的 agent 託管，網頁終端加檔案瀏覽器加遠端桌面；預付錢包按分扣，睡眠只算磁碟，冷儲存更低費率；建立前錢包需有一天的運行費；宣稱 gVisor。
- **Archal**：模擬第三方 API 的有狀態測試環境，不是計算沙盒，不對標。
- **共通點**：都沒做瀏覽器版 VS Code；都以 git clone 為主入口；都預付額度、免卡試用；沒有人在 MVP 接 Stripe 訂閱。
- **我們有而他們沒有**：依任務完成的自動降級、無預設時限、放行證據、帶不確定區間的帳本、冷恢復依 session 接回對話。
- **瀏覽器 IDE 選項**：只有 code-server 可行（MIT、Open VSX、子路徑、驗證交外層、非 root 映像、月更）；微軟 VS Code Server 授權禁止代管；OpenVSCode Server 自 2026-02 停更；Theia 瀏覽器版實驗性；Coder 是整套平台。Claude Code 擴充在 Open VSX，官方建議裝不上就在整合終端跑 CLI。代價：每沙盒多數百 MB 到 1 GB、代理層與 Idle 訊號要改、約 1.5 到 2.5 人週一次性工作。gVisor #14761（非 root 開不了 PTY）要先在 #8 釐清。決定見 plan.md「已決定的方向」與 #52。
